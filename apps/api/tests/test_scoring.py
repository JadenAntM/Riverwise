from datetime import UTC, datetime, timedelta

import pytest

from app.scoring import ScoreInput, ScoreStatus, calculate_score

NOW = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)


def score_input(**overrides) -> ScoreInput:
    values = {
        "evaluation_time": NOW,
        "latest_observed_at": NOW - timedelta(minutes=30),
        "latest_flow": 10.0,
        "baseline_median": 10.0,
        "six_hour_change_pct": -5.0,
        "precipitation_12h_mm": 3.0,
        "cloud_cover_pct": 80.0,
    }
    values.update(overrides)
    return ScoreInput(**values)


def test_complete_score_exposes_components_and_version() -> None:
    result = calculate_score(score_input())
    assert result.status is ScoreStatus.AVAILABLE
    assert result.confidence == "complete"
    assert result.score == 10.0
    assert result.available_points == 10
    assert result.rules_version == "v1.0.0"


@pytest.mark.parametrize(
    ("ratio", "points"),
    [(0.49, 0), (0.5, 2), (0.8, 4), (1.5, 4), (1.51, 2), (2.0, 2), (2.01, 0)],
)
def test_flow_ratio_boundaries(ratio: float, points: int) -> None:
    result = calculate_score(score_input(latest_flow=ratio * 10))
    assert result.components[0].points == points


@pytest.mark.parametrize(
    ("change", "points"),
    [(-20.01, 0), (-20, 2), (0, 2), (0.01, 1), (20, 1), (20.01, 0)],
)
def test_six_hour_change_boundaries(change: float, points: int) -> None:
    result = calculate_score(score_input(six_hour_change_pct=change))
    assert result.components[1].points == points


def test_stale_hydro_returns_no_score() -> None:
    result = calculate_score(score_input(latest_observed_at=NOW - timedelta(hours=3, seconds=1)))
    assert result.status is ScoreStatus.STALE
    assert result.score is None


def test_partial_weather_is_rescaled_and_labeled() -> None:
    result = calculate_score(score_input(cloud_cover_pct=None))
    assert result.status is ScoreStatus.AVAILABLE
    assert result.confidence == "partial"
    assert result.available_points == 8
    assert result.score == 10.0


def test_missing_weather_returns_no_score() -> None:
    result = calculate_score(score_input(cloud_cover_pct=None, precipitation_12h_mm=None))
    assert result.status is ScoreStatus.INSUFFICIENT_DATA
    assert result.score is None


def test_missing_baseline_returns_no_score() -> None:
    result = calculate_score(score_input(baseline_median=None))
    assert result.status is ScoreStatus.INSUFFICIENT_HISTORY
