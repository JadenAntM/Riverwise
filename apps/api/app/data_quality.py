"""Descriptive station coverage and ingestion diagnostics, not score rules."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class DischargeGaps:
    observed_cadence_minutes: float | None
    gap_threshold_minutes: float | None
    gap_count: int
    longest_gap_minutes: float | None


def discharge_gaps(observed_times: list[datetime]) -> DischargeGaps:
    """Flag gaps relative to observed cadence, with a one-hour minimum threshold."""
    times = sorted({_aware(value) for value in observed_times})
    intervals = [
        (right - left).total_seconds() / 60
        for left, right in zip(times, times[1:])
    ]
    if not intervals:
        return DischargeGaps(None, None, 0, None)
    cadence = float(median(intervals))
    threshold = max(60.0, cadence * 3)
    gaps = [interval for interval in intervals if interval > threshold]
    return DischargeGaps(cadence, threshold, len(gaps), max(gaps, default=None))


def discharge_state(
    now: datetime,
    observed_at: datetime | None,
    last_run_at: datetime | None,
    last_run_status: str | None,
    last_error_kind: str | None,
) -> str:
    """Explain stale readings without equating a successful fetch with a new measurement."""
    if observed_at is not None and _aware(observed_at) > now + timedelta(minutes=5):
        return "future_observation"
    if observed_at is not None and now - _aware(observed_at) <= timedelta(hours=3):
        return "current"
    if last_run_status == "failed":
        if last_error_kind in {"provider_timeout", "provider_http", "provider_network"}:
            return "provider_error"
        if last_error_kind == "invalid_payload":
            return "invalid_payload"
        if last_error_kind == "missing_measurement":
            return "missing_measurement"
    if observed_at is None:
        return "missing"
    if (
        last_run_status == "success"
        and last_run_at is not None
        and now - _aware(last_run_at) <= timedelta(minutes=90)
    ):
        return "delayed_publication"
    return "stale"
