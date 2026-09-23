# Riverwise

Riverwise is a mobile-friendly Nova Scotia river-conditions dashboard. The MVP combines measured Water Survey of Canada discharge with nearby Open-Meteo model weather and a transparent experimental conditions score.

The score is not a prediction of catches, river safety, fish abundance, habitat quality, or legal fishing eligibility.

## Current status

The complete local data product now runs across six verified Water Survey of Canada gauges:

- `01FB001` — **NORTHEAST MARGAREE RIVER AT MARGAREE VALLEY**
- `01FB003` — **SOUTHWEST MARGAREE RIVER NEAR UPPER MARGAREE**
- `01FC002` — **CHETICAMP RIVER ABOVE ROBERT BROOK**
- `01EO001` — **ST. MARYS RIVER AT STILLWATER**
- `01EF001` — **LAHAVE RIVER AT WEST NORTHFIELD**
- `01ED005` — **MERSEY RIVER BELOW GEORGE LAKE**

On 2026-09-23, all six official recent-data feeds returned current parameter 47 discharge and completed a live ingestion run successfully. The three province-wide additions also returned 3,388–3,478 daily observations in the bounded ten-year backfill.

Implemented:

- Versioned PostgreSQL schema and Alembic migration.
- Six verified editable station seeds spanning Cape Breton, eastern mainland Nova Scotia, and the South Shore.
- Typed WSC CSV and Open-Meteo parsing.
- Measured WSC water-temperature ingestion where a gauge reports parameter 5.
- A bounded WSC daily-flow backfill for season-matched station baselines.
- Idempotent observation updates, including revised upstream values.
- Offline fixture import and live provider import with bounded timeout/retries and independent failure recording.
- Pure versioned scoring with explicit evaluation time.
- A `v1.1.0-shadow` candidate score and side-by-side Score Lab; `v1.0.0` remains the dashboard score.
- Idempotent hourly snapshots for both score versions, including partial, stale, and unavailable states.
- Seven- and 30-day score-history charts on each station page.
- Measured reliability reporting for provider success, data freshness, temperature coverage, observation counts, historical depth, and changed provider values.
- Station list, detail, 48-hour history, and ingestion-status API endpoints.
- Responsive station list/detail interface with visible data gaps and provenance.
- Hourly ingestion scheduler with source- and station-level run monitoring.
- Accessible station map supplemented by an equivalent text station list.
- Automated backend boundary/integration tests, frontend lint/type/build checks, and CI.

## Architecture

```text
WSC CSV ─────────┐
                 ├─> Python ingestion ─> PostgreSQL ─> FastAPI ─> Next.js
Open-Meteo JSON ─┘          │                 │
                            └─ ingest runs    └─ versioned score inputs
```

Web requests read only from PostgreSQL. They never call external providers.

## Quick start with Docker

Requirements: Docker Desktop with Compose.

```bash
cp .env.example .env
docker compose up --build -d db api web scheduler
```

