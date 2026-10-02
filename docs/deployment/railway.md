# Railway deployment runbook

This runbook deploys Riverwise as four Railway services: PostgreSQL, the FastAPI API, the Next.js web app, and a one-shot ingestion job that runs every 30 minutes. It deliberately keeps the repository root as the Docker build context because both application images copy files from more than one top-level directory.

## Before connecting GitHub

- Merge the tested Railway compatibility pull request to `main`.
- Confirm the Railway project contains a PostgreSQL service named `Postgres` (or substitute its actual service name in reference variables).
- On the current free/trial plan, record usage and review it regularly; the owner reports no spending-cap setting is available and accepts proceeding without one. Revisit alerts and limits before a paid-plan change.
- Keep database public networking disabled. Riverwise uses Railway's private `DATABASE_URL` reference.

Connecting a GitHub source can create a deployment. Do not connect any Riverwise service until the compatibility changes are on `main`.

## Why the branch and Dockerfile fields were missing

An empty service has no source. Open the service, select **Settings → Service Source → Connect Repo**, and choose `JadenAntM/Riverwise`. The source branch setting appears after a repository is connected.

Railway's supported custom-Dockerfile setting is a service variable rather than a field that is always visible:

```text
RAILWAY_DOCKERFILE_PATH=/apps/api/Dockerfile
```

Leave **Root Directory** blank for all Riverwise services. Setting it to `/apps/api` or `/apps/web` would make files needed by the Docker builds unavailable.

## 1. Configure PostgreSQL

1. Name the database service `Postgres` if it has another temporary name.
2. Leave public networking disabled.
3. Open its Backups tab and record whether a native schedule is available on the selected plan. If it is available, enable the best suitable schedule and record its retention in the deployment ADR. Use the independent [logical export and restore procedure](postgres-backups.md) in either case.
4. Do not copy database credentials into source control or this document.

## 2. Deploy the API

Create or open an empty service named `api`.

1. Add these variables before connecting the repository:

   ```text
   RAILWAY_DOCKERFILE_PATH=/apps/api/Dockerfile
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   API_CORS_ORIGINS=https://temporary.example
   PORT=8000
   ```

   Use Railway's reference-variable picker for `DATABASE_URL`; change `Postgres` if the database service has a different name.

2. In **Settings → Service Source**, connect `JadenAntM/Riverwise` and select `main` as the deployment branch.
3. Leave **Root Directory** blank.
4. Set the health-check path to `/health`.
5. Enable **Wait for CI** for GitHub autodeploys if it is available on the account.
6. Review and deploy the staged changes.
7. Under networking, generate a public domain and record it as `API_URL` below.
8. Open `API_URL/health`. Do not continue until it reports a healthy database connection.

```text
API_URL=________________________________________
```

## 3. Deploy the web app

Create an empty service named `web`.

1. Add these variables before connecting the repository:

   ```text
   RAILWAY_DOCKERFILE_PATH=/apps/web/Dockerfile
   NEXT_PUBLIC_API_URL=https://replace-with-api-domain.up.railway.app
   PORT=3000
   ```

2. Replace `NEXT_PUBLIC_API_URL` with the API domain from the previous section. Do not include a trailing slash.
3. Connect `JadenAntM/Riverwise`, select `main`, leave **Root Directory** blank, and enable **Wait for CI** if available.
4. Review and deploy the staged changes.
5. Generate a public domain and open it. This is the initial portfolio URL.

`NEXT_PUBLIC_API_URL` is embedded into the browser bundle during the image build. Changing it requires a web redeploy.

```text
WEB_URL=________________________________________
```

Return to the `api` variables, set `API_CORS_ORIGINS` to the exact `WEB_URL`, and redeploy the API. Then confirm the public web app can load its station data.

## 4. Add 30-minute ingestion

Create an empty service named `ingest-hourly`. It must not have a public domain.

1. Add:

   ```text
   RAILWAY_DOCKERFILE_PATH=/apps/api/Dockerfile
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```

2. Connect `JadenAntM/Riverwise`, select `main`, leave **Root Directory** blank, and enable **Wait for CI** if available.
3. Override the start command:

   ```text
   python /workspace/jobs/ingest/ingest.py --source live
   ```

4. Set the cron schedule to:

   ```text
   */30 * * * *
   ```

Railway evaluates cron schedules in UTC and can start them a few minutes late. This command performs one ingestion and exits; do not run `scheduler.py` as the Railway start command. If a previous execution is still active at the next scheduled time, Railway skips the overlapping run.

## 5. Verify the deployment

Manually run `ingest-hourly` once, then verify:

- The job exits successfully rather than remaining active.
- `API_URL/health` reports a healthy database and a current ingestion timestamp.
- `WEB_URL/status` lists all six stations.
- The run produces eighteen current score snapshots: six stations times three score versions, with `v1.0.0` still the dashboard score.
- Provider failures, if present, are isolated and visible rather than erasing prior observations.

Then test independence from the development computer:

1. Record the latest ingestion time on `/status`.
2. Stop the local Docker Compose services and leave the computer off or asleep for at least two scheduled cycles.
3. Reopen the public status page and confirm the latest ingestion time advanced by at least two hours.
4. Confirm the corresponding scheduled runs succeeded in Railway's deployment history.
5. Add the dated evidence to the ADR; do not claim cloud independence until this check passes.

## 6. Portfolio and operations follow-up

- Add `WEB_URL` to the GitHub repository description, README, résumé project entry, and portfolio.
- Record the deployed commit SHA, date, URLs, backup/restore status, current cost-control availability, and independence-test evidence in the ADR.
- After seven days, record measured Railway usage and projected monthly cost. Do not describe trial credit as a permanent hosting cost.
- Before the trial ends, decide whether to move to the paid plan or pause the deployment. Confirm the selected plan still supports all four services and cron jobs.

The [PostgreSQL backup runbook](postgres-backups.md) describes the temporary manual export and local restore drill. Keep the dated restore evidence in ADR 0005. Count seven consecutive days from the first stored production snapshot, and distinguish source-attempt success from availability of the public web and API services.

## Phase 2 operator alert rollout

The API's `/api/v1/operational-health` returns HTTP 503 for current discharge staleness, three consecutive station/source failures, or an import overdue by 90 minutes. `/api/v1/ingestion` and `/status` explain the same findings. These are data-operation checks; `/health` remains a process/database check. The scheduled job opens and resolves deduplicated alerts in PostgreSQL. It posts opening and six-hour reminder events only when `OPERATOR_ALERT_WEBHOOK_URL` points to an HTTPS endpoint that accepts Riverwise's JSON body. Set the variable only on the scheduled-ingestion service, keep the URL out of source control, and test delivery with a controlled local or non-production failure before relying on it. With no URL, findings appear in logs and the status page but no external notification is sent.

Monitor `/api/v1/operational-health` from outside Railway if continuous scheduler-stoppage detection is required: a stopped scheduled job cannot send its own webhook. The endpoint accepts GET and HEAD with the same HTTP status because free UptimeRobot HTTP checks use HEAD and selecting GET requires a paid plan. Document the monitor interval, destination, test result, and any actual incidents before claiming alerting is operational. Apply migrations 0004–0006 before deploying the new API or ingestion image; an old application version may not understand new alert-state data, so verify a rollback path. The 2026-10-02 rollout evidence is in ADR 0007.

## Rollback

For an application regression, open the affected Railway service's deployment history and redeploy the last known-good commit. For a schema or data incident, stop `ingest-hourly` first, preserve logs, and assess database restoration before redeploying application code. Never assume an application rollback reverses a database migration or provider data revision.
