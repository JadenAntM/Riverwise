import csv
import io
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import HydroObservation, HydroRevision, Station, WeatherHour

WSC_HEADERS = {
    "ID",
    "Date",
    "Parameter/Paramètre",
    "Value/Valeur",
    "Qualifier/Qualificatif",
    "Approval/Approbation",
}
WSC_DAILY_HEADERS = {
    "ID",
    "Date",
    "Parameter/Paramètre",
    "Value/Valeur",
    "Symbol/Symbole",
}
PARAMETERS = {
    "47": ("discharge", "m³/s"),
    "46": ("level", "m"),
    "5": ("water_temperature", "°C"),
}


class NoUsableObservations(ValueError):
    """A valid provider response contained no measurements Riverwise can use."""


@dataclass(frozen=True)
class HydroRow:
    station_id: str
    observed_at_utc: datetime
    parameter: str
    value: float
    unit: str
    qualifier: str | None
    approval: str | None


def _unique_hydro_rows(rows: list[HydroRow]) -> list[HydroRow]:
    unique: dict[tuple[str, datetime, str], HydroRow] = {}
    for row in rows:
        key = (row.station_id, row.observed_at_utc, row.parameter)
        previous = unique.get(key)
        if previous is not None and previous != row:
            raise ValueError("Provider response contains conflicting duplicate observations")
        unique[key] = row
    return list(unique.values())


@dataclass(frozen=True)
class UpsertResult:
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    revisions: int = 0

    def __add__(self, other: "UpsertResult") -> "UpsertResult":
        return UpsertResult(
            processed=self.processed + other.processed,
            inserted=self.inserted + other.inserted,
            updated=self.updated + other.updated,
            revisions=self.revisions + other.revisions,
        )


def parse_wsc_csv(content: str, allowed_station_ids: set[str]) -> list[HydroRow]:
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    normalized_headers = {header.strip() for header in reader.fieldnames or []}
    if not WSC_HEADERS.issubset(normalized_headers):
        raise ValueError("WSC response is missing required CSV headers")

    rows: list[HydroRow] = []
    for source_row in reader:
        raw = {(key or "").strip(): value for key, value in source_row.items()}
        station_id = raw["ID"].strip()
        if station_id not in allowed_station_ids:
            raise ValueError(f"Unexpected station ID: {station_id}")
        parameter_id = raw["Parameter/Paramètre"].strip()
        if parameter_id not in PARAMETERS:
            continue
        if not raw["Value/Valeur"].strip():
            continue
        value = float(raw["Value/Valeur"])
        if not math.isfinite(value):
            raise ValueError("Hydrometric values must be finite")
        parameter, unit = PARAMETERS[parameter_id]
        if parameter in {"discharge", "level"} and value < 0:
            raise ValueError("Water level and discharge must be nonnegative")
        if parameter == "water_temperature" and not -5 <= value <= 40:
            raise ValueError("Water temperature is outside the accepted source range")
        observed_at = datetime.fromisoformat(raw["Date"].replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            raise ValueError("Hydrometric timestamps must include a timezone")
        qualifier = (
            raw.get("Qualifier/Qualificatif", "").strip()
            or raw.get("Qualifiers/Qualificatifs", "").strip()
            or None
        )
        rows.append(
            HydroRow(
                station_id,
                observed_at.astimezone(UTC),
                parameter,
                value,
                unit,
                qualifier,
                raw.get("Approval/Approbation", "").strip() or None,
            )
        )
    if not rows:
        raise NoUsableObservations("WSC response contained no usable observations")
    return _unique_hydro_rows(rows)


def parse_wsc_daily_csv(content: str, allowed_station_ids: set[str]) -> list[HydroRow]:
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    normalized_headers = {header.strip() for header in reader.fieldnames or []}
    if not WSC_DAILY_HEADERS.issubset(normalized_headers):
        raise ValueError("WSC daily response is missing required CSV headers")

    rows: list[HydroRow] = []
    for source_row in reader:
        raw = {(key or "").strip(): value for key, value in source_row.items()}
        station_id = raw["ID"].strip()
        if station_id not in allowed_station_ids:
            raise ValueError(f"Unexpected station ID: {station_id}")
        if raw["Parameter/Paramètre"].strip().lower() not in {
            "discharge",
            "discharge/débit",
        }:
            continue
        if not raw["Value/Valeur"].strip():
            continue
        value = float(raw["Value/Valeur"])
        if not math.isfinite(value) or value < 0:
            raise ValueError("Daily discharge must be finite and nonnegative")
        observed_at = datetime.fromisoformat(raw["Date"]).replace(tzinfo=UTC)
        rows.append(
            HydroRow(
                station_id=station_id,
                observed_at_utc=observed_at,
                parameter="daily_discharge",
                value=value,
                unit="m³/s",
                qualifier=raw.get("Symbol/Symbole", "").strip() or None,
                approval=None,
            )
        )
    if not rows:
        raise NoUsableObservations("WSC daily response contained no usable observations")
    return _unique_hydro_rows(rows)


def parse_open_meteo(
    payload: dict[str, Any], station_id: str, evaluation_time: datetime
) -> list[dict[str, Any]]:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    keys = ("temperature_2m", "precipitation", "cloud_cover", "surface_pressure")
    if not times or any(len(hourly.get(key, [])) != len(times) for key in keys):
        raise ValueError("Open-Meteo response contains mismatched hourly arrays")
    limits = {
        "temperature_2m": (-80, 60),
        "precipitation": (0, 500),
        "cloud_cover": (0, 100),
        "surface_pressure": (800, 1100),
    }
    result = []
    seen_times: set[datetime] = set()
    for index, raw_time in enumerate(times):
        valid_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        valid_at = (
            valid_at.replace(tzinfo=UTC)
            if valid_at.tzinfo is None
            else valid_at.astimezone(UTC)
        )
        if valid_at in seen_times:
            raise ValueError("Open-Meteo response contains duplicate hourly timestamps")
        seen_times.add(valid_at)
        values = {}
        for key, (minimum, maximum) in limits.items():
            value = hourly[key][index]
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"Open-Meteo {key} must be numeric or null")
                if not math.isfinite(value) or not minimum <= value <= maximum:
                    raise ValueError(f"Open-Meteo {key} is outside the accepted source range")
            values[key] = value
        result.append(
            {
                "station_id": station_id,
                "valid_at_utc": valid_at,
                "kind": "historical_or_modelled" if valid_at <= evaluation_time else "forecast",
                "air_temp_c": values["temperature_2m"],
                "precip_mm": values["precipitation"],
                "cloud_cover_pct": values["cloud_cover"],
                "pressure_hpa": values["surface_pressure"],
            }
        )
    if not any(
        row[key] is not None
        for row in result
        for key in ("air_temp_c", "precip_mm", "cloud_cover_pct", "pressure_hpa")
    ):
        raise NoUsableObservations("Open-Meteo response contained no usable weather values")
    return result