Open [http://localhost:3000](http://localhost:3000). The rule comparison is at [http://localhost:3000/score-lab](http://localhost:3000/score-lab), reliability and ingestion status are at [http://localhost:3000/status](http://localhost:3000/status), and API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

The scheduler performs a live import when it starts and then at 10 minutes past each hour. Real-time hydrometric and weather data are refreshed each cycle. Daily discharge history is imported once and refreshed at most every 20 hours. It needs internet access, and scheduling pauses when Docker Desktop or the computer is stopped or asleep. No provider API keys or accounts are required.

To run an additional live import manually:

```bash
docker compose --profile tools run --rm ingest python /workspace/jobs/ingest/ingest.py --source live
```

Provider failures are recorded independently, so one failure does not erase previously stored observations from another source or station. To load deterministic fixtures instead of live data:

```bash
docker compose --profile tools run --rm ingest
```

The fixtures preserve their source timestamps and will correctly appear stale after their 2026-09-23 observation window.

## Local development

### API and ingestion

```bash
python3 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.txt
cd apps/api
../../.venv/bin/alembic upgrade head
cd ../..
.venv/bin/python jobs/ingest/ingest.py --source fixtures --evaluation-time 2026-09-23T16:30:00Z
cd apps/api
../../.venv/bin/uvicorn app.main:app --reload
```

The default local database is SQLite for a lightweight development loop. Docker and CI exercise PostgreSQL, which is the intended application database.

### Web

```bash
npm install
npm run dev:web
```

The web app expects the API at `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` is set.

## Verification

```bash
cd apps/api
../../.venv/bin/ruff check . ../../jobs/ingest
../../.venv/bin/pytest -q
cd ../..
npm run verify
docker compose config --quiet
```

To check local configuration, fixture parsing, database connectivity, and station count after migration/import:

```bash
.venv/bin/python jobs/ingest/diagnose.py
```

## API

- `GET /health`
- `GET /api/v1/stations`
- `GET /api/v1/ingestion`
- `GET /api/v1/reliability?days=30` (`days` must be `7` or `30`)
- `GET /api/v1/scores/compare`
- `GET /api/v1/stations/{id}`
- `GET /api/v1/stations/{id}/score-history?days=7` (`days` must be `7` or `30`)
- `GET /api/v1/stations/{id}/history?hours=48` (`1–168`; invalid values return FastAPI’s documented `422` validation response)

Known stations without usable data return `200` with explicit null/status fields. Unknown stations return `404`.

## Source discoveries

Water Survey of Canada’s official real-time CSV endpoint uses:

- `ID`
- `Date` in UTC ISO-8601 form
- `Parameter/Paramètre` (`47` for unit-value discharge and `5` for water temperature where available)
- `Value/Valeur`
- qualifier, symbol, approval, grade, and additional-qualifier columns

The WSC daily endpoint supplies one discharge value per date and retains provider symbols such as estimated-value markers. Riverwise imports up to ten years for a season-matched baseline, then refreshes a 14-day overlap so revisions can be updated. WSC notes that outputs other than flow and level do not have standardized quality assurance, so measured water temperature is shown with its timestamp and availability rather than treated as universally comparable.

The primary committed WSC fixture is downsampled from the official five-minute response to keep it small; values and timestamps were not rewritten. Additional small fixtures pin verified rows for the added gauges, measured temperature, and daily history. The Open-Meteo fixture is a bounded portion of the model response for the original gauge coordinates. See [`tests/fixtures/README.md`](tests/fixtures/README.md) for provenance and limitations.

Official sources:

- [Water Survey of Canada web services](https://wateroffice.ec.gc.ca/services/)
- [Station 01FB001](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01FB001)
- [Station 01FB003](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01FB003)
- [Station 01FC002](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01FC002)
- [Station 01EO001](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01EO001)
- [Station 01EF001](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01EF001)
- [Station 01ED005](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01ED005)
- [Open-Meteo forecast API](https://open-meteo.com/en/docs)

## Scoring

Rules live in `apps/api/app/scoring.py`. The production dashboard still uses `v1.0.0`: recent flow relative to a 14-day median, six-hour change, nearby modeled precipitation, and nearby modeled cloud cover.

The Score Lab also runs `v1.1.0-shadow`. It replaces recent flow with a percentile against prior years within ±7 calendar days, scores absolute six-hour stability, and uses measured water temperature when available. A seasonal baseline requires at least 21 daily values across at least three previous years. Missing water temperature produces a visibly partial score rather than substituting nearby air temperature. This candidate is an inspectable hypothesis, not evidence of better catch prediction.

See the architecture decisions in [`docs/decisions`](docs/decisions) and the full [`PROJECT_SPEC.md`](PROJECT_SPEC.md).

## Data and safety notes

- Hydrometric readings may be provisional, late, or revised.
- A gauge represents its location, not an entire river or access point.
- Nearby modeled air temperature is not water temperature.
- Missing values and gaps are preserved rather than interpolated for scoring.
- Provider revision counters record source-field changes detected after this feature was enabled; they are not reconstructed retroactively.
- Consult official regulations and local safety information before fishing.
