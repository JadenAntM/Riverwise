from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

RULES_VERSION = "v1.0.0"
MAX_HYDRO_AGE = timedelta(hours=3)


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
