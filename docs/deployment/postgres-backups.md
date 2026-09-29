# Manual PostgreSQL export and restore drill

Riverwise stores reproducible provider observations and non-reproducible accumulated score snapshots and ingestion history. Until a native backup schedule is confirmed and enabled, take a portable logical export at least weekly and before schema changes. Keep copies on encrypted storage outside this repository and outside the Railway project. A local-only copy does not survive loss of that computer.

Railway's [Postgres backup guide](https://docs.railway.com/guides/postgres-backups-restores) documents logical dumps and the `railway connect --tunnel-only` workflow. On 2026-09-29, the user confirmed that this project's Postgres **Backups** tab requires Pro for native backups on the current Trial plan. Recheck the tab after any plan change. A native volume backup restores within the same Railway project and environment, while a logical dump can be restored elsewhere.

## Export from Railway

On macOS, install the Railway CLI and PostgreSQL client tools. Riverwise's local Docker database uses PostgreSQL 17; `pg_dump` 18 can export an older PostgreSQL server, but verify the installed client version before each drill.

```zsh
brew install railway libpq
export PATH="$(brew --prefix libpq)/bin:$PATH"
pg_dump --version
pg_restore --version
```

From this repository, use `railway link` if it is not already linked, selecting the Riverwise project and **production** environment. In terminal 1, open a private tunnel to the service named `Postgres` and leave it running:

```zsh
railway connect Postgres --tunnel-only
```

In terminal 2, paste the tunnel connection URL when prompted. Input is hidden; do not put the URL in a command, file, shell history, or repository. Create the backup in a sibling directory so it cannot be committed accidentally:

```zsh
mkdir -p ../Riverwise-backups
umask 077
read -rs "RW_BACKUP_URL?Paste the tunnel connection URL: "
echo
BACKUP_FILE="../Riverwise-backups/riverwise-production-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump "$RW_BACKUP_URL" --format=custom --no-owner --no-acl --file="$BACKUP_FILE"
unset RW_BACKUP_URL
```

Stop if `pg_dump` reports an error. Only after it succeeds, check the archive and record its checksum:

```zsh
pg_restore --list "$BACKUP_FILE" >/dev/null
shasum -a 256 "$BACKUP_FILE" > "${BACKUP_FILE}.sha256"
ls -lh "$BACKUP_FILE" "${BACKUP_FILE}.sha256"
shasum -a 256 -c "${BACKUP_FILE}.sha256"
```

The archive listing and checksum check do not prove that every row can be restored. Preserve the dump and its checksum together. Before a later restore, rerun the checksum check from the repository directory.

## Restore into a separate local database

Never use the production connection URL as the restore target. Start the local PostgreSQL 17 container and create a distinct scratch database:

```zsh
docker compose up -d db
RESTORE_DB="riverwise_restore_$(date -u +%Y%m%d_%H%M%S)"
docker compose exec -T db createdb -U riverwise "$RESTORE_DB"
time pg_restore \
  --dbname="postgresql://riverwise:riverwise@localhost:5432/${RESTORE_DB}" \
  --no-owner --no-acl --exit-on-error "$BACKUP_FILE"
```

Confirm table counts and recent timestamps in the scratch database:

```zsh
docker compose exec -T db psql -U riverwise -d "$RESTORE_DB" -c "
  SELECT 'stations' AS table_name, count(*) FROM stations
  UNION ALL SELECT 'hydro_observations', count(*) FROM hydro_observations
  UNION ALL SELECT 'weather_hours', count(*) FROM weather_hours
  UNION ALL SELECT 'score_snapshots', count(*) FROM score_snapshots
  UNION ALL SELECT 'ingest_runs', count(*) FROM ingest_runs;
  SELECT max(observed_at_utc) AS latest_observation FROM hydro_observations;
  SELECT max(computed_at_utc) AS latest_snapshot FROM score_snapshots;
"
```

Compare the counts with production near the export time if possible. Record the export time, checksum, PostgreSQL versions, restore duration, table counts, and latest timestamps in the deployment ADR. Once verified, remove only the named scratch database:

```zsh
docker compose exec -T db dropdb -U riverwise "$RESTORE_DB"
```

Check that no database matching `riverwise_restore_%` remains if cleanup is uncertain. Keep the export and checksum; do not commit either one.
