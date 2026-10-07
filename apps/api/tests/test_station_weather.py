"""Offline contract checks for separate history/forecast and measured freshness."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from conftest import EVALUATION_TIME
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ingestion import upsert_weather
from app.models import WeatherHour


def weather_row(time: datetime, kind: str, precip: float | None = 1.0) -> dict:
    return {
        "station_id": "01FB001",
        "valid_at_utc": time,
        "kind": kind,
        "air_temp_c": 14.0,
        "precip_mm": precip,
        "cloud_cover_pct": 70.0,
        "pressure_hpa": 1000.0,
    }


def test_weather_preserves_classification_boundaries_nulls_and_provenance(
    client: TestClient, session: Session
) -> None:
    session.execute(delete(WeatherHour))
    hour = EVALUATION_TIME.replace(minute=0)
    upsert_weather(
        session,
        [
            weather_row(hour - timedelta(hours=48), "historical_or_modelled"),
            weather_row(hour - timedelta(hours=47), "historical_or_modelled", None),
            weather_row(hour, "historical_or_modelled", 0),
            weather_row(hour, "forecast", 99),  # expired forecasts stay out of history
            weather_row(hour + timedelta(hours=1), "historical_or_modelled", 99),
            weather_row(hour + timedelta(hours=1), "forecast", 2),
            weather_row(hour + timedelta(hours=24), "forecast", 3),
            weather_row(hour + timedelta(hours=25), "forecast", 4),
        ],
        EVALUATION_TIME,
    )
    session.commit()
    response = client.get("/api/v1/stations/01FB001/weather")
    assert response.status_code == 200
    data = response.json()
    assert data["history_hours"] == 48
    assert data["forecast_hours"] == 24
    assert [row["precip_mm"] for row in data["history"]] == [None, 0]
    assert [row["precip_mm"] for row in data["forecast"]] == [2, 3]
    assert all(row["kind"] == "historical_or_modelled" for row in data["history"])
    assert all(row["kind"] == "forecast" for row in data["forecast"])
    assert data["history"][0]["valid_at_utc"].endswith("Z")
    assert data["forecast"][0]["retrieved_at_utc"] == "2026-09-23T16:30:00Z"
    assert data["forecast"][0]["provider_issued_at_utc"] is None
    assert "preceding" in data["precipitation_semantics"]


def test_empty_weather_and_unknown_station_are_distinct(client: TestClient) -> None:
    response = client.get("/api/v1/stations/01FC002/weather")
    assert response.status_code == 200
    assert response.json()["history"] == []
    assert response.json()["forecast"] == []
    assert client.get("/api/v1/stations/UNKNOWN/weather").status_code == 404
    for query in ("history_hours=0", "history_hours=169", "forecast_hours=0", "forecast_hours=25"):
        assert client.get(f"/api/v1/stations/01FB001/weather?{query}").status_code == 422


def test_forecast_revisions_do_not_change_the_current_score(
    client: TestClient, session: Session
) -> None:
    before = client.get("/api/v1/stations/01FB001").json()["score"]
    time = EVALUATION_TIME.replace(minute=0) + timedelta(hours=1)
    upsert_weather(session, [weather_row(time, "forecast", 400)], EVALUATION_TIME)
    session.commit()
    preview = client.get("/api/v1/stations/01FB001/weather").json()
    assert preview["forecast"][0]["precip_mm"] == 400
    upsert_weather(session, [weather_row(time, "forecast", 0)], EVALUATION_TIME)
    session.commit()
    preview = client.get("/api/v1/stations/01FB001/weather").json()
    assert preview["forecast"][0]["precip_mm"] == 0
    assert (
        len(
            [
                row
                for row in preview["forecast"]
                if row["valid_at_utc"] == time.isoformat().replace("+00:00", "Z")
            ]
        )
        == 1
    )
    assert client.get("/api/v1/stations/01FB001").json()["score"] == before


def test_retrieval_stale_boundary_is_separate_from_valid_time(
    client: TestClient, session: Session
) -> None:
    session.execute(delete(WeatherHour))
    hour = EVALUATION_TIME.replace(minute=0)
    future = hour + timedelta(hours=1)
    upsert_weather(session, [weather_row(future, "forecast")], EVALUATION_TIME - timedelta(hours=3))
    session.commit()
    assert (
        client.get("/api/v1/stations/01FB001/weather").json()["forecast"][0]["retrieval_state"]
        == "current"
    )
    row = session.query(WeatherHour).one()
    row.ingested_at_utc = EVALUATION_TIME - timedelta(hours=3, seconds=1)
    session.commit()
    assert (
        client.get("/api/v1/stations/01FB001/weather").json()["forecast"][0]["retrieval_state"]
        == "stale"
    )


def test_weather_window_remains_utc_across_atlantic_dst(
    client: TestClient, session: Session
) -> None:
    session.execute(delete(WeatherHour))
    now = datetime(2026, 11, 1, 3, 30, tzinfo=UTC)
    upsert_weather(
        session,
        [
            weather_row(now.replace(minute=0) + timedelta(hours=index), "forecast")
            for index in range(1, 25)
        ],
        now,
    )
    session.commit()
    with patch("app.main.datetime", wraps=datetime) as clock:
        clock.now.return_value = now
        data = client.get("/api/v1/stations/01FB001/weather").json()
    assert len(data["forecast"]) == 24
    assert data["forecast"][0]["valid_at_utc"] == "2026-11-01T04:00:00Z"
    assert data["forecast_end_at_utc"] == "2026-11-02T03:00:00Z"


def test_flow_age_does_not_follow_score_completeness(client: TestClient) -> None:
    station = client.get("/api/v1/stations/01FB001").json()
    observed = datetime.fromisoformat(
        station["latest_flow"]["observed_at_utc"].replace("Z", "+00:00")
    )
    with patch("app.main.datetime", wraps=datetime) as clock:
        clock.now.return_value = observed + timedelta(hours=3)
        data = client.get("/api/v1/stations/01FB001").json()
        assert data["flow_state"] == "current"
        assert data["flow_age_minutes"] == 180
        clock.now.return_value += timedelta(seconds=1)
        data = client.get("/api/v1/stations/01FB001").json()
        assert data["flow_state"] == "stale"
    missing = client.get("/api/v1/stations/01FC002").json()
    assert missing["flow_state"] == "missing"
    assert missing["flow_age_minutes"] is None
