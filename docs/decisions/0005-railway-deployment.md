# ADR 0005: Deploy the Riverwise data product on Railway

## Status

Accepted; production verification is pending.

## Context

Riverwise needs hosted PostgreSQL, two containerized applications, hourly ingestion that continues when the developer computer is off, HTTPS portfolio URLs, logs, and cost controls. The existing repository is a monorepo whose images require the repository root as their Docker build context. Deployment claims must be based on observed operation and cost rather than assumptions.

## Decision

Use one Railway project with four services:

- A private managed PostgreSQL database.
- A persistent FastAPI service built from `/apps/api/Dockerfile`.
- A persistent Next.js service built from `/apps/web/Dockerfile`.
- A scheduled service built from the API image that runs `python /workspace/jobs/ingest/ingest.py --source live` at `10 * * * *` UTC and exits.

Use Railway reference variables for the private database URL, public HTTPS domains for the API and web app, an exact web-origin CORS allowlist, and GitHub `main` autodeploys that wait for CI when the feature is available. Keep the local Docker Compose scheduler for local development; Railway cron replaces it only in the hosted environment.

Configure a usage alert and hard spending limit before application deployment. Enable the best PostgreSQL backup schedule available on the selected plan. Measure usage for seven days before recording a projected monthly cost.

## Alternatives considered

- **AWS or Azure:** both provide suitable primitives, but require more infrastructure, identity, networking, scheduling, and billing configuration than this portfolio-sized service currently justifies. They remain options if Riverwise later needs cloud-specific experience or greater control.
- **Vercel plus a separate API, database, and scheduler provider:** strong for the Next.js frontend, but spreads operations and billing across multiple platforms.
- **Render:** a credible integrated alternative, but Railway was selected for its straightforward multi-service project, private reference variables, Docker builds, managed PostgreSQL, cron jobs, and generated domains.
- **Always-on Python scheduler:** functionally similar to local Compose, but consumes resources continuously and creates an additional long-running process to monitor.

## Consequences

The deployment stays close to the locally verified containers and has one operational surface. The hourly process consumes resources only while ingesting. Railway becomes a platform dependency, cron timing is not exact, and overlapping runs are skipped if a prior job does not terminate. The web API URL is a build-time variable, so URL changes require a frontend rebuild. Application rollback does not automatically reverse database changes.

## Production evidence

Complete these fields only after observing the deployed system:

```text
Deployment date:
Deployed commit:
Public web URL:
Public API URL:
Budget alert:
Hard spending limit:
Backup schedule and restoration limits:
Seven-day measured usage:
Projected monthly cost:
Computer-off ingestion test date and result:
Last known-good rollback deployment:
```

The operational procedure and verification checklist are in [`docs/deployment/railway.md`](../deployment/railway.md).

