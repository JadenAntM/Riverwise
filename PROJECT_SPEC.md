# Riverwise: Brook Trout Conditions — implementation specification

## Product goal

Build a mobile-friendly dashboard for anglers checking Nova Scotia rivers. Show measured river flow and nearby weather, plus a transparent **experimental conditions score**. The score is a heuristic for exploring conditions, not a validated prediction of catches, river safety, fish abundance, habitat quality, or legal fishing eligibility.

Always show observation time, source, qualifiers, and data gaps. Refer to the feature as a **conditions score**, never as a “bite probability.”

## Product positioning

Use **Riverwise: Brook Trout Conditions** as the working product name. Avoid “Bite Window” in the product title because it suggests a validated prediction that the application does not provide.

The principal portfolio story is:

> A reliable full-stack data product built around imperfect public datasets, with idempotent ingestion, provenance, freshness handling, accessible visualization, and transparent versioned scoring.

## First release

Start with one verified active Nova Scotia gauge that reports recent discharge and deliver a complete data-to-page vertical slice. After that slice is reliable, expand to **three verified active gauges**, including a Margaree gauge only if usable discharge is available.

Keep station IDs, names, coordinates, and source links in an editable seed file. Expand to 10–20 stations only after the first release is reliable. A gauge describes its location, not an entire river or a fishing access point. Never invent station IDs.

Visitors can:

- Browse an accessible station list.
- Open a station to see its score or explicit unavailable state, reasons, latest observations, nearby weather, and a 48-hour discharge chart.
- Compare a station’s flow with its own recent baseline.
- Optionally use a map after the list and detail experiences are complete. All data must remain accessible without the map.

No accounts, alerts, machine learning, predicted river flow, or province-wide coverage in v1. A forward-looking “bite window” chart is outside v1.

## Data sources and constraints

