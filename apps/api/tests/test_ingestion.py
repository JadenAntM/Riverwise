from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion import (
    NoUsableObservations,
    parse_open_meteo,
    parse_wsc_csv,
    parse_wsc_daily_csv,
    upsert_hydro,
)
from app.models import HydroObservation, HydroRevision, ScoreSnapshot
from app.service import persist_score_snapshots

ROOT = Path(__file__).resolve().parents[3]


def test_parser_preserves_source_fields() -> None:
    content = (ROOT / "tests" / "fixtures" / "wsc_01FB001_sample.csv").read_text()
    rows = parse_wsc_csv(content, {"01FB001"})
    assert rows[-1].station_id == "01FB001"
    assert rows[-1].observed_at_utc == datetime(2026, 9, 23, 16, tzinfo=UTC)
    assert rows[-1].parameter == "discharge"
    assert rows[-1].unit == "m³/s"
    assert rows[-1].approval == "Provisional/Provisoire"


def test_parser_normalizes_live_header_whitespace() -> None:
    content = (
        "\ufeff ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,"
        "Approval/Approbation\n"
        "01FB001,2026-09-23T17:05:00Z,47,8.01,,Provisional/Provisoire\n"
    )
    rows = parse_wsc_csv(content, {"01FB001"})
    assert len(rows) == 1
    assert rows[0].value == 8.01


def test_parser_supports_optional_water_temperature() -> None:
    content = (
        ROOT / "tests" / "fixtures" / "wsc_01FB001_temperature_sample.csv"
    ).read_text()
    rows = parse_wsc_csv(content, {"01FB001"})
    assert rows[-1].parameter == "water_temperature"
    assert rows[-1].value == 11.15
    assert rows[-1].unit == "°C"


def test_daily_parser_preserves_historical_symbol() -> None:
    content = (
        ROOT / "tests" / "fixtures" / "wsc_01FB001_daily_sample.csv"
    ).read_text()
    rows = parse_wsc_daily_csv(content, {"01FB001"})
    estimated = next(row for row in rows if row.observed_at_utc.date().isoformat() == "2022-09-24")
    assert estimated.parameter == "daily_discharge"
    assert estimated.value == 196
    assert estimated.qualifier == "E"


def test_additional_verified_station_fixture() -> None:
    content = (
        ROOT / "tests" / "fixtures" / "wsc_additional_stations_sample.csv"
    ).read_text()
    rows = parse_wsc_csv(content, {"01FB003", "01FC002"})
    assert [(row.station_id, row.value) for row in rows] == [
        ("01FB003", 10.3),
        ("01FC002", 3.35),
    ]


def test_expanded_verified_station_fixture() -> None:
    content = (
        ROOT / "tests" / "fixtures" / "wsc_expanded_stations_sample.csv"
    ).read_text()
    rows = parse_wsc_csv(content, {"01EO001", "01EF001", "01ED005"})
    assert [(row.station_id, row.value) for row in rows] == [
        ("01EO001", 24.2),
        ("01EF001", 18.6),
        ("01ED005", 3.07),
    ]


def test_parser_rejects_unexpected_station() -> None:
    content = (
        "ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,"
        "Approval/Approbation\n"
        "OTHER,2026-09-23T16:00:00Z,47,1.0,,Provisional\n"
    )
    with pytest.raises(ValueError, match="Unexpected station"):
        parse_wsc_csv(content, {"01FB001"})


def test_parser_skips_missing_values_and_deduplicates_identical_rows() -> None:
    header = (
        "ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,"
        "Approval/Approbation\n"
    )
    missing = "01FB001,2026-09-23T15:00:00Z,47,,,Provisional\n"
    valid = "01FB001,2026-09-23T16:00:00Z,47,8.1,,Provisional\n"
    assert len(parse_wsc_csv(header + missing + valid + valid, {"01FB001"})) == 1
    with pytest.raises(NoUsableObservations, match="no usable observations"):
        parse_wsc_csv(header + missing, {"01FB001"})


def test_parser_rejects_conflicting_duplicates_and_implausible_values() -> None:
    header = (
        "ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,"
        "Approval/Approbation\n"
    )
    valid = "01FB001,2026-09-23T16:00:00Z,47,8.1,,Provisional\n"
    revised = valid.replace("8.1", "8.2")
    with pytest.raises(ValueError, match="conflicting duplicate"):
        parse_wsc_csv(header + valid + revised, {"01FB001"})
    with pytest.raises(ValueError, match="nonnegative"):
        parse_wsc_csv(header + valid.replace("8.1", "-1"), {"01FB001"})
    with pytest.raises(ValueError, match="finite"):
        parse_wsc_csv(header + valid.replace("8.1", "NaN"), {"01FB001"})


def test_weather_parser_rejects_bad_ranges_and_duplicate_hours() -> None:
    now = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)
    hourly = {
        "time": ["2026-09-23T16:00"],
        "temperature_2m": [12.0],
        "precipitation": [1.0],
        "cloud_cover": [50],
        "surface_pressure": [1010.0],
    }
    assert len(parse_open_meteo({"hourly": hourly}, "01FB001", now)) == 1
    with pytest.raises(ValueError, match="cloud_cover"):
        parse_open_meteo(
            {"hourly": {**hourly, "cloud_cover": [101]}}, "01FB001", now
        )
    with pytest.raises(ValueError, match="duplicate hourly"):
        parse_open_meteo(
            {"hourly": {key: values * 2 for key, values in hourly.items()}},
            "01FB001",
            now,
        )
    with pytest.raises(NoUsableObservations, match="no usable weather"):
        parse_open_meteo(
            {"hourly": {key: [None] for key in hourly if key != "time"} | {"time": hourly["time"]}},
            "01FB001",
            now,
        )


def test_upsert_is_idempotent_and_applies_revision(session: Session) -> None:
    first = (
        "ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,"
        "Approval/Approbation\n"
        "01FB001,2026-09-23T16:00:00Z,47,8.10,,Provisional/Provisoire\n"
    )
    revised = first.replace("8.10", "8.25")
    ingested_at = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)
    unchanged = upsert_hydro(session, parse_wsc_csv(first, {"01FB001"}), ingested_at)
    changed = upsert_hydro(session, parse_wsc_csv(revised, {"01FB001"}), ingested_at)
    count = session.scalar(
        select(func.count())
        .select_from(HydroObservation)
        .where(HydroObservation.parameter == "discharge")
    )
    observation = session.scalar(
        select(HydroObservation).where(
            HydroObservation.observed_at_utc == datetime(2026, 9, 23, 16)
        )
    )
    assert count == 39
    assert observation is not None
    assert observation.value == 8.25
    assert unchanged.updated == 1
    assert unchanged.revisions == 0
    assert changed.updated == 1
    assert changed.revisions == 1
    revisions = list(session.scalars(select(HydroRevision)).all())
    assert len(revisions) == 1
    assert revisions[0].old_fields_json["value"] == 8.1
    assert revisions[0].new_fields_json["value"] == 8.25
    assert revisions[0].detected_at_utc == ingested_at.replace(tzinfo=None)


def test_score_snapshot_persistence_is_idempotent(session: Session) -> None:
    evaluation_time = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)
    station_ids = ["01FB001", "01FB003", "01FC002", "01EO001", "01EF001", "01ED005"]
    persist_score_snapshots(session, station_ids, evaluation_time)
    persist_score_snapshots(session, station_ids, evaluation_time)
    count = session.scalar(select(func.count()).select_from(ScoreSnapshot))
    assert count == 18
