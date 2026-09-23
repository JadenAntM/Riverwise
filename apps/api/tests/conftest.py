import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.ingestion import (
    parse_open_meteo,
    parse_wsc_csv,
    parse_wsc_daily_csv,
    seed_station,
    upsert_hydro,
    upsert_weather,
)
from app.main import app
from app.models import IngestRun
from app.service import persist_score_snapshots

ROOT = Path(__file__).resolve().parents[3]
EVALUATION_TIME = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    with maker() as db:
        stations = json.loads((ROOT / "data" / "stations.json").read_text())
        for item in stations:
            seed_station(db, item)
        station = stations[0]
        hydro = parse_wsc_csv(
            (ROOT / "tests" / "fixtures" / "wsc_01FB001_sample.csv").read_text(),
            {station["id"]},
        )
        temperature = parse_wsc_csv(
            (ROOT / "tests" / "fixtures" / "wsc_01FB001_temperature_sample.csv").read_text(),
            {station["id"]},
        )
        daily = parse_wsc_daily_csv(
            (ROOT / "tests" / "fixtures" / "wsc_01FB001_daily_sample.csv").read_text(),
            {station["id"]},
        )
        weather = parse_open_meteo(
            json.loads(
                (ROOT / "tests" / "fixtures" / "open_meteo_01FB001_sample.json").read_text()
            ),
            station["id"],
            EVALUATION_TIME,
        )
        upsert_hydro(db, [*hydro, *temperature, *daily], EVALUATION_TIME)
        upsert_weather(db, weather, EVALUATION_TIME)
        db.add(
            IngestRun(
                started_at_utc=EVALUATION_TIME,
                ended_at_utc=EVALUATION_TIME,
                source="offline_fixtures",
                station_id=station["id"],
                status="success",
                fetched_count=len(hydro) + len(temperature) + len(daily) + len(weather),
                upserted_count=len(hydro) + len(temperature) + len(daily) + len(weather),
                inserted_count=len(hydro) + len(temperature) + len(daily) + len(weather),
                updated_count=0,
                revision_count=0,
                duration_ms=10,
            )
        )
        db.commit()
        persist_score_snapshots(db, [item["id"] for item in stations], EVALUATION_TIME)
        yield db


@pytest.fixture
def client(session: Session) -> TestClient:
    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
