# Riverwise

Riverwise is a mobile-friendly Nova Scotia river-conditions dashboard. The MVP combines measured Water Survey of Canada discharge with nearby Open-Meteo model weather and a transparent experimental conditions score.

The score is not a prediction of catches, river safety, fish abundance, habitat quality, or legal fishing eligibility.

## Current status

The first complete vertical slice now runs across three verified Water Survey of Canada gauges:

- `01FB001` — **NORTHEAST MARGAREE RIVER AT MARGAREE VALLEY**
- `01FB003` — **SOUTHWEST MARGAREE RIVER NEAR UPPER MARGAREE**
- `01FC002` — **CHETICAMP RIVER ABOVE ROBERT BROOK**

On 2026-09-23, all three official recent-data feeds returned current parameter 47 discharge and completed a live ingestion run successfully.

Implemented:

- Versioned PostgreSQL schema and Alembic migration.
- Three verified editable station seeds.
- Typed WSC CSV and Open-Meteo parsing.
- Idempotent observation updates, including revised upstream values.
- Offline fixture import and live provider import with bounded timeout/retries and independent failure recording.
- Pure versioned scoring with explicit evaluation time.
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

Open [http://localhost:3000](http://localhost:3000). Ingestion status is at [http://localhost:3000/status](http://localhost:3000/status), and API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

The scheduler performs a live import when it starts and then at 10 minutes past each hour. It needs internet access, and scheduling pauses when Docker Desktop or the computer is stopped or asleep. No provider API keys or accounts are required.

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
- `GET /api/v1/stations/{id}`
- `GET /api/v1/stations/{id}/history?hours=48` (`1–168`; invalid values return FastAPI’s documented `422` validation response)

Known stations without usable data return `200` with explicit null/status fields. Unknown stations return `404`.

## Source discoveries

Water Survey of Canada’s official real-time CSV endpoint uses:

- `ID`
- `Date` in UTC ISO-8601 form
- `Parameter/Paramètre` (`47` for unit-value discharge)
- `Value/Valeur`
- qualifier, symbol, approval, grade, and additional-qualifier columns

The primary committed WSC fixture is downsampled from the official five-minute response to keep it small; values and timestamps were not rewritten. A second small fixture pins verified rows for the two added gauges. The Open-Meteo fixture is a bounded portion of the model response for the original gauge coordinates. See [`tests/fixtures/README.md`](tests/fixtures/README.md) for provenance and limitations.

Official sources:

- [Water Survey of Canada web services](https://wateroffice.ec.gc.ca/services/)
- [Station 01FB001](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01FB001)
- [Station 01FB003](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01FB003)
- [Station 01FC002](https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01FC002)
- [Open-Meteo forecast API](https://open-meteo.com/en/docs)

## Scoring

Rules live in `apps/api/app/scoring.py` and are versioned as `v1.0.0`. The function accepts its evaluation time explicitly and returns score, status, confidence, coverage, components, and reasons. A score requires fresh discharge, a station-specific baseline, a valid six-hour comparison, and at least one non-forecast weather component.

See the architecture decisions in [`docs/decisions`](docs/decisions) and the full [`PROJECT_SPEC.md`](PROJECT_SPEC.md).

## Data and safety notes

- Hydrometric readings may be provisional, late, or revised.
- A gauge represents its location, not an entire river or access point.
- Nearby modeled air temperature is not water temperature.
- Missing values and gaps are preserved rather than interpolated for scoring.
- Consult official regulations and local safety information before fishing.
