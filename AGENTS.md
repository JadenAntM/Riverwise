# Riverwise project context

## Purpose

Riverwise is a portfolio-quality, mobile-friendly dashboard for exploring Nova Scotia river conditions relevant to brook trout anglers. It combines measured Water Survey of Canada hydrometric observations with nearby Open-Meteo weather and an explicitly experimental, explainable conditions score.

The canonical product and implementation plan is [`PROJECT_SPEC.md`](./PROJECT_SPEC.md). Read it before planning or implementing project work. If code and the specification disagree, flag the discrepancy rather than silently changing product meaning.

## Current status

The six-station reliability milestone is complete for verified WSC stations `01FB001`, `01FB003`, `01FC002`, `01EO001`, `01EF001`, and `01ED005`. The project includes migrations, fixture and live ingestion paths, idempotent updates, scoring, read APIs, a responsive station index/detail interface, discharge and score-history charts, an accessible station map with a text equivalent, source/station ingestion monitoring, measured reliability metrics, tests, Docker Compose, CI, and documentation. A post-MVP experiment also ingests season-matched daily discharge history and measured water temperature where WSC reports it, then compares `v1.0.0` with a non-production `v1.1.0-shadow` score in the Score Lab.

The Docker `scheduler` imports live WSC and Open-Meteo data immediately on startup and then hourly at 10 minutes past the hour. `/api/v1/ingestion` and `/status` expose the latest per-station source runs, score snapshots, reliability metrics, and observation freshness. The latest verified live cycle on 2026-09-23 completed current WSC and Open-Meteo ingestion successfully for all six stations.

Hourly ingestion now persists both rule versions, including unavailable states. `/api/v1/reliability`, `/api/v1/stations/{id}/score-history`, `/status`, and station details expose seven- and 30-day measured history. Revision tracking is prospective from its rollout and is not retroactive. The next reliability task is to let these records accumulate and document a real observation window; do not claim improved accuracy without outcome data. A private trip log was explicitly excluded from this iteration. Device-local favourites are still an available next product decision. Alerts remain later because they require choices about identity, notification channel, thresholds, consent, cost, and delivery infrastructure.

## Non-negotiable product rules

- Call the output an **experimental conditions score**, never a bite probability or catch prediction.
- Do not imply safety, fish abundance, habitat quality, or legal fishing eligibility.
- Never invent station IDs, readings, timestamps, performance results, scientific validation, or hosting costs.
- Preserve source timestamps, units, qualifiers, revisions, provenance, and gaps.
- Distinguish measured hydrometric data, modeled/historical weather, and forecasts. Never use future forecasts in a current score.
- Show explicit stale, missing, partial, and insufficient-data states.
- Keep all core information accessible on mobile and without a map, color, or hover.
- Store times in UTC and display Atlantic time with an explicit timezone.

## Planned stack

- Web: Next.js, TypeScript, Recharts, and Leaflet.
- API: FastAPI with documented OpenAPI contracts.
- Ingestion: Python with typed parsing, timeouts, bounded retries, and idempotent upserts.
- Storage: PostgreSQL with migrations.
- Local environment: Docker Compose.

Do not change the stack or introduce cloud infrastructure without documenting the reason and tradeoffs. Deployment follows a complete local v1.

## Working conventions

- Work in the delivery-phase order in `PROJECT_SPEC.md` unless a discovered dependency requires a documented deviation.
- Keep network access out of normal unit tests. Commit small, legally usable fixtures covering valid, missing, qualified, and revised data.
- Keep scoring pure, deterministic, versioned, and supplied with an explicit evaluation time.
- Add or update tests with behavior changes, especially around timestamps, threshold boundaries, missing data, and revisions.
- Use migrations for database changes and update OpenAPI plus consumers when contracts change.
- Keep secrets out of source control and logs; update `.env.example` when configuration changes.
- Prefer the smallest complete vertical slice over parallel layers that cannot yet work end to end.

## Documentation and portfolio integrity

Record real source discoveries and deviations in the README. Capture measured test coverage, ingestion behavior, response times, accessibility results, and hosting cost only after they exist. Do not turn aspirations into résumé claims.

When a decision affects product meaning or data interpretation, create a short architecture decision record under `docs/decisions/`.
