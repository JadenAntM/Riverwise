# ADR 0005: Deploy the Riverwise data product on Railway

## Status

Accepted; production observation is in progress. The seven-day reliability criterion has not yet elapsed.

## Context

Riverwise needs hosted PostgreSQL, two containerized applications, recurring ingestion that continues when the developer computer is off, HTTPS portfolio URLs, logs, and cost controls. The existing repository is a monorepo whose images require the repository root as their Docker build context. Deployment claims must be based on observed operation and cost rather than assumptions.

## Decision

Use one Railway project with four services:

- A private managed PostgreSQL database.
- A persistent FastAPI service built from `/apps/api/Dockerfile`.
- A persistent Next.js service built from `/apps/web/Dockerfile`.
- A scheduled service built from the API image that runs `python /workspace/jobs/ingest/ingest.py --source live` at `*/30 * * * *` UTC and exits. The 30-minute polling cadence reduces the delay between a newly published WSC observation and Riverwise's next successful import without implying that WSC publishes every 30 minutes.

Use Railway reference variables for the private database URL, public HTTPS domains for the API and web app, an exact web-origin CORS allowlist, and GitHub `main` autodeploys that wait for CI when the feature is available. Keep the local Docker Compose scheduler for local development; Railway cron replaces it only in the hosted environment.

Configure a usage alert and hard spending limit before application deployment. Enable the best PostgreSQL backup schedule available on the selected plan. Measure usage for seven days before recording a projected monthly cost.

## Alternatives considered

- **AWS or Azure:** both provide suitable primitives, but require more infrastructure, identity, networking, scheduling, and billing configuration than this portfolio-sized service currently justifies. They remain options if Riverwise later needs cloud-specific experience or greater control.
- **Vercel plus a separate API, database, and scheduler provider:** strong for the Next.js frontend, but spreads operations and billing across multiple platforms.
- **Render:** a credible integrated alternative, but Railway was selected for its straightforward multi-service project, private reference variables, Docker builds, managed PostgreSQL, cron jobs, and generated domains.
- **Always-on Python scheduler:** functionally similar to local Compose, but consumes resources continuously and creates an additional long-running process to monitor.

## Consequences

The deployment stays close to the locally verified containers and has one operational surface. The scheduled process consumes resources only while ingesting. Railway becomes a platform dependency, cron timing is not exact, and overlapping runs are skipped if a prior job does not terminate. The web API URL is a build-time variable, so URL changes require a frontend rebuild. Application rollback does not automatically reverse database changes.

## Production evidence as of 2026-09-29 22:31 UTC

- First hosted import: 2026-09-24, according to the deployment record. The first stored score snapshot visible through the public API is at 2026-09-24 15:05:42 UTC. The 72-hour point was 2026-09-27 15:05:42 UTC; the seven-day point will be 2026-10-01 15:05:42 UTC.
- Railway reported successful web, API, and scheduled-ingestion deployments of `f9f309b2d4d9b537aee777ad0490f2dd2a8a6201`. This release includes the status-API last-success fix tracked in [GitHub issue #1](https://github.com/JadenAntM/Riverwise/issues/1) and the Phase 2 shadow model. The >250-failure edge case has not been induced in production.
- Public web URL: <https://web-production-4762c.up.railway.app>. Public API URL: <https://api-production-f376.up.railway.app>.
- Public `/api/v1/ingestion` at 2026-09-29 21:36 UTC showed a latest successful WSC and Open-Meteo import for every station at about 21:31 UTC. All six discharge ages were 26–76 minutes, below the three-hour stale threshold. The latest source states were all successful.
- Public `/api/v1/reliability?days=7` at the same check contained 3,778 successful provider/station attempts out of 3,786 recorded attempts (99.8%). Eight individual failures were recorded: five WSC attempts for `01FB003`, two Open-Meteo attempts for `01ED005`, and one Open-Meteo attempt for `01EO001`. Other imports continued. This seven-day query currently contains only the available production history, not a completed seven-day observation window.
- Every station had 312 stored candidate snapshots and 1,962–2,011 recent discharge observations. A spot check of `01FB001` score history found 312 evaluation times and 624 snapshots across both versions from 2026-09-24 15:05:42 to 2026-09-29 21:31 UTC. The largest gap between successive `v1.0.0` snapshots for this station was 1,968 seconds (32 minutes 48 seconds). These are ingestion and data coverage checks, not proof of public site uptime.
- Railway CLI showed $0.59 of resource usage so far in the 2026-09-23 23:03 to 2026-09-29 23:59 UTC billing period for the linked project, `chic-magic`, which is the only project in the workspace. This is an interim resource-usage figure, not an actual seven-day cost or a paid-plan bill. The CLI reported no workspace usage limit; the budget alert and hard-limit settings still need confirmation in Railway.
- A Railway query of web and API HTTP logs for `500..599` responses returned no entries in the available seven-day log window on 2026-09-29. This is not a continuous uptime measurement. A review also found a status-API edge case: after more than 250 failed source runs, it could lose the recorded last successful update. [GitHub issue #1](https://github.com/JadenAntM/Riverwise/issues/1) tracks that production bug; a tested fix is deployed but the production edge case has not been induced.
- The first Phase 2 production ingestion at 22:31 UTC completed all 12 station-source imports and wrote 18 versioned score snapshots. Successful structured events appeared with Railway's error label because Python logging wrote to stderr. [GitHub issue #2](https://github.com/JadenAntM/Riverwise/issues/2) tracks this logging bug; commit `23b66555c1d1e34df0e70cee5e588046dfe1d0c8` routes successes to stdout and failures to stderr. Production log verification remains pending the next scheduled run.
- The user reported that ingestion continued while their Mac was off. The exact before/after timestamps and Railway run IDs have not yet been recorded, so the dated independence check in the deployment runbook remains open.
- On 2026-09-29, the user confirmed that the Postgres Backups tab requires Railway Pro for native backups on the current Trial plan. No native backup schedule is enabled. Railway's [backup guide](https://docs.railway.com/volumes/backups) describes native schedules; the [manual logical export procedure](../deployment/postgres-backups.md) is the current independently restorable strategy. Recheck the entitlement after any plan change.
- On 2026-09-29, a custom-format production dump was restored into a separate local PostgreSQL database. `pg_restore` completed in about 0.312 seconds. The restored database contained 6 stations, 56,292 hydro observations, 1,878 weather hours, 3,732 score snapshots, and 3,774 ingestion runs. Its latest observation was 2026-09-29 20:40 UTC; latest score snapshot was 2026-09-29 21:02:32 UTC. The 778 KB dump's SHA-256 checksum and archive listing were verified; the temporary database was removed. The dump is currently a local copy, and a second copy on separate encrypted storage remains to be made.
- Railway CLI currently reports that the web service is built with Railpack (`npm run build --workspace=@riverwise/web`), even though the original decision and deployment runbook specify `apps/web/Dockerfile`. The API and scheduled import retain Docker builds. This deployment deviation does not change the product stack, but the actual web build path should be rechecked before claiming Dockerfile parity.

Still to record after 2026-10-01 15:05 UTC: a completed seven-day provider/station window, actual public service uptime evidence, failures and data coverage for that window, measured seven-day Railway usage, projected monthly cost with the selected plan's minimum, computer-off timestamps, and a last known-good rollback deployment. The operational procedure is in [`docs/deployment/railway.md`](../deployment/railway.md). Provider failures alone are not application bugs; file GitHub issues for confirmed production defects.
