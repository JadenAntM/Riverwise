from datetime import UTC, datetime, timedelta

import pytest

from app.scoring import (
    CandidateScoreInput,
    ScoreInput,
    ScoreStatus,
    calculate_candidate_score,
    calculate_score,
)

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


def candidate_input(**overrides) -> CandidateScoreInput:
    values = {
        "evaluation_time": NOW,
        "latest_observed_at": NOW - timedelta(minutes=30),
        "seasonal_flow_percentile": 50.0,
        "six_hour_change_pct": 5.0,
        "water_temperature_c": 14.0,
        "water_temperature_observed_at": NOW - timedelta(minutes=15),
    }
    values.update(overrides)
    return CandidateScoreInput(**values)


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


def test_candidate_score_is_versioned_and_complete() -> None:
    result = calculate_candidate_score(candidate_input())
    assert result.score == 10.0
    assert result.confidence == "complete"
    assert result.rules_version == "v1.1.0-shadow"


@pytest.mark.parametrize(
    ("percentile", "points"),
    [(9.9, 0), (10, 2), (25, 4), (75, 4), (75.1, 2), (90, 2), (90.1, 0)],
)
def test_candidate_seasonal_percentile_boundaries(
    percentile: float, points: int
) -> None:
    result = calculate_candidate_score(candidate_input(seasonal_flow_percentile=percentile))
    assert result.components[0].points == points


@pytest.mark.parametrize(
    ("change", "points"),
    [(-25.1, 0), (-25, 1), (-10, 2), (0, 2), (10, 2), (10.1, 1), (25, 1), (25.1, 0)],
)
def test_candidate_flow_stability_boundaries(change: float, points: int) -> None:
    result = calculate_candidate_score(candidate_input(six_hour_change_pct=change))
    assert result.components[1].points == points


@pytest.mark.parametrize(
    ("temperature", "points"),
    [(5.9, 0), (6, 2), (11.9, 2), (12, 4), (16, 4), (16.1, 2), (18, 2), (18.1, 0)],
)
def test_candidate_water_temperature_boundaries(
    temperature: float, points: int
) -> None:
    result = calculate_candidate_score(candidate_input(water_temperature_c=temperature))
    assert result.components[2].points == points


def test_candidate_missing_temperature_is_partial_without_inflating_coverage() -> None:
    result = calculate_candidate_score(
        candidate_input(water_temperature_c=None, water_temperature_observed_at=None)
    )
    assert result.status is ScoreStatus.AVAILABLE
    assert result.confidence == "partial"
    assert result.available_points == 6
    assert result.components[2].points is None


def test_candidate_stale_temperature_is_partial() -> None:
    result = calculate_candidate_score(
        candidate_input(water_temperature_observed_at=NOW - timedelta(hours=3, seconds=1))
    )
    assert result.status is ScoreStatus.AVAILABLE
    assert result.confidence == "partial"
    assert result.available_points == 6
    assert result.components[2].points is None


def test_candidate_requires_seasonal_history() -> None:
    result = calculate_candidate_score(candidate_input(seasonal_flow_percentile=None))
    assert result.status is ScoreStatus.INSUFFICIENT_HISTORY
    assert result.score is None


def test_candidate_stale_hydro_returns_no_score() -> None:
    result = calculate_candidate_score(
        candidate_input(latest_observed_at=NOW - timedelta(hours=3, seconds=1))
    )
    assert result.status is ScoreStatus.STALE
    assert result.score is None
