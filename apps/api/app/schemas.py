from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ObservationOut(BaseModel):
    observed_at_utc: datetime
    value: float
    unit: str
    qualifier: str | None
    approval: str | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("observed_at_utc")
    @classmethod
    def mark_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class WeatherOut(BaseModel):
    valid_at_utc: datetime
    kind: str
    air_temp_c: float | None
    precip_mm: float | None
    cloud_cover_pct: float | None
    pressure_hpa: float | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("valid_at_utc")
    @classmethod
    def mark_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ComponentOut(BaseModel):
    key: str
    label: str
    points: int | None
    maximum: int
    reason: str


class ScoreOut(BaseModel):
    value: float | None
    status: str
    confidence: str
    earned_points: int
    available_points: int
    rules_version: str
    reasons: list[str]
    components: list[ComponentOut]


class StationSummary(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    province: str
    source_url: str
    latest_flow: ObservationOut | None
    score: ScoreOut


class StationDetail(StationSummary):
    candidate_score: ScoreOut
    baseline_median_m3s: float | None
    seasonal_median_m3s: float | None
    seasonal_flow_percentile: float | None
    seasonal_sample_count: int
    seasonal_year_count: int
    six_hour_change_pct: float | None
    precipitation_12h_mm: float | None
    latest_water_temperature: ObservationOut | None
    current_weather: WeatherOut | None


class ScoreComparisonOut(BaseModel):
    station_id: str
    station_name: str
    current_score: ScoreOut
    candidate_score: ScoreOut
    latest_flow: ObservationOut | None
    latest_water_temperature: ObservationOut | None
    seasonal_flow_percentile: float | None
    seasonal_median_m3s: float | None
    seasonal_sample_count: int
    seasonal_year_count: int


class HistoryResponse(BaseModel):
    station_id: str
    hours: int = Field(ge=1, le=168)
    observations: list[ObservationOut]


class HealthResponse(BaseModel):
    status: str
    database: str
    last_ingest_status: str | None
    last_ingest_at_utc: datetime | None

    @field_validator("last_ingest_at_utc")
    @classmethod
    def mark_optional_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class IngestSourceStatusOut(BaseModel):
    source: str
    station_id: str | None
    status: str
    last_attempt_at_utc: datetime
    last_success_at_utc: datetime | None
    fetched_count: int
    upserted_count: int
    duration_ms: int | None
    error: str | None


class StationFreshnessOut(BaseModel):
    id: str
    name: str
    latest_observed_at_utc: datetime | None
    age_minutes: int | None


class IngestionStatusOut(BaseModel):
    generated_at_utc: datetime
    schedule: str
    sources: list[IngestSourceStatusOut]
    stations: list[StationFreshnessOut]
