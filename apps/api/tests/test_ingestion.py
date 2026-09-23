from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion import parse_wsc_csv, upsert_hydro
from app.models import HydroObservation

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


def test_additional_verified_station_fixture() -> None:
    content = (
        ROOT / "tests" / "fixtures" / "wsc_additional_stations_sample.csv"
    ).read_text()
    rows = parse_wsc_csv(content, {"01FB003", "01FC002"})
    assert [(row.station_id, row.value) for row in rows] == [
        ("01FB003", 10.3),
        ("01FC002", 3.35),
    ]


def test_parser_rejects_unexpected_station() -> None:
    content = (
        "ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,"
        "Approval/Approbation\n"
        "OTHER,2026-09-23T16:00:00Z,47,1.0,,Provisional\n"
    )
    with pytest.raises(ValueError, match="Unexpected station"):
        parse_wsc_csv(content, {"01FB001"})


def test_upsert_is_idempotent_and_applies_revision(session: Session) -> None:
    first = (
        "ID,Date,Parameter/Paramètre,Value/Valeur,Qualifier/Qualificatif,"
        "Approval/Approbation\n"
        "01FB001,2026-09-23T16:00:00Z,47,8.10,,Provisional\n"
    )
    revised = first.replace("8.10", "8.25")
    ingested_at = datetime(2026, 9, 23, 16, 30, tzinfo=UTC)
    upsert_hydro(session, parse_wsc_csv(first, {"01FB001"}), ingested_at)
    upsert_hydro(session, parse_wsc_csv(revised, {"01FB001"}), ingested_at)
    count = session.scalar(select(func.count()).select_from(HydroObservation))
    observation = session.scalar(
        select(HydroObservation).where(
            HydroObservation.observed_at_utc == datetime(2026, 9, 23, 16)
        )
    )
    assert count == 39
    assert observation is not None
    assert observation.value == 8.25
