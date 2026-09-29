from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

RULES_VERSION = "v1.0.0"
CANDIDATE_RULES_VERSION = "v1.1.0-shadow"
EXPERIMENT_RULES_VERSION = "v1.2.0-shadow"
MAX_HYDRO_AGE = timedelta(hours=3)
MAX_TEMPERATURE_AGE = timedelta(hours=3)


class ScoreStatus(StrEnum):
    AVAILABLE = "available"
    STALE = "stale"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class ScoreInput:
    evaluation_time: datetime
    latest_observed_at: datetime
    latest_flow: float
    baseline_median: float | None
    six_hour_change_pct: float | None
    precipitation_12h_mm: float | None
    cloud_cover_pct: float | None


@dataclass(frozen=True)
class CandidateScoreInput:
    evaluation_time: datetime
    latest_observed_at: datetime
    seasonal_flow_percentile: float | None
    six_hour_change_pct: float | None
    water_temperature_c: float | None
    water_temperature_observed_at: datetime | None


@dataclass(frozen=True)
class ExperimentScoreInput:
    evaluation_time: datetime
    latest_observed_at: datetime
    monthly_flow_percentile: float | None
    one_hour_change_pct: float | None
    six_hour_change_pct: float | None
    twenty_four_hour_change_pct: float | None
    precipitation_6h_mm: float | None
    precipitation_24h_mm: float | None
    precipitation_72h_mm: float | None
    rapid_rise_threshold_pct: float | None
    water_temperature_c: float | None
    water_temperature_observed_at: datetime | None


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    points: int | None
    maximum: int
    reason: str


@dataclass(frozen=True)
class ScoreResult:
    score: float | None
    status: ScoreStatus
    confidence: str
    earned_points: int
    available_points: int
    components: tuple[Component, ...]
    rules_version: str = RULES_VERSION

    @property
    def reasons(self) -> list[str]:
        return [component.reason for component in self.components]


def _flow_component(latest: float, baseline: float) -> Component:
    ratio = latest / baseline
    if 0.8 <= ratio <= 1.5:
        points = 4
        reason = "Flow is within 80–150% of this station's 14-day median."
    elif 0.5 <= ratio < 0.8 or 1.5 < ratio <= 2.0:
        points = 2
        reason = "Flow is moderately outside this station's recent range."
    else:
        points = 0
        reason = "Flow is well outside this station's recent range."
    return Component("flow_ratio", "Flow vs 14-day median", points, 4, reason)


def _change_component(change: float) -> Component:
    if -20 <= change <= 0:
        points = 2
        reason = "Flow has been stable or gently falling over six hours."
    elif 0 < change <= 20:
        points = 1
        reason = "Flow has risen by no more than 20% over six hours."
    else:
        points = 0
        reason = "Flow has moved by more than 20% over six hours."
    return Component("six_hour_change", "6-hour flow change", points, 2, reason)


def _precip_component(precipitation: float | None) -> Component:
    if precipitation is None:
        return Component(
            "precipitation",
            "Previous 12-hour precipitation",
            None,
            2,
            "Recent precipitation is unavailable.",
        )
    if 1 <= precipitation <= 10:
        points = 2
        reason = (
            f"{precipitation:.1f} mm of nearby modeled precipitation fell in the previous 12 hours."
        )
    elif 0 <= precipitation < 1:
        points = 1
        reason = "Little nearby modeled precipitation fell in the previous 12 hours."
    else:
        points = 0
        reason = f"Nearby modeled precipitation was high at {precipitation:.1f} mm over 12 hours."
    return Component("precipitation", "Previous 12-hour precipitation", points, 2, reason)


def _cloud_component(cloud_cover: float | None) -> Component:
    if cloud_cover is None:
        return Component(
            "cloud_cover",
            "Current cloud cover",
            None,
            2,
            "Current nearby cloud cover is unavailable.",
        )
    if cloud_cover >= 70:
        points = 2
        reason = f"Nearby modeled cloud cover is high at {cloud_cover:.0f}%."
    elif cloud_cover >= 30:
        points = 1
        reason = f"Nearby modeled cloud cover is moderate at {cloud_cover:.0f}%."
    else:
        points = 0
        reason = f"Nearby modeled cloud cover is low at {cloud_cover:.0f}%."
    return Component("cloud_cover", "Current cloud cover", points, 2, reason)


