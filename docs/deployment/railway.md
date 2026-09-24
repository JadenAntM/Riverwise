# Railway deployment runbook

This runbook deploys Riverwise as four Railway services: PostgreSQL, the FastAPI API, the Next.js web app, and a one-shot hourly ingestion job. It deliberately keeps the repository root as the Docker build context because both application images copy files from more than one top-level directory.

## Before connecting GitHub

- Merge the tested Railway compatibility pull request to `main`.
- Confirm the Railway project contains a PostgreSQL service named `Postgres` (or substitute its actual service name in reference variables).
- Configure a usage alert and a hard spending limit in Railway before starting application services.
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
3. Open its backup settings and enable the best available schedule for the selected plan. Record the schedule in the deployment ADR after confirming it in the UI.
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

## 4. Add hourly ingestion

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
   10 * * * *
   ```

Railway evaluates cron schedules in UTC and can start them a few minutes late. This command performs one ingestion and exits; do not run `scheduler.py` as the Railway start command. If a previous execution is still active at the next scheduled time, Railway skips the overlapping run.

## 5. Verify the deployment

Manually run `ingest-hourly` once, then verify:

- The job exits successfully rather than remaining active.
- `API_URL/health` reports a healthy database and a current ingestion timestamp.
- `WEB_URL/status` lists all six stations.
- The run produces twelve current score snapshots: six stations times two score versions.
- Provider failures, if present, are isolated and visible rather than erasing prior observations.

Then test independence from the development computer:

1. Record the latest ingestion time on `/status`.
2. Stop the local Docker Compose services and leave the computer off or asleep for at least two scheduled cycles.
3. Reopen the public status page and confirm the latest ingestion time advanced by at least two hours.
4. Confirm the corresponding scheduled runs succeeded in Railway's deployment history.
5. Add the dated evidence to the ADR; do not claim cloud independence until this check passes.

## 6. Portfolio and operations follow-up

- Add `WEB_URL` to the GitHub repository description, README, résumé project entry, and portfolio.
- Record the deployed commit SHA, date, URLs, backup schedule, alert threshold, hard limit, and independence-test evidence in the ADR.
- After seven days, record measured Railway usage and projected monthly cost. Do not describe trial credit as a permanent hosting cost.
- Before the trial ends, decide whether to move to the paid plan or pause the deployment. Confirm the selected plan still supports all four services and cron jobs.

## Rollback

For an application regression, open the affected Railway service's deployment history and redeploy the last known-good commit. For a schema or data incident, stop `ingest-hourly` first, preserve logs, and assess database restoration before redeploying application code. Never assume an application rollback reverses a database migration or provider data revision.

