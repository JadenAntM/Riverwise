from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    province: Mapped[str] = mapped_column(String(2), default="NS")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    has_discharge: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    source_url: Mapped[str] = mapped_column(String(500))

    hydro_observations: Mapped[list["HydroObservation"]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )
    weather_hours: Mapped[list["WeatherHour"]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )


class HydroObservation(Base):
    __tablename__ = "hydro_observations"
    __table_args__ = (
        UniqueConstraint("station_id", "observed_at_utc", "parameter"),
        Index("ix_hydro_station_parameter_time", "station_id", "parameter", "observed_at_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"))
    observed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    parameter: Mapped[str] = mapped_column(String(20))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    qualifier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approval: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ingested_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    station: Mapped[Station] = relationship(back_populates="hydro_observations")


class WeatherHour(Base):
    __tablename__ = "weather_hours"
    __table_args__ = (
        UniqueConstraint("station_id", "valid_at_utc", "kind"),
        Index("ix_weather_station_time", "station_id", "valid_at_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"))
    valid_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(32))
    air_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    precip_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    ingested_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    station: Mapped[Station] = relationship(back_populates="weather_hours")


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"))
    computed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hydro_observed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[str] = mapped_column(String(40))
    available_points: Mapped[int] = mapped_column(Integer)
    earned_points: Mapped[int] = mapped_column(Integer)
    components_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    rules_version: Mapped[str] = mapped_column(String(32))


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    station_id: Mapped[str | None] = mapped_column(ForeignKey("stations.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    upserted_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
