from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Station
from .schemas import (
    HealthResponse,
    HistoryResponse,
    IngestionStatusOut,
    ObservationOut,
    ScoreComparisonOut,
    ScoreOut,
    StationDetail,
    StationSummary,
    WeatherOut,
)
from .scoring import CANDIDATE_RULES_VERSION, RULES_VERSION, ScoreResult
from .service import (
    candidate_score_station,
    hydro_for_station,
    ingestion_overview,
    last_ingest,
    score_station,
)

app = FastAPI(
    title="Riverwise API",
    version="0.1.0",
    description="Read-only river conditions API with transparent data freshness and scoring.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _score_out(
    result: ScoreResult | None, empty_rules_version: str = RULES_VERSION
) -> ScoreOut:
    if result is None:
        return ScoreOut(
            value=None,
            status="insufficient_data",
            confidence="unavailable",
            earned_points=0,
            available_points=0,
            rules_version=empty_rules_version,
            reasons=["No discharge observations are available."],
            components=[],
        )
    reasons = result.reasons or [
        {
            "stale": "The latest discharge observation is more than three hours old.",
            "insufficient_history": (
                "At least 24 readings spanning seven days and a six-hour comparison are required."
            ),
            "insufficient_data": "At least one non-forecast weather component is required.",
        }.get(result.status.value, "A score is not currently available.")
    ]
    return ScoreOut(
        value=result.score,
        status=result.status.value,
        confidence=result.confidence,
        earned_points=result.earned_points,
        available_points=result.available_points,
        rules_version=result.rules_version,
        reasons=reasons,
        components=[component.__dict__ for component in result.components],
    )


def _station_summary(session: Session, station: Station, now: datetime) -> StationSummary:
    result, context = score_station(session, station.id, now)
    latest = context.get("latest")
    return StationSummary(
        id=station.id,
        name=station.name,
        latitude=station.latitude,
        longitude=station.longitude,
        province=station.province,
        source_url=station.source_url,
        latest_flow=ObservationOut.model_validate(latest) if latest else None,
        score=_score_out(result),
    )


@app.get("/health", response_model=HealthResponse)
def health(session: Session = Depends(get_db)) -> HealthResponse:
    session.execute(text("SELECT 1"))
    run = last_ingest(session)
    return HealthResponse(
        status="ok",
        database="ok",
        last_ingest_status=run.status if run else None,
        last_ingest_at_utc=run.started_at_utc if run else None,
    )


@app.get("/api/v1/stations", response_model=list[StationSummary])
def stations(session: Session = Depends(get_db)) -> list[StationSummary]:
    now = datetime.now(UTC)
    items = list(
        session.scalars(select(Station).order_by(Station.display_order, Station.name)).all()
    )
    summaries = [_station_summary(session, station, now) for station in items]
    confidence_rank = {"complete": 0, "partial": 1, "unavailable": 2}
    return sorted(
        summaries,
        key=lambda item: (
            confidence_rank.get(item.score.confidence, 3),
            -(item.score.value if item.score.value is not None else -1),
            item.name,
        ),
    )


@app.get("/api/v1/ingestion", response_model=IngestionStatusOut)
def ingestion_status(session: Session = Depends(get_db)) -> IngestionStatusOut:
    now = datetime.now(UTC)
    overview = ingestion_overview(session, now)
    return IngestionStatusOut(
        generated_at_utc=now,
        schedule="hourly",
        sources=overview["sources"],
        stations=overview["stations"],
    )


@app.get("/api/v1/scores/compare", response_model=list[ScoreComparisonOut])
def compare_scores(session: Session = Depends(get_db)) -> list[ScoreComparisonOut]:
    now = datetime.now(UTC)
    stations = list(
        session.scalars(select(Station).order_by(Station.display_order, Station.name)).all()
    )
    rows = []
    for station in stations:
        current, base_context = score_station(session, station.id, now)
        candidate, context = candidate_score_station(
            session, station.id, now, base_context
        )
        latest = context.get("latest")
        temperature = context.get("latest_water_temperature")
        rows.append(
            ScoreComparisonOut(
                station_id=station.id,
                station_name=station.name,
                current_score=_score_out(current),
                candidate_score=_score_out(candidate, CANDIDATE_RULES_VERSION),
                latest_flow=ObservationOut.model_validate(latest) if latest else None,
                latest_water_temperature=(
                    ObservationOut.model_validate(temperature) if temperature else None
                ),
                seasonal_flow_percentile=context.get("seasonal_flow_percentile"),
                seasonal_median_m3s=context.get("seasonal_median_m3s"),
                seasonal_sample_count=context.get("seasonal_sample_count", 0),
                seasonal_year_count=context.get("seasonal_year_count", 0),
            )
        )
    return rows


@app.get("/api/v1/stations/{station_id}", response_model=StationDetail)
def station_detail(station_id: str, session: Session = Depends(get_db)) -> StationDetail:
    station = session.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    now = datetime.now(UTC)
    result, context = score_station(session, station.id, now)
    candidate, context = candidate_score_station(session, station.id, now, context)
    latest = context.get("latest")
    temperature = context.get("latest_water_temperature")
    weather = context.get("current_weather")
    return StationDetail(
        id=station.id,
        name=station.name,
        latitude=station.latitude,
        longitude=station.longitude,
        province=station.province,
        source_url=station.source_url,
        latest_flow=ObservationOut.model_validate(latest) if latest else None,
        score=_score_out(result),
        candidate_score=_score_out(candidate, CANDIDATE_RULES_VERSION),
        baseline_median_m3s=context.get("baseline_median"),
        seasonal_median_m3s=context.get("seasonal_median_m3s"),
        seasonal_flow_percentile=context.get("seasonal_flow_percentile"),
        seasonal_sample_count=context.get("seasonal_sample_count", 0),
        seasonal_year_count=context.get("seasonal_year_count", 0),
        six_hour_change_pct=context.get("six_hour_change_pct"),
        precipitation_12h_mm=context.get("precipitation_12h_mm"),
        latest_water_temperature=(
            ObservationOut.model_validate(temperature) if temperature else None
        ),
        current_weather=WeatherOut.model_validate(weather) if weather else None,
    )


@app.get("/api/v1/stations/{station_id}/history", response_model=HistoryResponse)
def station_history(
    station_id: str,
    hours: int = Query(default=48, ge=1, le=168),
    session: Session = Depends(get_db),
) -> HistoryResponse:
    if not session.get(Station, station_id):
        raise HTTPException(status_code=404, detail="Station not found")
    observations = hydro_for_station(
        session, station_id, datetime.now(UTC) - timedelta(hours=hours)
    )
    return HistoryResponse(
        station_id=station_id,
        hours=hours,
        observations=[ObservationOut.model_validate(item) for item in observations],
    )
