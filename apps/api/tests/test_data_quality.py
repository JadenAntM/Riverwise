from datetime import UTC, datetime, timedelta

from app.data_quality import discharge_gaps, discharge_state

NOW = datetime(2026, 10, 2, 16, tzinfo=UTC)


def test_discharge_gaps_use_observed_cadence_without_inventing_readings() -> None:
    times = [NOW - timedelta(minutes=value) for value in (0, 15, 30, 45, 180, 195)]
    result = discharge_gaps(times)
    assert result.observed_cadence_minutes == 15
    assert result.gap_threshold_minutes == 60
    assert result.gap_count == 1
    assert result.longest_gap_minutes == 135
    assert discharge_gaps([NOW]).observed_cadence_minutes is None
    assert discharge_gaps([NOW]).gap_count == 0


def test_stale_discharge_diagnoses_distinct_failures_and_delayed_publication() -> None:
    old = NOW - timedelta(hours=4)
    recent_attempt = NOW - timedelta(minutes=20)
    assert discharge_state(NOW, NOW - timedelta(minutes=20), None, None, None) == "current"
    assert discharge_state(NOW, None, None, None, None) == "missing"
    assert discharge_state(NOW, NOW + timedelta(minutes=10), None, None, None) == (
        "future_observation"
    )
    assert discharge_state(NOW, old, recent_attempt, "failed", "provider_timeout") == (
        "provider_error"
    )
    assert discharge_state(NOW, old, recent_attempt, "failed", "invalid_payload") == (
        "invalid_payload"
    )
    assert discharge_state(NOW, old, recent_attempt, "failed", "missing_measurement") == (
        "missing_measurement"
    )
    assert discharge_state(NOW, old, recent_attempt, "success", None) == (
        "delayed_publication"
    )
    assert discharge_state(NOW, old, NOW - timedelta(hours=2), "success", None) == "stale"
