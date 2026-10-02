"""A disposable PostgreSQL contract check; skipped without an explicit test URL."""

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import normalize_database_url
from app.ingestion import parse_wsc_csv, seed_station, upsert_hydro
from app.models import HydroObservation, HydroRevision, IngestRun, Station
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
        "ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,"
        "Approval/Approbation\n"
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
                assert upsert_hydro(
                    session, parse_wsc_csv(header + original, {station_id}), now
                ).inserted == 1
                assert upsert_hydro(
                    session, parse_wsc_csv(header + original, {station_id}), now
                ).revisions == 0
                assert upsert_hydro(
                    session, parse_wsc_csv(header + revised, {station_id}), now
                ).revisions == 1
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
                    item for item in ingestion_overview(session, now)["sources"]
                    if item["station_id"] == station_id
                )
                assert source["error_kind"] == "invalid_payload"
                assert source["run_id"] > 0
            finally:
                session.rollback()
                session.execute(delete(HydroRevision).where(HydroRevision.station_id == station_id))
                session.execute(delete(IngestRun).where(IngestRun.station_id == station_id))
                session.execute(
                    delete(HydroObservation).where(HydroObservation.station_id == station_id)
                )
                session.execute(delete(Station).where(Station.id == station_id))
                session.commit()
    finally:
        engine.dispose()
