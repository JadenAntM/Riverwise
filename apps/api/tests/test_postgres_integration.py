"""A disposable PostgreSQL contract check; skipped without an explicit test URL."""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import normalize_database_url
from app.ingestion import parse_wsc_csv, seed_station, upsert_hydro, upsert_weather
from app.main import station_weather
from app.models import (
    HydroObservation,
    HydroRevision,
    IngestRun,
    Station,
    WeatherHour,
)
from app.service import ingestion_overview


def test_postgres_revision_and_diagnostic_contract() -> None:
    raw_url = os.getenv("RIVERWISE_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("No explicit disposable PostgreSQL test database configured")
    url = make_url(normalize_database_url(raw_url))
    if url.get_backend_name() != "postgresql" or "_test" not in (url.database or ""):
        pytest.fail("RIVERWISE_TEST_DATABASE_URL must name a PostgreSQL test database")

    station_id = "TSTPH2"
    now = datetime(2026, 10, 2, 16, tzinfo=UTC)
    header = (
        "ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,Approval/Approbation\n"
    )
    original = f"{station_id},2026-10-02T15:00:00Z,47,8.1,,Provisional\n"
    revised = original.replace("8.1", "8.2")
    engine = create_engine(url)
    try:
        with Session(engine, expire_on_commit=False) as session:
            assert session.get(Station, station_id) is None
            try:
                seed_station(
                    session,
                    {
                        "id": station_id,
                        "name": "Temporary PostgreSQL test station",
                        "latitude": 46.0,
                        "longitude": -61.0,
                        "province": "NS",
                        "active": True,
                        "has_discharge": True,
                        "display_order": 99,
                        "source_url": "https://example.org/test-only",
                    },
                )
                assert (
                    upsert_hydro(
                        session, parse_wsc_csv(header + original, {station_id}), now
                    ).inserted
                    == 1
                )
                assert (
                    upsert_hydro(
                        session, parse_wsc_csv(header + original, {station_id}), now
                    ).revisions
                    == 0
                )
                assert (
                    upsert_hydro(
                        session, parse_wsc_csv(header + revised, {station_id}), now
                    ).revisions
                    == 1
                )
                revision = session.scalar(
                    select(HydroRevision).where(HydroRevision.station_id == station_id)
                )
                assert revision is not None
                assert revision.old_fields_json["value"] == 8.1
                assert revision.new_fields_json["value"] == 8.2
                session.add(
                    IngestRun(
                        started_at_utc=now,
                        source="wsc",
                        station_id=station_id,
                        status="failed",
                        error_kind="invalid_payload",
                    )
                )
                session.commit()
                source = next(
                    item
                    for item in ingestion_overview(session, now)["sources"]
                    if item["station_id"] == station_id
                )
                assert source["error_kind"] == "invalid_payload"
                assert source["run_id"] > 0
                weather = {
                    "station_id": station_id,
                    "valid_at_utc": now + timedelta(hours=1),
                    "kind": "forecast",
                    "air_temp_c": 14.0,
                    "precip_mm": None,
                    "cloud_cover_pct": 70.0,
                    "pressure_hpa": None,
                }
                upsert_weather(session, [weather], now - timedelta(hours=4))
                session.commit()
                with patch("app.main.datetime", wraps=datetime) as clock:
                    clock.now.return_value = now
                    preview = station_weather(station_id, 48, 24, session)
                assert preview.history == []
                assert len(preview.forecast) == 1
                assert preview.forecast[0].valid_at_utc == now + timedelta(hours=1)
                assert preview.forecast[0].retrieval_state == "stale"
                assert preview.forecast[0].precip_mm is None
                assert preview.forecast[0].provider_issued_at_utc is None
                upsert_weather(session, [{**weather, "precip_mm": 0.0}], now)
                session.commit()
                with patch("app.main.datetime", wraps=datetime) as clock:
                    clock.now.return_value = now
                    preview = station_weather(station_id, 48, 24, session)
                assert len(preview.forecast) == 1
                assert preview.forecast[0].precip_mm == 0.0
                assert preview.forecast[0].retrieval_state == "current"
            finally:
                session.rollback()
                session.execute(delete(HydroRevision).where(HydroRevision.station_id == station_id))
                session.execute(delete(IngestRun).where(IngestRun.station_id == station_id))
                session.execute(delete(WeatherHour).where(WeatherHour.station_id == station_id))
                session.execute(
                    delete(HydroObservation).where(HydroObservation.station_id == station_id)
                )
                session.execute(delete(Station).where(Station.id == station_id))
                session.commit()
    finally:
        engine.dispose()
