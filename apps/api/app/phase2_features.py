"""Deterministic, non-forecast context features for the experimental score."""

from datetime import UTC, date, datetime, timedelta
from math import acos, cos, degrees, pi, radians, sin, tan
from statistics import quantiles
from zoneinfo import ZoneInfo

from .models import HydroObservation, WeatherHour

ATLANTIC = ZoneInfo("America/Halifax")
ENDPOINT_TOLERANCE = timedelta(minutes=30)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def flow_change(
    observations: list[HydroObservation], latest: HydroObservation, hours: int
) -> float | None:
    target = _utc(latest.observed_at_utc) - timedelta(hours=hours)
    candidates = [
        row for row in observations if abs(_utc(row.observed_at_utc) - target) <= ENDPOINT_TOLERANCE
    ]
    if not candidates:
        return None
    earlier = min(candidates, key=lambda row: abs(_utc(row.observed_at_utc) - target))
    if earlier.value <= 0.001:
        return None
    return (latest.value - earlier.value) / earlier.value * 100


def precipitation_total(
    weather: list[WeatherHour], evaluation_time: datetime, hours: int
) -> float | None:
    """Open-Meteo's timestamp labels the end of the preceding hourly sum."""
    hour = evaluation_time.replace(minute=0, second=0, microsecond=0)
    values = {
        _utc(row.valid_at_utc): row.precip_mm
        for row in weather
        if row.kind == "historical_or_modelled" and _utc(row.valid_at_utc) <= hour
    }
    window = [values.get(hour - timedelta(hours=offset)) for offset in range(hours)]
    return sum(window) if all(value is not None for value in window) else None


def pressure_change(
    weather: list[WeatherHour], evaluation_time: datetime, hours: int = 6
) -> float | None:
    hour = evaluation_time.replace(minute=0, second=0, microsecond=0)
    values = {
        _utc(row.valid_at_utc): row.pressure_hpa
        for row in weather
        if row.kind == "historical_or_modelled" and _utc(row.valid_at_utc) <= hour
    }
    current, previous = values.get(hour), values.get(hour - timedelta(hours=hours))
    return current - previous if current is not None and previous is not None else None


def rapid_rise_reference(
    observations: list[HydroObservation], latest: HydroObservation
) -> float | None:
    """90th percentile of positive 1h changes in the prior 14 days, excluding latest."""
    prior = [
        row
        for row in observations
        if _utc(latest.observed_at_utc) - timedelta(days=14)
        <= _utc(row.observed_at_utc)
        < _utc(latest.observed_at_utc)
    ]
    if len(prior) < 24 or _utc(prior[-1].observed_at_utc) - _utc(
        prior[0].observed_at_utc
    ) < timedelta(days=7):
        return None
    hourly: dict[datetime, HydroObservation] = {}
    for row in prior:
        hour = _utc(row.observed_at_utc).replace(minute=0, second=0, microsecond=0)
        hourly[hour] = row
    sampled = list(hourly.values())
    rises = [
        change
        for index, row in enumerate(sampled)
        if (change := flow_change(sampled[:index], row, 1)) is not None and change > 0
    ]
    if len(rises) < 24:
        return None
    # Inclusive quartile method avoids a single extreme defining the reference.
    return quantiles(rises, n=10, method="inclusive")[8]


def monthly_percentile(
    daily: list[HydroObservation], evaluation_time: datetime, latest_flow: float
) -> tuple[float | None, int, int]:
    rows = [
        row
        for row in daily
        if _utc(row.observed_at_utc).month == evaluation_time.month
        and _utc(row.observed_at_utc).year < evaluation_time.year
    ]
    years = len({_utc(row.observed_at_utc).year for row in rows})
    if len(rows) < 21 or years < 3:
        return None, len(rows), years
    below = sum(row.value < latest_flow for row in rows)
    equal = sum(row.value == latest_flow for row in rows)
    return (below + equal / 2) / len(rows) * 100, len(rows), years


def solar_times(day: date, latitude: float, longitude: float) -> tuple[datetime, datetime]:
    """Approximate apparent sunrise/sunset using NOAA's equation of time and zenith."""
    ordinal = day.timetuple().tm_yday
    gamma = 2 * pi / 365 * (ordinal - 1)
    equation = 229.18 * (
        0.000075
        + 0.001868 * cos(gamma)
        - 0.032077 * sin(gamma)
        - 0.014615 * cos(2 * gamma)
        - 0.040849 * sin(2 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * cos(gamma)
        + 0.070257 * sin(gamma)
        - 0.006758 * cos(2 * gamma)
        + 0.000907 * sin(2 * gamma)
        - 0.002697 * cos(3 * gamma)
        + 0.00148 * sin(3 * gamma)
    )
    lat = radians(latitude)
    angle = degrees(
        acos(cos(radians(90.833)) / (cos(lat) * cos(declination)) - tan(lat) * tan(declination))
    )
    midnight = datetime(day.year, day.month, day.day, tzinfo=UTC)
    sunrise = midnight + timedelta(minutes=720 - 4 * (longitude + angle) - equation)
    sunset = midnight + timedelta(minutes=720 - 4 * (longitude - angle) - equation)
    return sunrise, sunset


def daylight_context(evaluation_time: datetime, latitude: float, longitude: float) -> dict:
    local_date = evaluation_time.astimezone(ATLANTIC).date()
    sunrise, sunset = solar_times(local_date, latitude, longitude)
    return {
        "sunrise_at_utc": sunrise.isoformat(),
        "sunset_at_utc": sunset.isoformat(),
        "is_daylight": sunrise <= evaluation_time < sunset,
        "daylight_minutes": round((sunset - sunrise).total_seconds() / 60),
    }
