import importlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion import NoUsableObservations
from app.models import IngestRun

ROOT = Path(__file__).resolve().parents[3]


def _ingest_log(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    return importlib.import_module("jobs.ingest.ingest")._log


def test_successful_ingest_events_use_stdout(capsys, monkeypatch) -> None:
    _ingest_log(monkeypatch)("source_complete", source="wsc", station_id="01FB001")

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "level": "info",
        "event": "source_complete",
        "source": "wsc",
        "station_id": "01FB001",
    }


def test_failed_ingest_events_use_stderr(capsys, monkeypatch) -> None:
    _ingest_log(monkeypatch)("source_failed", source="wsc", station_id="01FB001", error="test")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "level": "error",
        "event": "source_failed",
        "source": "wsc",
        "station_id": "01FB001",
        "error": "test",
    }


def test_failure_kind_separates_provider_and_payload_errors(monkeypatch) -> None:
    _ingest_log(monkeypatch)
    ingest = importlib.import_module("jobs.ingest.ingest")
    assert ingest._error_kind(httpx.TimeoutException("timeout")) == "provider_timeout"
    assert ingest._error_kind(NoUsableObservations("empty")) == "missing_measurement"
    assert ingest._error_kind(ValueError("bad CSV")) == "invalid_payload"


def test_wsc_invalid_response_records_classification_and_stable_run_id(
    session: Session, monkeypatch, capsys
) -> None:
    _ingest_log(monkeypatch)
    ingest = importlib.import_module("jobs.ingest.ingest")

    class FakeResponse:
        text = "invalid CSV"

        def raise_for_status(self) -> None:
            pass

    class FakeClient:
        def get(self, *_args, **_kwargs) -> FakeResponse:
            return FakeResponse()

    ingest._ingest_wsc_station(
        session,
        FakeClient(),
        {"id": "01FB001"},
        datetime(2026, 9, 23, 16, 30, tzinfo=UTC),
    )
    run = session.scalar(
        select(IngestRun)
        .where(IngestRun.source == "wsc")
        .order_by(IngestRun.id.desc())
        .limit(1)
    )
    assert run is not None
    assert run.status == "failed"
    assert run.error_kind == "invalid_payload"
    event = json.loads(capsys.readouterr().err)
    assert event["run_id"] == run.id
    assert event["error_kind"] == "invalid_payload"


def test_failed_wsc_station_does_not_prevent_weather_import(
    session: Session, monkeypatch, capsys
) -> None:
    _ingest_log(monkeypatch)
    ingest = importlib.import_module("jobs.ingest.ingest")
    weather_payload = json.loads(
        (ROOT / "tests" / "fixtures" / "open_meteo_01FB001_sample.json").read_text()
    )

    class FakeResponse:
        text = "invalid CSV"

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return weather_payload

    class FakeClient:
        def get(self, *_args, **_kwargs) -> FakeResponse:
            return FakeResponse()

    now = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)
    station = {"id": "01FB001", "latitude": 46.36, "longitude": -61.05}
    ingest._ingest_wsc_station(session, FakeClient(), station, now)
    ingest._ingest_weather_station(session, FakeClient(), station, now)
    runs = list(
        session.scalars(select(IngestRun).where(IngestRun.source.in_(("wsc", "open_meteo"))))
    )
    assert [(run.source, run.status) for run in runs] == [
        ("wsc", "failed"),
        ("open_meteo", "success"),
    ]
    assert "source_complete" in capsys.readouterr().out


def test_operator_alert_webhook_delivery_is_deduplicated(
    session: Session, monkeypatch, capsys
) -> None:
    _ingest_log(monkeypatch)
    ingest = importlib.import_module("jobs.ingest.ingest")
    now = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)
    for minute in (1, 2, 3):
        session.add(
            IngestRun(
                started_at_utc=now.replace(minute=30 + minute),
                source="wsc",
                station_id="01FB001",
                status="failed",
            )
        )
    session.commit()

    delivered = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            assert timeout == 5.0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url: str, *, json: dict) -> FakeResponse:
            assert url == "https://example.org/private-test-webhook"
            delivered.append(json)
            return FakeResponse()

    monkeypatch.setattr(ingest.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        ingest,
        "get_settings",
        lambda: type("Settings", (), {"operator_alert_webhook_url": "https://example.org/private-test-webhook"})(),
    )
    ingest._process_operational_alerts(session, now.replace(minute=34))
    first_count = len(delivered)
    assert first_count > 0
    assert any(item["code"] == "repeated_failure" for item in delivered)
    ingest._process_operational_alerts(session, now.replace(minute=35))
    assert len(delivered) == first_count
    session.add(
        IngestRun(
            started_at_utc=now.replace(minute=36),
            source="wsc",
            station_id="01FB001",
            status="success",
        )
    )
    session.commit()
    ingest._process_operational_alerts(session, now.replace(minute=37))
    assert any(
        item["event"] == "riverwise.operator_alert.resolved"
        and item["key"] == "repeated_failure:wsc:01FB001"
        for item in delivered
    )
    assert "private-test-webhook" not in capsys.readouterr().err
