from datetime import UTC, datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import HydroObservation, IngestRun, Station, WeatherHour
from .scoring import (
    CandidateScoreInput,
    ScoreInput,
    ScoreResult,
    calculate_candidate_score,
    calculate_score,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def hydro_for_station(
    session: Session, station_id: str, since: datetime | None = None
) -> list[HydroObservation]:
    query = select(HydroObservation).where(
        HydroObservation.station_id == station_id,
        HydroObservation.parameter == "discharge",
    )
    if since:
        query = query.where(HydroObservation.observed_at_utc >= since)
    return list(session.scalars(query.order_by(HydroObservation.observed_at_utc)).all())


def weather_for_station(session: Session, station_id: str, since: datetime) -> list[WeatherHour]:
    query = (
        select(WeatherHour)
        .where(
            WeatherHour.station_id == station_id,
            WeatherHour.kind == "historical_or_modelled",
            WeatherHour.valid_at_utc >= since,
        )
        .order_by(WeatherHour.valid_at_utc)
    )
    return list(session.scalars(query).all())


def _nearest(
    observations: list[HydroObservation], target: datetime, tolerance: timedelta
) -> HydroObservation | None:
    candidates = [
        obs for obs in observations if abs(_aware(obs.observed_at_utc) - target) <= tolerance
    ]
    return min(candidates, key=lambda obs: abs(_aware(obs.observed_at_utc) - target), default=None)


def score_station(
    session: Session, station_id: str, evaluation_time: datetime
) -> tuple[ScoreResult | None, dict]:
    observations = hydro_for_station(session, station_id, evaluation_time - timedelta(days=15))
    if not observations:
        return None, {"baseline_median": None, "six_hour_change_pct": None, "latest": None}
    latest = observations[-1]
    latest_time = _aware(latest.observed_at_utc)
    prior = [obs for obs in observations if _aware(obs.observed_at_utc) < latest_time]
    span = (
        _aware(prior[-1].observed_at_utc) - _aware(prior[0].observed_at_utc)
        if len(prior) >= 2
        else timedelta(0)
    )
    baseline = (
        median(obs.value for obs in prior)
        if len(prior) >= 24 and span >= timedelta(days=7)
        else None
    )
    six_hour = _nearest(observations, latest_time - timedelta(hours=6), timedelta(minutes=30))
    change = None
    if six_hour and six_hour.value > 0.001:
        change = (latest.value - six_hour.value) / six_hour.value * 100

    weather = weather_for_station(session, station_id, evaluation_time - timedelta(hours=13))
    hour = evaluation_time.replace(minute=0, second=0, microsecond=0)
    precip_values = [
        item.precip_mm
        for item in weather
        if hour - timedelta(hours=12) <= _aware(item.valid_at_utc) < hour
        and item.precip_mm is not None
    ]
    precip = sum(precip_values) if len(precip_values) == 12 else None
    cloud_row = min(
        (item for item in weather if abs(_aware(item.valid_at_utc) - hour) <= timedelta(hours=1)),
        key=lambda item: abs(_aware(item.valid_at_utc) - hour),
        default=None,
    )
    cloud = cloud_row.cloud_cover_pct if cloud_row else None

    result = calculate_score(
        ScoreInput(evaluation_time, latest_time, latest.value, baseline, change, precip, cloud)
    )
    return result, {
        "baseline_median": baseline,
        "six_hour_change_pct": change,
        "latest": latest,
        "current_weather": cloud_row,
        "precipitation_12h_mm": precip,
    }


def _seasonal_flow_context(
    session: Session, station_id: str, target_time: datetime, latest_flow: float
) -> dict:
    daily = list(
        session.scalars(
            select(HydroObservation)
            .where(
                HydroObservation.station_id == station_id,
                HydroObservation.parameter == "daily_discharge",
            )
            .order_by(HydroObservation.observed_at_utc)
        ).all()
    )
    target = datetime(2000, target_time.month, target_time.day, tzinfo=UTC)
    seasonal = []
    years: set[int] = set()
    for observation in daily:
        observed_at = _aware(observation.observed_at_utc)
        if observed_at.year >= target_time.year:
            continue
        candidate = datetime(2000, observed_at.month, observed_at.day, tzinfo=UTC)
        difference = abs((candidate - target).days)
        if min(difference, 366 - difference) <= 7:
            seasonal.append(observation.value)
            years.add(observed_at.year)

    if len(seasonal) < 21 or len(years) < 3:
        return {
            "seasonal_flow_percentile": None,
            "seasonal_median_m3s": None,
            "seasonal_sample_count": len(seasonal),
            "seasonal_year_count": len(years),
        }

    below = sum(value < latest_flow for value in seasonal)
    equal = sum(value == latest_flow for value in seasonal)
    return {
        "seasonal_flow_percentile": (below + 0.5 * equal) / len(seasonal) * 100,
        "seasonal_median_m3s": median(seasonal),
        "seasonal_sample_count": len(seasonal),
        "seasonal_year_count": len(years),
    }


def candidate_score_station(
    session: Session,
    station_id: str,
    evaluation_time: datetime,
    base_context: dict | None = None,
) -> tuple[ScoreResult | None, dict]:
    if base_context is None:
        _, base_context = score_station(session, station_id, evaluation_time)
    latest = base_context.get("latest")
    if latest is None:
        return None, {
            **base_context,
            "latest_water_temperature": None,
            "seasonal_flow_percentile": None,
            "seasonal_median_m3s": None,
            "seasonal_sample_count": 0,
            "seasonal_year_count": 0,
        }

    temperature = session.scalar(
        select(HydroObservation)
        .where(
            HydroObservation.station_id == station_id,
            HydroObservation.parameter == "water_temperature",
            HydroObservation.observed_at_utc <= evaluation_time,
        )
        .order_by(HydroObservation.observed_at_utc.desc())
        .limit(1)
    )
    seasonal = _seasonal_flow_context(
        session,
        station_id,
        _aware(latest.observed_at_utc),
        latest.value,
    )
    result = calculate_candidate_score(
        CandidateScoreInput(
            evaluation_time=evaluation_time,
            latest_observed_at=_aware(latest.observed_at_utc),
            seasonal_flow_percentile=seasonal["seasonal_flow_percentile"],
            six_hour_change_pct=base_context.get("six_hour_change_pct"),
            water_temperature_c=temperature.value if temperature else None,
            water_temperature_observed_at=(
                _aware(temperature.observed_at_utc) if temperature else None
            ),
        )
    )
    return result, {
        **base_context,
        **seasonal,
        "latest_water_temperature": temperature,
    }


def last_ingest(session: Session) -> IngestRun | None:
    return session.scalar(select(IngestRun).order_by(IngestRun.started_at_utc.desc()).limit(1))


def ingestion_overview(session: Session, evaluation_time: datetime) -> dict:
    runs = list(
        session.scalars(
            select(IngestRun)
            .where(IngestRun.station_id.is_not(None))
            .order_by(IngestRun.started_at_utc.desc())
            .limit(250)
        ).all()
    )
    latest: dict[tuple[str, str | None], IngestRun] = {}
    last_success: dict[tuple[str, str | None], datetime] = {}
    for run in runs:
        key = (run.source, run.station_id)
        latest.setdefault(key, run)
        if run.status == "success" and key not in last_success:
            last_success[key] = _aware(run.started_at_utc)

    source_rows = [
        {
            "source": run.source,
            "station_id": run.station_id,
            "status": run.status,
            "last_attempt_at_utc": _aware(run.started_at_utc),
            "last_success_at_utc": last_success.get(key),
            "fetched_count": run.fetched_count,
            "upserted_count": run.upserted_count,
            "duration_ms": run.duration_ms,
            "error": run.error,
        }
        for key, run in latest.items()
    ]
    source_rows.sort(key=lambda item: (item["source"], item["station_id"] or ""))

    station_rows = []
    stations = list(session.scalars(select(Station).order_by(Station.display_order)).all())
    for station in stations:
        latest_observation = session.scalar(
            select(HydroObservation)
            .where(
                HydroObservation.station_id == station.id,
                HydroObservation.parameter == "discharge",
            )
            .order_by(HydroObservation.observed_at_utc.desc())
            .limit(1)
        )
        observed_at = _aware(latest_observation.observed_at_utc) if latest_observation else None
        station_rows.append(
            {
                "id": station.id,
                "name": station.name,
                "latest_observed_at_utc": observed_at,
                "age_minutes": (
                    max(0, int((evaluation_time - observed_at).total_seconds() / 60))
                    if observed_at
                    else None
                ),
            }
        )
    return {"sources": source_rows, "stations": station_rows}