def upsert_hydro(
    session: Session, rows: list[HydroRow], ingested_at: datetime
) -> UpsertResult:
    inserted = 0
    updated = 0
    revisions = 0
    for row in rows:
        existing = session.scalar(
            select(HydroObservation).where(
                HydroObservation.station_id == row.station_id,
                HydroObservation.observed_at_utc == row.observed_at_utc,
                HydroObservation.parameter == row.parameter,
            )
        )
        if existing:
            old_fields = {
                "value": existing.value,
                "unit": existing.unit,
                "qualifier": existing.qualifier,
                "approval": existing.approval,
            }
            new_fields = {
                "value": row.value,
                "unit": row.unit,
                "qualifier": row.qualifier,
                "approval": row.approval,
            }
            changed = (
                old_fields != new_fields
            )
            if changed:
                session.add(
                    HydroRevision(
                        observation_id=existing.id,
                        station_id=row.station_id,
                        observed_at_utc=row.observed_at_utc,
                        parameter=row.parameter,
                        detected_at_utc=ingested_at,
                        old_fields_json=old_fields,
                        new_fields_json=new_fields,
                    )
                )
            existing.value = row.value
            existing.unit = row.unit
            existing.qualifier = row.qualifier
            existing.approval = row.approval
            existing.ingested_at_utc = ingested_at
            updated += 1
            revisions += int(changed)
        else:
            session.add(HydroObservation(**row.__dict__, ingested_at_utc=ingested_at))
            inserted += 1
    session.commit()
    return UpsertResult(len(rows), inserted, updated, revisions)


def upsert_weather(
    session: Session, rows: list[dict[str, Any]], ingested_at: datetime
) -> UpsertResult:
    inserted = 0
    updated = 0
    revisions = 0
    for row in rows:
        existing = session.scalar(
            select(WeatherHour).where(
                WeatherHour.station_id == row["station_id"],
                WeatherHour.valid_at_utc == row["valid_at_utc"],
                WeatherHour.kind == row["kind"],
            )
        )
        values = {**row, "ingested_at_utc": ingested_at}
        if existing:
            changed = any(getattr(existing, key) != value for key, value in row.items())
            for key, value in values.items():
                setattr(existing, key, value)
            updated += 1
            revisions += int(changed)
        else:
            session.add(WeatherHour(**values))
            inserted += 1
    session.commit()
    return UpsertResult(len(rows), inserted, updated, revisions)


def seed_station(session: Session, data: dict[str, Any]) -> Station:
    station = session.get(Station, data["id"])
    if station:
        for key, value in data.items():
            setattr(station, key, value)
    else:
        station = Station(**data)
        session.add(station)
    session.commit()
    return station
