# Phase 3 release checklist

Prepared 2026-10-07. Status: **release preparation; production deployment is on hold**.

## Candidate and scope

The managed `codex/phase3-release` branch is based on `11ee7497b5b6de3ed8a246bec1ebe272b5365fb1`, the fetched main baseline. It contains station search/region/sort, written and keyboard map states, proportional discharge charts and source tables, station sharing/metadata, modeled precipitation history, and a separate bounded future-weather preview. The new weather read endpoint uses existing storage. There are **no database migrations, scoring changes, or ingestion changes** in this release. ADR 0008's precipitation-window discrepancy remains a separate versioned scoring decision.

The combined original working copy retains the Phase 4 Trip Planner, migration 0007, forecast storage, eight-day ingestion request, and forecast parser/API. Those changes are excluded from this candidate. The alert-drill helper is a manual fixture-only tool; application and scheduler entrypoints do not run it.

## Gates and evidence

| Gate | State | Evidence needed |
| --- | --- | --- |
| Phase 3 isolated and reviewed | Prepared | Candidate branch/PR and exact commit SHA; verify no planner, migration or ingestion diff |
| Fresh local verification | Passed 2026-10-07 | 111 backend tests passed, one PostgreSQL test skipped because Docker was stopped; Python lint, frontend lint/type/standalone build and 18 Chromium journeys passed |
| Fresh GitHub CI | Pending | All three jobs green on the final candidate SHA; PostgreSQL migrations end at 0006 |
| Physical phone | Pending owner check | Device, browser, date/time, URL and results below |
| Real degradation email | Drill prepared; delivery pending | Monitor incident transition and actual received alert/recovery email timestamps |
| Fresh backup and restore | Pending | Pre-release export UTC time/checksum and successful isolated restore; use the backup runbook |
| Rollback | Procedure prepared | Record current deployed API/web/ingestion SHAs before merging; application rollback has no Phase 3 schema rollback |
| Production deployment | On hold | Complete the gates, then explicitly authorize merge/deployment |

The owner reported healthy production on October 7 at about 11:10 a.m. EDT (15:10 UTC): `01FB003` recovered, all 12 latest calls succeeded, all six readings were current, operational health was 200, and both monitors were Up. These are owner-supplied observations, not independently rechecked deployment evidence. Record the post-rollout observation window separately from seven-day statistics that contain pre-rollout time. The October 2 compatibility fix was verified around 23:24 UTC; October 9 around 23:24 UTC is its seven-day point, not an automatic release date.

## Controlled degradation-email drill

This separates application threshold checks from monitor/email delivery. It does **not** change production readings, thresholds, scheduler, monitor URLs, or recipients.

The helper uses the deployed `operational_findings` implementation against a new in-memory SQLite database on each evaluation. It uses the real committed `01FB003` discharge fixture and its historical clock. Only the source-run statuses are synthetic, explicitly identified as drill data. No `DATABASE_URL` is used as a target, and no webhook or email is sent by the helper.

From the candidate checkout:

```sh
.venv/bin/python scripts/phase2_alert_drill.py serve \
  --state-file /private/tmp/riverwise-phase2-alert-drill.json --port 8013
```

In another terminal:

```sh
.venv/bin/python scripts/phase2_alert_drill.py set-state \
  --state-file /private/tmp/riverwise-phase2-alert-drill.json --state healthy
curl -I http://127.0.0.1:8013/api/v1/operational-health
.venv/bin/python scripts/phase2_alert_drill.py set-state \
  --state-file /private/tmp/riverwise-phase2-alert-drill.json --state two-failures
curl -I http://127.0.0.1:8013/api/v1/operational-health
.venv/bin/python scripts/phase2_alert_drill.py set-state \
  --state-file /private/tmp/riverwise-phase2-alert-drill.json --state degraded
curl -i http://127.0.0.1:8013/api/v1/operational-health
.venv/bin/python scripts/phase2_alert_drill.py set-state \
  --state-file /private/tmp/riverwise-phase2-alert-drill.json --state healthy
```

Expected statuses: **200 → 200 → 503 → 200**, with matching GET/HEAD status and an empty HEAD body. Degraded JSON must identify `repeated_failure:wsc:01FB003`. These local checks do not prove delivery.

