#!/usr/bin/env python3
import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402
from app.alerts import mark_alert_notified, refresh_operational_alerts  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.ingestion import (  # noqa: E402
    NoUsableObservations,
    UpsertResult,
    parse_open_meteo,
    parse_wsc_csv,
    parse_wsc_daily_csv,
    seed_station,
    upsert_hydro,
    upsert_weather,
)
from app.models import HydroObservation, IngestRun  # noqa: E402
from app.service import persist_score_snapshots  # noqa: E402

def _log(event: str, **fields: object) -> None:
    failed = event.endswith("_failed") or event == "operator_alert_opened"
    print(
        json.dumps(
            {"level": "error" if failed else "info", "event": event, **fields},
            default=str,
            separators=(",", ":"),
        ),
        file=sys.stderr if failed else sys.stdout,
        flush=True,
    )


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "provider_timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return "provider_http"
    if isinstance(exc, httpx.RequestError):
        return "provider_network"
    if isinstance(exc, NoUsableObservations):
        return "missing_measurement"
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return "invalid_payload"
    return "internal_error"


def _record_run(
    session,
    source: str,
    station_id: str | None,
    started: datetime,
    status: str,
    fetched: int,
    stats: UpsertResult,
    error: str | None = None,
    error_kind: str | None = None,
) -> int:
    ended = datetime.now(UTC)
    run = IngestRun(
        started_at_utc=started,
        ended_at_utc=ended,
        source=source,
        station_id=station_id,
        status=status,
        fetched_count=fetched,
        upserted_count=stats.processed,
        inserted_count=stats.inserted,
        updated_count=stats.updated,
        revision_count=stats.revisions,
        duration_ms=int((ended - started).total_seconds() * 1000),
        error_kind=error_kind,
        error=error[:500] if error else None,
    )
    session.add(run)
    session.commit()
    return run.id


def _load_seed(session) -> list[dict]:
    stations = json.loads((ROOT / "data" / "stations.json").read_text())
    for item in stations:
        seed_station(session, item)
    return stations


def ingest_fixture(session, evaluation_time: datetime) -> None:
    stations = _load_seed(session)
    station = stations[0]
    started = datetime.now(UTC)
    hydro_text = (ROOT / "tests" / "fixtures" / "wsc_01FB001_sample.csv").read_text()
    weather_data = json.loads(
        (ROOT / "tests" / "fixtures" / "open_meteo_01FB001_sample.json").read_text()
    )
    hydro = parse_wsc_csv(hydro_text, {station["id"]})
    temperature = parse_wsc_csv(
        (ROOT / "tests" / "fixtures" / "wsc_01FB001_temperature_sample.csv").read_text(),
        {station["id"]},
    )
    daily = parse_wsc_daily_csv(
        (ROOT / "tests" / "fixtures" / "wsc_01FB001_daily_sample.csv").read_text(),
        {station["id"]},
    )
    weather = parse_open_meteo(weather_data, station["id"], evaluation_time)
    hydro_rows = [*hydro, *temperature, *daily]
    stats = upsert_hydro(session, hydro_rows, started) + upsert_weather(
        session, weather, started
    )
    run_id = _record_run(
        session,
        "offline_fixtures",
        station["id"],
        started,
        "success",
        len(hydro_rows) + len(weather),
        stats,
    )
    snapshot_count = persist_score_snapshots(
        session, [item["id"] for item in stations], evaluation_time
    )
    _log(
        "ingest_complete",
        run_id=run_id,
        source="offline_fixtures",
        fetched=len(hydro_rows) + len(weather),
        upserted=stats.processed,
        inserted=stats.inserted,
        updated=stats.updated,
        revisions=stats.revisions,
        score_snapshots=snapshot_count,
    )


