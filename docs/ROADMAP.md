# Riverwise roadmap — from reliable conditions to trip planning

Planning baseline: 2026-09-29. This is the current execution plan, not a claim that future work is complete. [`PROJECT_SPEC.md`](../PROJECT_SPEC.md) remains the authority for product meaning, data provenance, accessibility, and the experimental-score guardrails. Architecture decisions document changes to those meanings before implementation.

## Product direction

Help a Nova Scotia angler decide **which river to check and when a trip might be practical**, using measured gauge data, nearby modeled weather, and clearly labeled forecasts. Riverwise is not a catch predictor, safety service, habitat assessment, access guide, or source of legal eligibility advice. A gauge represents its location, not an entire river.

Keep three distinct kinds of information in the interface and API:

1. **Observed:** WSC discharge and water temperature where actually reported, with measurement time, unit, qualifier, revision, and freshness.
2. **Modeled or forecast:** Open-Meteo weather near the gauge, with the valid time, retrieval time, provider issue/model-run time when available, source, and missing-data state. Future weather must never enter a current score.
3. **Experimental interpretation:** versioned score rules and, eventually, historical river-response comparisons. These are hypotheses or descriptive summaries, not claims about catches.

## Verified starting point and open evidence

- Six verified WSC gauges, Railway-hosted web/API/PostgreSQL, and scheduled ingestion are deployed. `v1.0.0` remains the dashboard score; `v1.1.0-shadow` and `v1.2.0-shadow` are visible in the Score Lab. New snapshots persist direct scoring inputs and point-level explanations. [ADR 0006](decisions/0006-v1-2-shadow-conditions-model.md) documents the v1.2 rollout and a **difference**, not accuracy, analysis.
- A manual production PostgreSQL export was restored into a separate local database. Native Railway backups require Pro on the current Trial plan. The [backup runbook](deployment/postgres-backups.md) exists; the owner accepts the current local-only recovery risk and defers an off-laptop copy until user data exists.
- Production ingestion began on 2026-09-24. The seven-day observation point is 2026-10-01 15:05 UTC; the full-window review, true public uptime evidence, actual seven-day cost, and dated computer-off evidence are not yet recorded. [ADR 0005](decisions/0005-railway-deployment.md) is the evidence log.
- On 2026-09-29, a production ingestion after the logging fix completed all 12 WSC/Open-Meteo station-source imports; Railway classified the successful structured events as `info`. This is one checked run, not a seven-day reliability claim. [Issue #1](https://github.com/JadenAntM/Riverwise/issues/1) and [issue #2](https://github.com/JadenAntM/Riverwise/issues/2) record discovered production defects and their follow-up.
- No effort-normalized angling outcomes, including zero-catch trips, are available. No score version has demonstrated greater fishing accuracy. Fresh WSC-measured water temperature was recently available at one of six gauges; do not fill other gauges with nearby air temperature.
- The current Open-Meteo import asks for one forecast day. The existing `weather_hours` key can retain the latest forecast for a valid hour, but cannot preserve multiple **as-issued** forecast versions for later forecast-error analysis. A seven-day planner needs an explicit data and retention decision.

## Sequence and release gates

| Order | Milestone | Release intent | Gate to move on |
| --- | --- | --- | --- |
| 1 | Close production reliability | v1.1 hardening | Complete and document seven consecutive days, backup recoverability, cost, and failure handling. |
| 2 | Strengthen data quality and operations | v1.1 follow-up | Detect missing, revised, and implausible data; alert on actionable ingestion failures or staleness. |
| 3 | Improve station discovery and interpretation | v1.3 | Users can find and understand a station on mobile, without relying on a map or color. |
| 4 | Add forecast-first trip planning | v1.4 | Users can compare the next 1–7 days without a future score or invented flow forecast. |
| 5 | Research historical rain-to-flow response | Conditional experiment | Backfilled paired data and out-of-time tests support a bounded, station-specific descriptive statement; otherwise do not ship it. |
| 6 | Add local personalization, then consider alerts | v1.5 | Favourites work without accounts; notification consent, privacy, and reliability are designed before email delivery. |

Engineering quality, accessibility, security, and portfolio evidence run through every milestone rather than being deferred to the end. **v2.0 is conditional**, not a calendar target: it requires a documented score evaluation against relevant outcomes and mature production reliability. A forecast planner alone does not make the conditions model validated.

Release labels in this table are product milestones, not score-rule versions. The `v1.1.0-shadow` and `v1.2.0-shadow` rule versions are already deployed for comparison while the v1.1 seven-day reliability evidence and v1.2 outcome validation remain open.

## 1. Close production reliability — v1.1 gate

1. After 2026-10-01 15:05 UTC, compute the actual seven-day window from stored ingestion attempts and snapshots: expected versus observed runs, station/provider success, gaps, revisions, score availability, and observation freshness. Distinguish ingestion success from public-site uptime.
2. Start a periodic external web/API health check and record its interval and failures. Existing HTTP logs alone cannot prove continuous uptime; if monitoring starts after the ingestion window, report the shorter measured uptime window and extend observation before claiming seven days of public uptime. Recheck `/status` for stale, partial, missing, and unavailable cases with reproducible test cases.
3. Record the 2026-09-29 23:01 UTC `info`-level ingestion run as production verification of the logging fix, then resolve issue #2. Keep issue #1 open until its >250-failure edge is sufficiently checked or explicitly close it as a tested fix with the production limitation noted. File an issue for each newly confirmed production defect.
4. Record Railway's measured seven-day resource usage, plan/minimum charges, and projected monthly cost separately. A spending cap is not a gate on the current free/trial plan; revisit cost controls before changing plans.
5. Continue manual exports and repeat a local restore drill periodically. The owner accepts the risk of a local-only copy until user data exists; revisit encrypted off-laptop storage before retaining user data and native backup entitlement if the Railway plan changes.
6. Record a dated computer-off or asleep interval and the Railway run IDs before and after it. Test a known-good rollback procedure without risking the only database copy.

**Done when:** the dated seven-day ingestion evidence, measured public uptime over its *actual* observation window, failures, costs, coverage, backup/restore results, and remaining exceptions are in ADR 0005 and the deployment runbook. Do not backfill or infer uptime for unmonitored days; extend the window if the strict seven-day public-uptime criterion is retained.

## 2. Data quality and operational foundation

At the owner's explicit request, this milestone started while Phase 1's continuous public-uptime evidence was still open; the two observation tracks are not conflated. On 2026-10-02, source validation, revision auditing, per-station gap and failure diagnoses, run IDs, and deduplicated alert detection were deployed; see [ADR 0007](decisions/0007-data-quality-and-operator-alerts.md). A separate external ingestion-health monitor is active and the owner received its test email. A real degradation-notification test and a measured post-deployment observation period remain open, so this is not yet a Phase 2 definition-of-done claim.

1. Define expected update cadence and acceptable observation age per station/source from actual history. Separate provider outage, delayed publication, genuinely absent measurement, and parser failure.
2. Test duplicate/revised upstream rows, qualifiers, impossible values, timestamp gaps, and idempotent retries. Show coverage and revision counts by station; retain enough provenance for diagnosis.
3. Add stable ingestion run IDs to structured logs and a small actionable alert for repeated failure or stale critical data. Alerting operators is separate from user fishing-condition notifications.
4. Measure query latency before adding indexes or retention rules. Add a protected diagnostics endpoint only if existing logs and public status cannot meet the operational need; do not expose internals publicly.
5. Add PostgreSQL-backed API/migration tests and staging or preview tests when the change risk justifies them. Run accessibility and browser journeys on the product paths touched by each release.

**Done when:** a failed provider, missing measurement, revision, and stale station are distinguishable in storage, API, logs, and UI; the team receives an actionable signal when ingestion stops meeting its documented target.

## 3. Make stations easier to find and understand — v1.3

1. Add station search, region filters, and sorting by freshness, completeness, and score with complete/partial states kept distinct. Avoid an unproven “best fishing” ranking.
2. Improve the station chart with measured discharge and separate nearby weather/rain history; explain units, source, qualifiers, gaps, and why a score is partial or stale.
3. Improve map status markers, legend, keyboard access, and the equivalent text list. Add useful shareable station metadata and test the flow on a real narrow-screen phone.
4. Add a small, clearly labeled future-weather preview as the bridge to trip planning; do not mix forecasts into the measured-history chart or current score.

**Done when:** a visitor can locate a station, understand the age and provenance of its data, and share its page without using a map, hover, or color interpretation.

## 4. Build a forecast-first Trip Planner — v1.4

**First release is a decision aid, not a saved-trip or river-flow prediction system.** A visitor chooses a station and a date within the next seven Atlantic calendar days, compares a few candidate days or stations, and sees forecast weather alongside the latest measured gauge conditions.

1. Write an ADR for forecast semantics, provider attribution/licensing, issue-time preservation, timezone/day boundaries, retention, and the explicit no-future-score boundary.
2. Extend ingestion and storage to request up to seven forecast days. Keep `retrieved_at_utc`, `valid_at_utc`, provider/model-run or `issued_at_utc` when available, and forecast-versus-observed classification; decide whether to retain as-issued versions or only the latest for the UI. Never silently rewrite a past forecast into an observation.
3. Build a read-only API for daily and useful hourly forecast rain amount/probability, air temperature, cloud cover, and sunrise/sunset where available. Handle missing hours and provider failure. Forecast precipitation near a gauge is not a watershed-wide measurement.
4. Build a mobile-first planner showing forecast retrieval time (and model issue time when available), source, Atlantic date/time, current measured flow and its age, and forecast lead time. Do not claim calibrated confidence without a backtest. Do not display a future conditions score, predicted discharge, catch likelihood, access claim, or safety recommendation.
5. Test UTC-to-Atlantic day boundaries and DST, a forecast revision, a missing forecast, stale measured flow, accessibility, and a narrow viewport. Instrument which planner views are used before adding accounts or notifications.

**Done when:** a visitor can compare 1–7 days at the six verified gauges, see exactly what is forecast versus measured, and use the experience when forecast or measured data are unavailable. No forecast value enters the current-score calculation.

## 5. Research historical rain-to-flow response — conditional

This is the user's “about 10 mm of rain on day two” idea. It is **not** a promise that 10 mm will produce a particular discharge or fishing outcome.

1. Backfill matching historical weather for the periods with WSC discharge. Document whether point weather at gauge coordinates is a defensible proxy for rainfall across each upstream watershed; if not, test a better geographically justified source or do not model that gauge.
2. Define rain events, 6/24/72-hour totals, starting flow, antecedent rain, season, and 6/24/48-hour downstream flow response. Account for snow/rain separation and gaps; never use later information to construct a forecast-time feature.
3. Evaluate by station and season using out-of-time holdouts. Report sample sizes, error and interval coverage against a simple baseline, missingness, and sensitivity to forecast lead time. Preserve forecast issue times if testing what a user could actually have known in advance.
4. Only if evidence is adequate, show a range of **historically observed** responses for genuinely comparable events, with sample count, time lag, source, and caveats. Suppress the insight when comparisons are sparse or unstable. Do not infer “good fishing” without relevant outcome data.

**Done when:** either a reproducible, well-calibrated descriptive comparison passes predeclared checks or a documented negative result explains why the feature is withheld. A negative result is a successful research outcome.

## 6. Personalization and notifications — v1.5 or later

Start with browser-local favourites, a favourites summary, and station ordering, then consider locally saved trip dates. Design condition thresholds and alert triggers only after data freshness and forecast revisions are trustworthy. Email alerts require explicit opt-in, deduplication, cooldowns, unsubscribe, visible delayed/incomplete-data states, privacy/retention decisions, and measured delivery reliability. Add accounts only if cross-device use warrants the added complexity.

## Continuous engineering and portfolio work

- CI should cover migrations, PostgreSQL integration, scoring boundaries, API contracts, and browser journeys. Add Axe checks, dependency/container scanning, Dependabot, public API rate limiting, and security-header/CORS review in proportion to risk.
- Record measured API latency and frontend performance before setting or claiming targets. Add error monitoring only when its signal and cost are justified. Introduce staging when production migrations or planner/alert changes make direct deployment risky. Automate exports only after the manual backup process is proven and secure.
- Maintain ADRs, a changelog, architecture diagram, screenshots/demo, real deployment/reliability evidence, and a dated production-failure case study. Create GitHub milestones, then prepare a portfolio/resume summary and interview explanation using only measured claims. Never turn provisional scoring or historical river response into an accuracy or catch-prediction claim.

## Immediate next actions

1. Close the seven-day reliability report at the actual observation point; verify cost, local backup/restore evidence, and any remaining production issues.
2. Write station/source completeness expectations and an actionable ingestion-failure alert—the minimum quality foundation for the next user-facing release.
3. Scope v1.3 station discovery and a small forecast preview, then write the Trip Planner ADR before changing forecast storage or UI.

The Phase 2 shadow model can continue collecting snapshots throughout this work. Pressure/daylight scoring and a production-score replacement remain research questions, not blockers for a forecast-only planner and not claims of improved accuracy.