To test email, the target must be reachable by the external monitor; localhost is not reachable from UptimeRobot. Use a separately identified temporary public drill target with the same helper and no production database, using an already approved hosting/tunnel option. A new hosting service, cost, tunnel or monitor plan change needs its own review before activation. Do not redirect either production monitor or interrupt production coverage. An optional container is prepared in `docs/deployment/alert-drill.Dockerfile`. If an isolated public drill service is later approved, set `RAILWAY_DOCKERFILE_PATH=/docs/deployment/alert-drill.Dockerfile`, leave root at the repository root, and attach no production database or secrets. Change states in that service with `python scripts/phase2_alert_drill.py set-state --state-file /tmp/riverwise-phase2-alert-drill.json --state degraded` (then `healthy` for recovery). This packaging is prepared, not provisioned or deployed; no hosting cost is assumed. Configure a separate drill monitor with the same method, interval, alert rules and owner email contact if the plan permits it. A sample email/test button is insufficient.

1. Record drill URL and monitor configuration, and wait for an observed healthy check.
2. Set `two-failures`; observe continued Up.
3. Set `degraded`; leave it until the monitor's incident threshold is satisfied. Record first failed check, incident creation, and **actual inbox receipt** of the degradation message. Record subject/incident ID and timestamps, not private email content.
4. Set `healthy`; observe recovery and record actual recovery receipt if enabled.
5. Confirm production remains healthy, stop the drill service, and remove the drill monitor/public exposure after recording evidence.

The drill verifies the threshold-to-HTTP result and monitor/email path. It does not establish delivery of a scheduler webhook or a real provider-outage email, and drill incidents must never count as production downtime. The owner must confirm inbox receipt; Codex cannot infer it from an HTTP status or monitor configuration.

## Physical phone check

Use the Phase 3 candidate preview on the same trusted Wi-Fi network, or an approved preview URL. Localhost on the phone refers to the phone, not this computer. Record device/model, OS, browser/version, UTC and local time, preview URL, and candidate SHA. A 390 px automated viewport is not this check.

- [ ] Search by river name and WSC ID; choose regions and clear a no-results filter.
- [ ] Sort by score, completeness, freshness, and name; read written status and measurement age.
- [ ] Open a gauge from both the card list and map/text equivalent. Core information works with the map unavailable.
- [ ] Read discharge units, timestamps and source/qualifier table. Scroll the table without horizontal page overflow.
- [ ] Read modeled precipitation history and the separate forecast; null, stale and missing states remain explicit.
- [ ] Copy/open a station link; fallback link is selectable if clipboard permission fails.
- [ ] Rotate portrait/landscape, increase text size, and use VoiceOver/TalkBack to check controls and reading order.
- [ ] Confirm `/status` and Score Lab still work and no Trip Planner navigation is present.

Record failures as concrete issues; do not mark the gate complete until the candidate is rechecked after a fix.

## Backup and rollback

Follow [postgres-backups.md](postgres-backups.md) before deployment. Keep credentials and archives outside Git. Record export time, checksum, client/server versions, isolated restore target, duration, table counts, latest observation/snapshot times and cleanup. Never restore onto production as a drill.

On 2026-10-07, `pg_restore --list` accepted the October 2 archive and its saved SHA-256 verified. Docker was stopped, so no new local restore was run. The existing October 2 export remains historical evidence, not a fresh pre-release export. Its archive listing and checksum can be rechecked read-only, but that alone is not a new restore drill.

Before merging, record each Railway service's current deployed commit and the release commit. Deploy the API before the web so `/weather` is available; a web-first mismatch must show an unavailable-weather state while measured data remains usable. If Railway autodeploys all services together, verify that compatibility behavior during rollout. The ingestion code/image's behavior is unchanged; confirm the next scheduled run still succeeds rather than claiming that no redeploy happened.

For an application regression, redeploy the recorded prior API/web commits in Railway. Do not downgrade migrations: Phase 3 adds none. If an unexpected data/schema problem occurs, stop ingestion and assess separately using the existing backup/rollback runbooks. Do not stop ingestion merely to test notification delivery.

After release, verify the public index/detail/weather/status paths, all six station freshness states, operational-health GET/HEAD, both monitors, and a subsequent scheduled cycle. Record the deployed SHA/time and actual results before marking deployment complete.