def ingest_live(session, evaluation_time: datetime) -> None:
    stations = _load_seed(session)
    # The first daily-history backfill is substantially larger than the
    # real-time request, while still needing a bounded network timeout.
    timeout = httpx.Timeout(30.0)
    transport = httpx.HTTPTransport(retries=2)
    with httpx.Client(timeout=timeout, transport=transport) as client:
        for station in stations:
            _ingest_wsc_station(session, client, station, evaluation_time)
        for station in stations:
            _ingest_wsc_daily_station(session, client, station, evaluation_time)
        for station in stations:
            _ingest_weather_station(session, client, station, evaluation_time)
    snapshot_count = persist_score_snapshots(
        session, [station["id"] for station in stations], evaluation_time
    )
    _log("score_snapshots_complete", written=snapshot_count)
    _process_operational_alerts(session, evaluation_time)


def _process_operational_alerts(session, evaluation_time: datetime) -> None:
    changes = refresh_operational_alerts(session, evaluation_time)
    webhook_url = get_settings().operator_alert_webhook_url
    for change in changes:
        alert = change.alert
        if change.opened:
            _log(
                "operator_alert_opened",
                alert_key=alert.key,
                code=alert.code,
                source=alert.source,
                station_id=alert.station_id,
                message=alert.message,
            )
        if change.resolved:
            _log("operator_alert_resolved", alert_key=alert.key, code=alert.code)
        if not webhook_url or not change.notify_due:
            continue
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    webhook_url,
                    json={
                        "event": (
                            "riverwise.operator_alert.resolved"
                            if change.resolved
                            else "riverwise.operator_alert"
                        ),
                        "key": alert.key,
                        "code": alert.code,
                        "source": alert.source,
                        "station_id": alert.station_id,
                        "message": alert.message,
                        "first_seen_at_utc": alert.first_seen_at_utc.isoformat(),
                    },
                )
                response.raise_for_status()
            if not change.resolved:
                mark_alert_notified(session, alert.key, evaluation_time)
            _log("operator_alert_delivered", alert_key=alert.key, code=alert.code)
        except Exception as exc:
            _log(
                "operator_alert_delivery_failed",
                alert_key=alert.key,
                code=alert.code,
                error_type=type(exc).__name__,
            )


