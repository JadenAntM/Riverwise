#!/usr/bin/env python3
import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402
from app.ingestion import (  # noqa: E402
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

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("riverwise.ingest")


def _log(event: str, **fields: object) -> None:
    logger.info(
        json.dumps({"event": event, **fields}, default=str, separators=(",", ":"))
    )


def _record_run(
    session,
    source: str,
    station_id: str | None,
    started: datetime,
    status: str,
    fetched: int,
    stats: UpsertResult,
    error: str | None = None,
) -> None:
    ended = datetime.now(UTC)
    session.add(
        IngestRun(
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
            error=error[:500] if error else None,
        )
    )
    session.commit()


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
    _record_run(
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
        _record_run(session, "wsc", station_id, started, "success", len(rows), stats)
        _log(
            "source_complete",
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
        _record_run(
            session, "wsc", station_id, started, "failed", 0, UpsertResult(), str(exc)
        )
        _log("source_failed", source="wsc", station_id=station_id, error=str(exc))


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
        _record_run(
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
        _record_run(
            session,
            "wsc_daily",
            station_id,
            started,
            "failed",
            0,
            UpsertResult(),
            str(exc),
        )
        _log(
            "source_failed",
            source="wsc_daily",
            station_id=station_id,
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
                "past_days": 2,
                "forecast_days": 1,
                "timezone": "GMT",
            },
        )
        response.raise_for_status()
        rows = parse_open_meteo(response.json(), station_id, evaluation_time)
        stats = upsert_weather(session, rows, started)
        _record_run(
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
        _record_run(
            session,
            "open_meteo",
            station_id,
            started,
            "failed",
            0,
            UpsertResult(),
            str(exc),
        )
        _log(
            "source_failed",
            source="open_meteo",
            station_id=station_id,
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