def calculate_score(data: ScoreInput) -> ScoreResult:
    if data.evaluation_time - data.latest_observed_at > MAX_HYDRO_AGE:
        return ScoreResult(None, ScoreStatus.STALE, "unavailable", 0, 0, ())
    if not data.baseline_median or data.baseline_median <= 0 or data.six_hour_change_pct is None:
        return ScoreResult(None, ScoreStatus.INSUFFICIENT_HISTORY, "unavailable", 0, 0, ())

    weather = (
        _precip_component(data.precipitation_12h_mm),
        _cloud_component(data.cloud_cover_pct),
    )
    if all(component.points is None for component in weather):
        return ScoreResult(None, ScoreStatus.INSUFFICIENT_DATA, "unavailable", 0, 0, weather)

    components = (
        _flow_component(data.latest_flow, data.baseline_median),
        _change_component(data.six_hour_change_pct),
        *weather,
    )
    available = sum(component.maximum for component in components if component.points is not None)
    earned = sum(component.points or 0 for component in components)
    score = round(earned / available * 10, 1)
    confidence = "complete" if available == 10 else "partial"
    return ScoreResult(score, ScoreStatus.AVAILABLE, confidence, earned, available, components)


def _seasonal_flow_component(percentile: float) -> Component:
    if 25 <= percentile <= 75:
        points = 4
        reason = f"Flow is near its seasonal middle range at the {percentile:.0f}th percentile."
    elif 10 <= percentile < 25 or 75 < percentile <= 90:
        points = 2
        reason = (
            f"Flow is moderately outside its seasonal range at the {percentile:.0f}th percentile."
        )
    else:
        points = 0
        reason = f"Flow is near a seasonal extreme at the {percentile:.0f}th percentile."
    return Component("seasonal_flow", "Seasonal flow percentile", points, 4, reason)


def _candidate_change_component(change: float) -> Component:
    magnitude = abs(change)
    if magnitude <= 10:
        points = 2
        reason = "Flow has changed by no more than 10% over six hours."
    elif magnitude <= 25:
        points = 1
        reason = "Flow has changed by 10–25% over six hours."
    else:
        points = 0
        reason = "Flow has changed by more than 25% over six hours."
    return Component("six_hour_stability", "6-hour flow stability", points, 2, reason)


def _water_temperature_component(data: CandidateScoreInput) -> Component:
    if data.water_temperature_c is None or data.water_temperature_observed_at is None:
        return Component(
            "water_temperature",
            "Measured water temperature",
            None,
            4,
            "Measured water temperature is unavailable at this station.",
        )
    if data.evaluation_time - data.water_temperature_observed_at > MAX_TEMPERATURE_AGE:
        return Component(
            "water_temperature",
            "Measured water temperature",
            None,
            4,
            "The latest measured water temperature is more than three hours old.",
        )
    temperature = data.water_temperature_c
    if 12 <= temperature <= 16:
        points = 4
        reason = (
            "Measured water temperature is within the 12–16°C candidate band at "
            f"{temperature:.1f}°C."
        )
    elif 6 <= temperature < 12 or 16 < temperature <= 18:
        points = 2
        reason = (
            "Measured water temperature is outside the central candidate band at "
            f"{temperature:.1f}°C."
        )
    else:
        points = 0
        reason = (
            f"Measured water temperature is well outside the candidate band at {temperature:.1f}°C."
        )
    return Component("water_temperature", "Measured water temperature", points, 4, reason)


def calculate_candidate_score(data: CandidateScoreInput) -> ScoreResult:
    if data.evaluation_time - data.latest_observed_at > MAX_HYDRO_AGE:
        return ScoreResult(
            None,
            ScoreStatus.STALE,
            "unavailable",
            0,
            0,
            (),
            CANDIDATE_RULES_VERSION,
        )
    if data.seasonal_flow_percentile is None or data.six_hour_change_pct is None:
        return ScoreResult(
            None,
            ScoreStatus.INSUFFICIENT_HISTORY,
            "unavailable",
            0,
            0,
            (),
            CANDIDATE_RULES_VERSION,
        )

    components = (
        _seasonal_flow_component(data.seasonal_flow_percentile),
        _candidate_change_component(data.six_hour_change_pct),
        _water_temperature_component(data),
    )
    available = sum(component.maximum for component in components if component.points is not None)
    earned = sum(component.points or 0 for component in components)
    score = round(earned / available * 10, 1)
    confidence = "complete" if available == 10 else "partial"
    return ScoreResult(
        score,
        ScoreStatus.AVAILABLE,
        confidence,
        earned,
        available,
        components,
        CANDIDATE_RULES_VERSION,
    )