| Source | Data | Important distinction |
| --- | --- | --- |
| [Water Survey of Canada real-time CSV service](https://wateroffice.ec.gc.ca/services/) | Station, timestamp, discharge in m³/s; optional level in m and qualifiers | Measurements may arrive late and be provisional or revised. Preserve observation time, units, and qualifiers. Its documented recent endpoint supports parameter 47 (discharge) and 46 (level); inspect real CSV headers before fixing parser assumptions. |
| [WSC station metadata](https://wateroffice.ec.gc.ca/download/csv_help_e.html) | Official ID, name, coordinates, province, active/real-time flags | Verify that every seed station actually reports discharge; active alone is insufficient. |
| [Open-Meteo API](https://open-meteo.com/en/docs) | Nearby hourly air temperature, precipitation, cloud cover, and pressure when available | Air temperature is not water temperature. Differentiate modeled historical/current weather from forecasts. Confirm usage, licensing, retention, and attribution terms before deployment. |

Fetch nearby weather at each gauge’s coordinates and align it by UTC hour. Do not overwrite hydrometric observation timestamps with weather timestamps. Never use future forecast values to compute a current score. Do not infer fish habitat or legal fishing eligibility from gauge data.

Before implementation assumptions are finalized, record:

- Actual provider headers, timestamp conventions, units, null conventions, and qualifier fields.
- Provider attribution and fixture-redistribution requirements.
- The definition and timestamp semantics of hourly precipitation.
- Whether the weather value is historical, modeled/current, or forecast.

## Architecture and repository

- `apps/web`: Next.js + TypeScript and Recharts. Add a client-rendered Leaflet map only after the accessible list and station detail page work well.
- `apps/api`: FastAPI, read-only station endpoints, and a pure, versioned scoring module.
- `jobs/ingest`: Python with HTTP timeouts, bounded retries, and typed parsing. Separate extraction, validation, normalization, persistence, and scoring. Pandas is optional for future batch history.
- PostgreSQL with migrations. Docker Compose runs the web application, API, and database locally. Include a one-shot import command and seed script.

**Deployment comes after local verification.** Make ingestion callable by an hourly scheduler. EventBridge/Lambda and a hosted database are optional later choices, subject to networking requirements and a measured cost estimate. Do not promise $0 hosting. Configure budget alerts before provisioning paid cloud resources.

## Smallest vertical slice

Before expanding features, complete this path for one station:

1. Fetch a real discharge response and retain a raw test fixture.
2. Validate, normalize, and idempotently persist the observations.
3. Read the observations through one API endpoint.
4. Render a mobile-friendly station page containing the value, unit, source, observation time, freshness, and visible gaps or unavailable state.
5. Exercise the path using an automated smoke test.

Weather, scoring, additional stations, the chart, and the map follow this slice in that order unless source discovery reveals a better dependency order.

## Data model

- `stations`: official ID (PK), name, latitude, longitude, province, active, has_discharge, display_order, source_url.
- `hydro_observations`: station_id, observed_at_utc, parameter (`discharge` / `level` / `water_temperature` / `daily_discharge`), value, unit, qualifier (nullable), ingested_at_utc. Unique on (station_id, observed_at_utc, parameter). The latter two parameters are post-MVP extensions and do not change the v1 contract.
- `weather_hours`: station_id, valid_at_utc, kind (`historical_or_modelled` / `forecast`), air_temp_c, precip_mm, cloud_cover_pct, pressure_hpa, ingested_at_utc. Unique on (station_id, valid_at_utc, kind). If past weather is unavailable, leave historical fields null rather than labeling a forecast as observed.
- `score_snapshots`: station_id, computed_at_utc, hydro_observed_at_utc, score (nullable), status, confidence, available_points, earned_points, components_json, rules_version.
- `ingest_runs`: started_at_utc, ended_at_utc, source, status, fetched/upserted counts, duration, and concise error.

Index hydro on (station_id, parameter, observed_at_utc DESC) and weather on (station_id, valid_at_utc DESC). Store UTC; display Atlantic time with an explicit timezone and correct daylight-saving offset. Preserve gaps rather than inventing measurements.

## Ingestion and derived features

1. Verify one station ID and inspect live CSV and weather responses. Commit small fixtures containing valid, missing, qualified, and revised rows. Record actual provider headers and date handling. Expand to three stations only after the vertical slice works.
2. Every run fetches an overlapping recent window, initially 72 hours, to capture delayed or revised values. Upsert observations; reruns must not duplicate records, and changed upstream values must update.
3. Validate allowlisted IDs, timestamps, units, finite nonnegative flow, and plausible weather values. A successful HTTP response containing unusable content counts as a failed source run.
4. Backfill bounded discharge history for a **14-day station-specific reference**. Compute its median from previous valid readings; require at least 24 valid readings spanning seven days. If insufficient, return `insufficient_history`. Do not compare raw flow between rivers.
5. Compute 1-hour and 6-hour percentage changes only when readings exist close to both target endpoints. Start with a documented tolerance of ±30 minutes and revisit it after observing actual station cadence. Do not interpolate across multi-hour gaps for scoring. A 24-hour change may be shown when supported.
6. Percentage change is unavailable when the earlier value is zero or below a documented small-positive guard value. Never divide by zero or report an unbounded percentage as a normal trend.
7. Handle one failed provider independently of another. Preserve previous observations, record source errors, and expose the last successful ingestion separately from the last measured reading.

An hourly job is not an hourly measurement guarantee: [WSC’s service standard](https://www.canada.ca/en/environment-climate-change/services/meteorological-service-standards/publications/hydrometric-data-information/chapter-3.html) allows near-real-time data to appear within two hours of observation.

## Score v1

Implement a deterministic, pure function that receives an explicit evaluation time and returns a 0–10 score, status, confidence, available points, earned points, component points, and plain-language reasons. Do not read the system clock inside the scoring function.

These thresholds are initial product assumptions, not established biological criteria. Put constants, interval inclusivity, timestamp tolerances, and rules version in one module so they can be reviewed and changed.

| Component | Maximum | Initial rule |
| --- | ---: | --- |
| Flow / station 14-day median | 4 | 4 points for ratio 0.8–1.5 inclusive; 2 for 0.5–<0.8 or >1.5–2.0; 0 otherwise. Requires a positive valid median. |
| 6-hour flow change | 2 | 2 for change from −20% through 0% inclusive; 1 for a rise >0% through 20%; 0 for a fall below −20% or rise above 20%. |
| Precipitation, previous 12 complete UTC hours | 2 | Sum intervals in `[evaluation_hour − 12h, evaluation_hour)`. Award 2 for 1–10 mm inclusive; 1 for 0–<1 mm; 0 for >10 mm. Mark missing if adequate non-forecast weather is unavailable. |
| Current cloud cover | 2 | Use the non-forecast weather hour containing the evaluation time, within a documented freshness tolerance. Award 2 for ≥70%; 1 for 30–<70%; 0 for <30%; otherwise mark missing. |

Score only if:

- Latest discharge is no more than three hours old at the supplied evaluation time.
- The baseline and valid 6-hour comparison exist.
- At least one weather component exists.

When exactly one weather component is missing, rescale earned points over the available maximum to 10, set confidence to `partial`, and display both coverage and the omission—for example, `7.5/10 · 8/10 points available · partial data`. Partial scores must not rank above complete scores solely because missing components were rescaled; sort complete scores first, then partial scores, then unavailable states.

If both weather components are missing, return a null score and `insufficient_data`. Stale hydro produces a null score and `stale`, while still showing the last measurement and its time. Round only the final score to one decimal. Recompute after data revisions and preserve the rules version.

Show beside every score:

> Experimental conditions score based on nearby weather and river flow; actual fishing conditions and local rules may differ.

Link to the source data and current official fishing regulations.

## Post-MVP score experiment

Keep `v1.0.0` as the primary dashboard score while running `v1.1.0-shadow` beside it in a clearly labeled Score Lab. This makes the change reviewable without silently changing the meaning of existing station rankings.

The candidate uses three components:

| Component | Maximum | Candidate rule |
| --- | ---: | --- |
| Season-matched flow percentile | 4 | Compare current discharge with prior-year daily discharge within ±7 calendar days. Require at least 21 values across three years. Award 4 points for the 25th–75th percentile inclusive, 2 for the 10th–<25th or >75th–90th percentile, and 0 otherwise. |
| 6-hour flow stability | 2 | Award 2 points when absolute change is ≤10%, 1 when it is >10% and ≤25%, and 0 otherwise. |
| Measured water temperature | 4 | Award 4 points for 12–16°C inclusive, 2 for 6–<12°C or >16–18°C, and 0 otherwise. Require a reading no more than three hours old. |

When measured water temperature is absent or stale, return a partial score over the six available points and state the omission. Never substitute modeled air temperature. The temperature bands are candidate product assumptions, not validated biological thresholds. WSC notes that non-flow/level outputs lack standardized quality assurance, so retain timestamps and qualifiers and avoid implying cross-station equivalence.

The comparison endpoint and UI must say that a different score is not proof of greater accuracy. Empirical validation would require consented, effort-normalized catch outcomes and should include zero-catch trips; Riverwise does not collect those records in this iteration.

## API contract

- `GET /health`: process and database diagnostics. Do not expose secrets or internal connection details.
- `GET /api/v1/stations`: every configured station, coordinates, latest flow with unit/time, score/status/confidence, coverage, and summary reasons. Include stations with missing data.
- `GET /api/v1/stations/{id}`: metadata, recent hydro/weather, baseline, trends with windows/units, score components, data ages, provenance, and the shadow candidate comparison fields.
- `GET /api/v1/stations/{id}/history?hours=48`: ordered observed discharge and optional level, timestamps, and qualifiers. Bound hours to 1–168.
- `GET /api/v1/scores/compare`: both rule versions plus the measured-temperature and seasonal-history context for every configured station.

Unknown station → 404. Known station without usable data → 200 with explicit nulls/status. For an invalid query, use FastAPI’s standard `422` validation response unless a deliberate compatibility layer changes it to `400`; document the selected contract in OpenAPI and tests.

Specify JSON types and examples in OpenAPI before connecting the UI. Read from PostgreSQL; do not call providers during web requests. Restrict CORS to configured origins.

## User interface

Home: accessible station list sorted by data completeness and score, source links, and last observation timestamps. Add map pins as optional polish after the list and detail experience is complete.

Station detail: score/status with reasons and coverage; actual reading time; 48-hour discharge chart with visible gaps; baseline/trends; nearby weather; and source notes.

Provide loading, error, empty, stale, partial, and insufficient-history states. Support keyboard navigation, text status in addition to color, sufficient contrast, and labels that do not require hover. Label each value accurately as measured hydrometric data, nearby modeled/historical weather, or forecast. All core information must work on a narrow viewport without the map.

## Operations and diagnostics

- Emit structured logs with run ID, provider, station ID when applicable, outcome, duration, and fetched/upserted counts. Do not log secrets or entire provider payloads.
- Expose last attempted and last successful ingestion per provider, plus the latest observation time per station.
- Provide a local diagnostic command that checks configuration, database connectivity, seed data, and fixture parsing.
- Keep ingestion retry counts and timeouts bounded and configurable.
- Preserve enough metadata to diagnose a revised observation without keeping unrestricted raw provider data indefinitely.

## Repository quality

- CI runs formatting checks, linting, static type checks, migrations against a clean database, unit tests, fixture-based integration tests, and the vertical-slice smoke test.
- Pin or constrain dependency versions and use committed lockfiles.
- Include `.env.example` without secrets.
- Record important choices in short architecture decision records, including score rescaling/ranking, weather classification, and deployment selection.
- Document the origin and permitted use of committed fixtures.
- Keep test fixtures small and redact anything not required for deterministic tests.

## Delivery phases and acceptance

### 1. Source discovery

Verify one gauge with recent discharge, capture CSV/JSON fixtures, and confirm field names, date conventions, units, qualifiers, weather semantics, and data-use terms. Record findings and deviations in the README.

**Exit criterion:** the selected source responses can be parsed deterministically from offline fixtures and the station’s identity is traceable to an official source.

### 2. One-station vertical slice

Implement the database migration, one station seed, discharge import, idempotent upsert, ingest-run record, API read path, and minimal responsive station page.

**Exit criterion:** a smoke test moves fixture data through persistence and the API into a rendered page with correct value, unit, source, timestamp, and freshness.

### 3. Reliable local data pipeline

Add real-network ingestion, bounded history backfill, revisions, failure isolation, diagnostics, and the remaining two verified stations. Substitute another verified gauge if Margaree lacks usable data and document the choice.

**Exit criterion:** tests cover duplicate runs, upstream revisions, missing data, invalid content, and independent provider failure.

### 4. Scoring and API completion

Implement the versioned pure scoring function and complete the list/detail/history contracts.

**Exit criterion:** tests cover every threshold boundary, large falls, zero denominators, insufficient history, stale flow, missing weather, partial-score coverage, time tolerances, gaps, and deterministic recomputation using an injected evaluation time.

### 5. Frontend completion

Connect the UI to the actual API and add the 48-hour chart. Verify list/detail/chart behavior and honest unavailable states on a narrow viewport and with keyboard-only navigation. Add the map last if time allows.

**Exit criterion:** no core information depends on the map, color, hover, or a wide viewport.

### 6. Handoff and deployment

Add a README with Docker Compose quick start, `.env.example`, migrations, seed/import commands, data attribution, architecture diagram, architecture decisions, and an end-to-end smoke check. Add CI. Deploy only after local v1 is complete, then record actual hosting cost and measured behavior.

**Exit criterion:** a new developer can clone the repository, run it locally, load fixtures without network access, optionally ingest real data with network access, and see accurate timestamps plus either an explainable score or an explicit unavailable state.

## Portfolio evidence to capture

Record real measurements during development rather than inventing claims:

- Number of verified stations and observations processed.
- Test counts and important failure scenarios covered.
- Ingestion duration, revision behavior, and any measured reliability period.
- API response times under a documented local or deployed test setup.
- Accessibility audit results and narrow-viewport checks.
- Actual monthly hosting cost after deployment.

Use these measurements in the README and résumé only with their testing context.

## Later enhancements

- Expand verified station coverage.
- Add alerts and favourites.
- Evaluate whether the shadow season-matched percentile should replace the production baseline after a documented observation period.
- Add a clearly labeled future-weather panel.
- Explore empirical modeling only with consented, sufficient catch records and meaningful validation.

## Implementation principles

Build in phase order. Keep the first complete data → API → UI slice small. Preserve exact source timestamps, distinguish weather from water measurements, and avoid fabricated data, fish-science claims, production-performance claims, or speculative cloud infrastructure.
