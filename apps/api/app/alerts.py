"""Operator-facing ingestion alerts, separate from fishing-condition notifications."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import HydroObservation, IngestRun, OperationalAlert, Station

SOURCES = ("wsc", "open_meteo")
IMPORT_OVERDUE = timedelta(minutes=90)
DISCHARGE_STALE = timedelta(hours=3)
REMINDER_INTERVAL = timedelta(hours=6)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class AlertFinding:
    key: str
    code: str
    source: str | None
    station_id: str
    message: str


@dataclass(frozen=True)
class AlertChange:
    alert: OperationalAlert
    opened: bool
    notify_due: bool
    resolved: bool = False


def operational_findings(session: Session, now: datetime) -> list[AlertFinding]:
    findings = []
    stations = list(session.scalars(select(Station).order_by(Station.display_order)).all())
    for station in stations:
        latest = session.scalar(
            select(HydroObservation.observed_at_utc)
            .where(
                HydroObservation.station_id == station.id,
                HydroObservation.parameter == "discharge",
                HydroObservation.observed_at_utc <= now,
            )
            .order_by(HydroObservation.observed_at_utc.desc())
            .limit(1)
        )
        if latest is None or now - _aware(latest) > DISCHARGE_STALE:
            findings.append(
                AlertFinding(
                    key=f"discharge_stale:{station.id}",
                    code="discharge_stale",
                    source="wsc",
                    station_id=station.id,
                    message=f"WSC {station.id} has no discharge reading within three hours.",
                )
            )
        for source in SOURCES:
            runs = list(
                session.scalars(
                    select(IngestRun)
                    .where(IngestRun.station_id == station.id, IngestRun.source == source)
                    .order_by(IngestRun.started_at_utc.desc(), IngestRun.id.desc())
                    .limit(3)
                ).all()
            )
            if not runs:
                continue
            if now - _aware(runs[0].started_at_utc) > IMPORT_OVERDUE:
                findings.append(
                    AlertFinding(
                        key=f"import_overdue:{source}:{station.id}",
                        code="import_overdue",
                        source=source,
                        station_id=station.id,
                        message=f"{source} import for WSC {station.id} has not run in 90 minutes.",
                    )
                )
            if len(runs) == 3 and all(run.status == "failed" for run in runs):
                findings.append(
                    AlertFinding(
                        key=f"repeated_failure:{source}:{station.id}",
                        code="repeated_failure",
                        source=source,
                        station_id=station.id,
                        message=(
                            f"{source} import for WSC {station.id} failed three times in a row."
                        ),
                    )
                )
    return findings


def refresh_operational_alerts(session: Session, now: datetime) -> list[AlertChange]:
    findings = operational_findings(session, now)
    active_keys = {finding.key for finding in findings}
    changes = []
    for finding in findings:
        alert = session.get(OperationalAlert, finding.key)
        opened = alert is None or alert.resolved_at_utc is not None
        if alert is None:
            alert = OperationalAlert(
                key=finding.key,
                code=finding.code,
                source=finding.source,
                station_id=finding.station_id,
                message=finding.message,
                first_seen_at_utc=now,
                last_seen_at_utc=now,
                resolved_at_utc=None,
                last_notified_at_utc=None,
            )
            session.add(alert)
        else:
            alert.message = finding.message
            alert.last_seen_at_utc = now
            if opened:
                alert.first_seen_at_utc = now
                alert.resolved_at_utc = None
                alert.last_notified_at_utc = None
        notify_due = (
            alert.last_notified_at_utc is None
            or now - _aware(alert.last_notified_at_utc) >= REMINDER_INTERVAL
        )
        changes.append(AlertChange(alert, opened, notify_due))
    for alert in session.scalars(
        select(OperationalAlert).where(OperationalAlert.resolved_at_utc.is_(None))
    ):
        if alert.key not in active_keys:
            alert.resolved_at_utc = now
            changes.append(AlertChange(alert, False, alert.last_notified_at_utc is not None, True))
    session.commit()
    return changes


def mark_alert_notified(session: Session, key: str, now: datetime) -> None:
    alert = session.get(OperationalAlert, key)
    if alert is None:
        raise ValueError(f"Unknown operational alert: {key}")
    alert.last_notified_at_utc = now
    session.commit()
