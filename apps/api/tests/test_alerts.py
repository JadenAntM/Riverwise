from datetime import datetime, timedelta

from conftest import EVALUATION_TIME
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.alerts import (
    mark_alert_notified,
    operational_findings,
    refresh_operational_alerts,
)
from app.models import IngestRun, OperationalAlert


def _run(session: Session, when: datetime, status: str) -> None:
    session.add(
        IngestRun(
            started_at_utc=when,
            ended_at_utc=when,
            source="wsc",
            station_id="01FB001",
            status=status,
        )
    )
    session.commit()


def test_repeated_failure_alert_opens_deduplicates_and_resolves(session: Session) -> None:
    for minute in (1, 2, 3):
        _run(session, EVALUATION_TIME + timedelta(minutes=minute), "failed")
    now = EVALUATION_TIME + timedelta(minutes=4)
    finding = next(
        item for item in operational_findings(session, now)
        if item.key == "repeated_failure:wsc:01FB001"
    )
    assert finding.code == "repeated_failure"

    first = refresh_operational_alerts(session, now)
    alert_change = next(item for item in first if item.alert.key == finding.key)
    assert alert_change.opened and alert_change.notify_due
    mark_alert_notified(session, finding.key, now)

    second = refresh_operational_alerts(session, now + timedelta(minutes=1))
    alert_change = next(item for item in second if item.alert.key == finding.key)
    assert not alert_change.opened and not alert_change.notify_due

    _run(session, now + timedelta(minutes=2), "success")
    resolved_changes = refresh_operational_alerts(session, now + timedelta(minutes=3))
    assert any(item.alert.key == finding.key and item.resolved for item in resolved_changes)
    stored = session.get(OperationalAlert, finding.key)
    assert stored is not None
    assert stored.resolved_at_utc is not None


def test_operational_health_exposes_degraded_state_without_secrets(client: TestClient) -> None:
    response = client.get("/api/v1/operational-health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert all(item["code"] == "discharge_stale" for item in response.json()["alerts"])
    status = client.get("/api/v1/ingestion")
    assert status.status_code == 200
    assert status.json()["alerts"] == response.json()["alerts"]


def test_operational_health_head_matches_get_status(client: TestClient, monkeypatch) -> None:
    degraded = client.head("/api/v1/operational-health")
    assert degraded.status_code == 503
    assert degraded.content == b""

    monkeypatch.setattr("app.main.operational_findings", lambda session, now: [])
    assert client.get("/api/v1/operational-health").status_code == 200
    healthy = client.head("/api/v1/operational-health")
    assert healthy.status_code == 200
    assert healthy.content == b""