def _ingest_wsc_station(
    session, client, station: dict, evaluation_time: datetime
) -> None:
    station_id = station["id"]
    started = datetime.now(UTC)
    try:
        response = client.get(
            "https://wateroffice.ec.gc.ca/services/real_time_data/csv/inline",
            params=[
                ("stations[]", station_id),
                ("parameters[]", "47"),
                ("parameters[]", "5"),
                (
                    "start_date",
                    (evaluation_time - timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S"),
                ),
                ("end_date", evaluation_time.strftime("%Y-%m-%d %H:%M:%S")),
            ],
        )
        response.raise_for_status()
        rows = parse_wsc_csv(response.text, {station_id})
        stats = upsert_hydro(session, rows, started)
        run_id = _record_run(session, "wsc", station_id, started, "success", len(rows), stats)
        _log(
            "source_complete",
            run_id=run_id,
            source="wsc",
            station_id=station_id,
            fetched=len(rows),
            upserted=stats.processed,
            inserted=stats.inserted,
            updated=stats.updated,
            revisions=stats.revisions,
        )
    except Exception as exc:
        session.rollback()
        error_kind = _error_kind(exc)
        run_id = _record_run(
            session, "wsc", station_id, started, "failed", 0, UpsertResult(), str(exc), error_kind
        )
        _log(
            "source_failed", run_id=run_id, source="wsc", station_id=station_id,
            error_kind=error_kind, error=str(exc),
        )


def _ingest_wsc_daily_station(
    session, client, station: dict, evaluation_time: datetime
) -> None:
    station_id = station["id"]
    recent_success = session.scalar(
        select(IngestRun)
        .where(
            IngestRun.source == "wsc_daily",
            IngestRun.station_id == station_id,
            IngestRun.status == "success",
        )
        .order_by(IngestRun.started_at_utc.desc())
        .limit(1)
    )
    if recent_success:
        started_at = recent_success.started_at_utc
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        if evaluation_time - started_at < timedelta(hours=20):
            return

    latest = session.scalar(
        select(HydroObservation)
        .where(
            HydroObservation.station_id == station_id,
            HydroObservation.parameter == "daily_discharge",
        )
        .order_by(HydroObservation.observed_at_utc.desc())
        .limit(1)
    )
    start_date = (
        latest.observed_at_utc.date() - timedelta(days=14)
        if latest
        else evaluation_time.date() - timedelta(days=3653)
    )
    started = datetime.now(UTC)
    try:
        response = client.get(
            "https://wateroffice.ec.gc.ca/services/daily_data/csv/inline",
            params=[
                ("stations[]", station_id),
                ("parameters[]", "flow"),
                ("start_date", start_date.isoformat()),
                ("end_date", evaluation_time.date().isoformat()),
            ],
        )
        response.raise_for_status()
        rows = parse_wsc_daily_csv(response.text, {station_id})
        stats = upsert_hydro(session, rows, started)
        run_id = _record_run(
            session,
            "wsc_daily",
            station_id,
            started,
            "success",
            len(rows),
            stats,
        )
        _log(
            "source_complete",
            run_id=run_id,
            source="wsc_daily",
            station_id=station_id,
            fetched=len(rows),
            upserted=stats.processed,
            inserted=stats.inserted,
            updated=stats.updated,
            revisions=stats.revisions,
        )
    except Exception as exc:
        session.rollback()
        error_kind = _error_kind(exc)
        run_id = _record_run(
            session,
            "wsc_daily",
            station_id,
            started,
            "failed",
            0,
            UpsertResult(),
            str(exc),
            error_kind,
        )
        _log(
            "source_failed",
            run_id=run_id,
            source="wsc_daily",
            station_id=station_id,
            error_kind=error_kind,
            error=str(exc),
        )


def _ingest_weather_station(
    session, client, station: dict, evaluation_time: datetime
) -> None:
    station_id = station["id"]
    started = datetime.now(UTC)
    try:
        response = client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": station["latitude"],
                "longitude": station["longitude"],
                "hourly": "temperature_2m,precipitation,cloud_cover,surface_pressure",
                "past_days": 4,
                "forecast_days": 1,
                "timezone": "GMT",
            },
        )
        response.raise_for_status()
        rows = parse_open_meteo(response.json(), station_id, evaluation_time)
        stats = upsert_weather(session, rows, started)
        run_id = _record_run(
            session,
            "open_meteo",
            station_id,
            started,
            "success",
            len(rows),
            stats,
        )
        _log(
            "source_complete",
            run_id=run_id,
            source="open_meteo",
            station_id=station_id,
            fetched=len(rows),
            upserted=stats.processed,
            inserted=stats.inserted,
            updated=stats.updated,
            revisions=stats.revisions,
        )
    except Exception as exc:
        session.rollback()
        error_kind = _error_kind(exc)
        run_id = _record_run(
            session,
            "open_meteo",
            station_id,
            started,
            "failed",
            0,
            UpsertResult(),
            str(exc),
            error_kind,
        )
        _log(
            "source_failed",
            run_id=run_id,
            source="open_meteo",
            station_id=station_id,
            error_kind=error_kind,
            error=str(exc),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Riverwise hydrometric and weather data"
    )
    parser.add_argument("--source", choices=("fixtures", "live"), default="fixtures")
    parser.add_argument(
        "--evaluation-time", help="ISO-8601 time used to classify fixture weather"
    )
    args = parser.parse_args()
    evaluation_time = (
        datetime.fromisoformat(args.evaluation_time.replace("Z", "+00:00"))
        if args.evaluation_time
        else datetime.now(UTC)
    )
    started = time.monotonic()
    with SessionLocal() as session:
        if args.source == "live":
            ingest_live(session, evaluation_time)
        else:
            ingest_fixture(session, evaluation_time)
    _log("run_finished", duration_ms=int((time.monotonic() - started) * 1000))


if __name__ == "__main__":
    main()
