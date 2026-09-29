from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import HydroObservation, WeatherHour
from app.phase2_features import (
    daylight_context,
    flow_change,
    monthly_percentile,
    precipitation_total,
    pressure_change,
    rapid_rise_reference,
)
from app.scoring import ExperimentScoreInput, ScoreStatus, calculate_experiment_score
from app.service import score_station

NOW = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)


def hydro(time: datetime, value: float, parameter: str = "discharge") -> HydroObservation:
    return HydroObservation(
        station_id="01FB001",
        observed_at_utc=time,
        parameter=parameter,
        value=value,
        unit="m³/s",
        ingested_at_utc=NOW,
    )


def weather(
    time: datetime,
    precip: float | None,
    pressure: float | None = 1000,
    kind: str = "historical_or_modelled",
) -> WeatherHour:
    return WeatherHour(
        station_id="01FB001",
        valid_at_utc=time,
        kind=kind,
        precip_mm=precip,
        pressure_hpa=pressure,
        ingested_at_utc=NOW,
    )


def experiment_input(**overrides) -> ExperimentScoreInput:
    values = {
        "evaluation_time": NOW,
        "latest_observed_at": NOW - timedelta(minutes=10),
        "monthly_flow_percentile": 50,
        "one_hour_change_pct": 0,
        "six_hour_change_pct": 0,
        "twenty_four_hour_change_pct": 0,
        "precipitation_6h_mm": 2,
        "precipitation_24h_mm": 5,
        "precipitation_72h_mm": 10,
        "rapid_rise_threshold_pct": 15,
        "water_temperature_c": 14,
        "water_temperature_observed_at": NOW - timedelta(minutes=10),
    }
    values.update(overrides)
    return ExperimentScoreInput(**values)


def test_complete_v12_score_and_explanation() -> None:
    result = calculate_experiment_score(experiment_input())
    assert result.score == 10
    assert result.available_points == 10
    assert result.rules_version == "v1.2.0-shadow"
    assert [(item.key, item.points) for item in result.components] == [
        ("monthly_flow_percentile", 3),
        ("1h_trend", 1),
        ("6h_trend", 1),
        ("precipitation_6h", 1),
        ("precipitation_24h", 1),
        ("precipitation_72h", 1),
        ("water_temperature", 2),
        ("rapid_rise_penalty", 0),
    ]


@pytest.mark.parametrize(
    "percentile,points", [(9.9, 0), (10, 1), (25, 3), (75, 3), (75.1, 1), (90, 1), (90.1, 0)]
)
def test_station_month_percentile_boundaries(percentile: float, points: int) -> None:
    result = calculate_experiment_score(experiment_input(monthly_flow_percentile=percentile))
    assert result.components[0].points == points


def test_rapid_rise_penalty_and_partial_coverage() -> None:
    result = calculate_experiment_score(
        experiment_input(
            one_hour_change_pct=20,
            precipitation_72h_mm=None,
            water_temperature_c=None,
            water_temperature_observed_at=None,
        )
    )
    assert result.components[-1].points == -1
    assert result.earned_points == 5
    assert result.available_points == 7
    assert result.confidence == "partial"


def test_v12_missing_and_stale_states() -> None:
    assert (
        calculate_experiment_score(
            experiment_input(
                latest_observed_at=NOW - timedelta(hours=3, seconds=1),
            )
        ).status
        is ScoreStatus.STALE
    )
    assert (
        calculate_experiment_score(
            experiment_input(
                monthly_flow_percentile=None,
            )
        ).status
        is ScoreStatus.INSUFFICIENT_HISTORY
    )
    assert (
        calculate_experiment_score(
            experiment_input(
                precipitation_6h_mm=None,
                precipitation_24h_mm=None,
                precipitation_72h_mm=None,
            )
        ).status
        is ScoreStatus.INSUFFICIENT_DATA
    )


def test_hourly_precipitation_uses_complete_preceding_hours_and_no_forecast() -> None:
    hour = NOW.replace(minute=0)
    rows = [weather(hour - timedelta(hours=offset), 1.0) for offset in range(72)]
    rows.append(weather(hour + timedelta(hours=1), 99.0, kind="forecast"))
    assert precipitation_total(rows, NOW, 6) == 6
    assert precipitation_total(rows, NOW, 24) == 24
    assert precipitation_total(rows, NOW, 72) == 72
    rows.pop(30)
    assert precipitation_total(rows, NOW, 24) == 24
    assert precipitation_total(rows, NOW, 72) is None


def test_pressure_trend_is_change_not_absolute_value() -> None:
    hour = NOW.replace(minute=0)
    assert (
        pressure_change([weather(hour, 0, 1003), weather(hour - timedelta(hours=6), 0, 1007)], NOW)
        == -4
    )
    assert pressure_change([weather(hour, 0, 1003)], NOW) is None


def test_flow_trends_require_comparable_endpoints_and_nonzero_prior() -> None:
    latest = hydro(NOW, 11)
    rows = [hydro(NOW - timedelta(hours=1, minutes=29), 10), latest]
    assert flow_change(rows, latest, 1) == pytest.approx(10)
    assert flow_change(rows, latest, 6) is None
    rows[0] = hydro(NOW - timedelta(hours=1, minutes=31), 10)
    assert flow_change(rows, latest, 1) is None
    rows[0] = hydro(NOW - timedelta(hours=1), 0)
    assert flow_change(rows, latest, 1) is None


def test_monthly_reference_excludes_current_year_and_requires_three_years() -> None:
    rows = [
        hydro(datetime(year, 9, day, tzinfo=UTC), float(day), "daily_discharge")
        for year in (2023, 2024, 2025, 2026)
        for day in range(1, 8)
    ]
    percentile, count, years = monthly_percentile(rows, NOW, 4)
    assert (count, years) == (21, 3)
    # The 2026 rows are excluded; ties receive a half rank.
    assert percentile == pytest.approx(50)


def test_rapid_rise_reference_requires_sufficient_positive_history() -> None:
    rows = [hydro(NOW - timedelta(hours=240 - hour), 10 + hour * 0.01) for hour in range(241)]
    assert rapid_rise_reference(rows, rows[-1]) is not None
    assert rapid_rise_reference(rows[:20], rows[19]) is None


def test_solar_context_is_local_day_and_changes_with_season() -> None:
    summer = daylight_context(datetime(2026, 6, 21, 16, tzinfo=UTC), 45.0, -63.0)
    winter = daylight_context(datetime(2026, 12, 21, 16, tzinfo=UTC), 45.0, -63.0)
    assert summer["is_daylight"] is True
    assert summer["daylight_minutes"] > winter["daylight_minutes"]
    assert summer["sunrise_at_utc"] < summer["sunset_at_utc"]


def test_historical_replay_does_not_read_future_discharge(session: Session) -> None:
    future = hydro(NOW + timedelta(hours=1), 999)
    session.add(future)
    session.commit()

    _, context = score_station(session, "01FB001", NOW)
    assert context["latest"].observed_at_utc.replace(tzinfo=UTC) <= NOW
    assert context["latest"].value != 999