def _experiment_flow_component(percentile: float) -> Component:
    if 25 <= percentile <= 75:
        points = 3
    elif 10 <= percentile < 25 or 75 < percentile <= 90:
        points = 1
    else:
        points = 0
    return Component(
        "monthly_flow_percentile",
        "Station-month flow percentile",
        points,
        3,
        f"Flow is at the {percentile:.0f}th percentile of this station's "
        "prior-year daily values for this month.",
    )


def _experiment_trend_component(change: float | None, hours: int) -> Component:
    if change is None:
        return Component(
            f"{hours}h_trend",
            f"{hours}-hour flow trend",
            None,
            1,
            f"A comparable {hours}-hour discharge reading is unavailable.",
        )
    lower, upper = (-5, 5) if hours == 1 else (-20, 10)
    points = int(lower <= change <= upper)
    direction = "rising" if change > 1 else "falling" if change < -1 else "stable"
    return Component(
        f"{hours}h_trend",
        f"{hours}-hour flow trend",
        points,
        1,
        f"Measured discharge is {direction} ({change:+.1f}% over {hours} hours).",
    )


def _experiment_rain_component(value: float | None, hours: int) -> Component:
    if value is None:
        return Component(
            f"precipitation_{hours}h",
            f"Previous {hours}-hour precipitation",
            None,
            1,
            f"The full {hours}-hour non-forecast precipitation window is unavailable.",
        )
    lower, upper = {6: (0.5, 5), 24: (1, 15), 72: (2, 30)}[hours]
    return Component(
        f"precipitation_{hours}h",
        f"Previous {hours}-hour precipitation",
        int(lower <= value <= upper),
        1,
        f"Nearby modeled precipitation totals {value:.1f} mm over {hours} complete hours.",
    )


def _experiment_temperature_component(data: ExperimentScoreInput) -> Component:
    candidate = _water_temperature_component(
        CandidateScoreInput(
            data.evaluation_time,
            data.latest_observed_at,
            None,
            None,
            data.water_temperature_c,
            data.water_temperature_observed_at,
        )
    )
    points = None if candidate.points is None else candidate.points // 2
    return Component(candidate.key, candidate.label, points, 2, candidate.reason)


def calculate_experiment_score(data: ExperimentScoreInput) -> ScoreResult:
    """A provisional conditions comparison; daylight and pressure remain context only."""
    version = EXPERIMENT_RULES_VERSION
    if data.evaluation_time - data.latest_observed_at > MAX_HYDRO_AGE:
        return ScoreResult(None, ScoreStatus.STALE, "unavailable", 0, 0, (), version)
    if data.monthly_flow_percentile is None or data.six_hour_change_pct is None:
        return ScoreResult(None, ScoreStatus.INSUFFICIENT_HISTORY, "unavailable", 0, 0, (), version)

    components = (
        _experiment_flow_component(data.monthly_flow_percentile),
        _experiment_trend_component(data.one_hour_change_pct, 1),
        _experiment_trend_component(data.six_hour_change_pct, 6),
        _experiment_rain_component(data.precipitation_6h_mm, 6),
        _experiment_rain_component(data.precipitation_24h_mm, 24),
        _experiment_rain_component(data.precipitation_72h_mm, 72),
        _experiment_temperature_component(data),
    )
    weather = components[3:6]
    if all(component.points is None for component in weather):
        return ScoreResult(
            None, ScoreStatus.INSUFFICIENT_DATA, "unavailable", 0, 0, components, version
        )

    penalty = 0
    if (
        data.one_hour_change_pct is not None
        and data.rapid_rise_threshold_pct is not None
        and data.one_hour_change_pct > data.rapid_rise_threshold_pct
    ):
        penalty = -1
    components += (
        Component(
            "rapid_rise_penalty",
            "Unusually rapid station-specific rise",
            penalty,
            0,
            "One-hour discharge rise exceeds this station's recent 90th-percentile rise rate."
            if penalty
            else "No unusually rapid one-hour rise was detected, or the reference is unavailable.",
        ),
    )
    available = sum(component.maximum for component in components if component.points is not None)
    earned = max(0, sum(component.points or 0 for component in components))
    score = round(earned / available * 10, 1)
    return ScoreResult(
        score,
        ScoreStatus.AVAILABLE,
        "complete" if available == 10 else "partial",
        earned,
        available,
        components,
        version,
    )
