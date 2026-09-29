#!/usr/bin/env python3
"""Replay Riverwise's score versions against one local database without writes.

Run with DATABASE_URL set to a local restore or local development database. The
script does not call providers and prints JSON to stdout. Never target production.
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402
from app.models import ScoreSnapshot, Station  # noqa: E402
from app.scoring import (  # noqa: E402
    CANDIDATE_RULES_VERSION,
    EXPERIMENT_RULES_VERSION,
    RULES_VERSION,
)
from app.service import (  # noqa: E402
    candidate_score_station,
    experiment_score_station,
    score_station,
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "mean": round(mean(values), 3) if values else None,
        "median": round(median(values), 3) if values else None,
        "minimum": round(min(values), 3) if values else None,
        "maximum": round(max(values), 3) if values else None,
    }


def analyze(max_times: int, station_filter: str | None = None) -> dict:
    with SessionLocal() as session:
        stations = list(
            session.scalars(select(Station).order_by(Station.display_order)).all()
        )
        if station_filter:
            stations = [station for station in stations if station.id == station_filter]
            if not stations:
                raise ValueError(f"Unknown station: {station_filter}")
        times = list(
            session.scalars(
                select(ScoreSnapshot.computed_at_utc)
                .where(ScoreSnapshot.rules_version == RULES_VERSION)
                .distinct()
                .order_by(ScoreSnapshot.computed_at_utc)
            ).all()
        )
        if not times:
            raise ValueError("No v1.0 score snapshots found in the local database")
        # Evenly spaced, deterministic sample across the stored observation window.
        if len(times) > max_times:
            indices = [
                (index * (len(times) - 1)) // (max_times - 1)
                for index in range(max_times)
            ]
            times = [times[index] for index in indices]

        rows = []
        for at in times:
            evaluation_time = _utc(at)
            for station in stations:
                current, base = score_station(session, station.id, evaluation_time)
                candidate, context = candidate_score_station(
                    session, station.id, evaluation_time, base
                )
                experiment, experiment_context = experiment_score_station(
                    session, station, evaluation_time, base, context
                )
                rows.append(
                    {
                        "station_id": station.id,
                        "evaluation_time": evaluation_time.isoformat(),
                        RULES_VERSION: current.score if current else None,
                        CANDIDATE_RULES_VERSION: candidate.score if candidate else None,
                        EXPERIMENT_RULES_VERSION: experiment.score
                        if experiment
                        else None,
                        "v1_2_confidence": experiment.confidence
                        if experiment
                        else "unavailable",
                        "v1_2_available_points": experiment.available_points
                        if experiment
                        else 0,
                        "pressure_hpa": experiment_context["pressure_hpa"],
                        "pressure_change_6h_hpa": experiment_context[
                            "pressure_change_6h_hpa"
                        ],
                    }
                )

    versions = (RULES_VERSION, CANDIDATE_RULES_VERSION, EXPERIMENT_RULES_VERSION)
    comparison = {}
    for version in versions:
        available = [row[version] for row in rows if row[version] is not None]
        comparison[version] = {
            **_summary(available),
            "availability_pct": round(len(available) / len(rows) * 100, 1),
        }
    differences = {}
    for version in versions[1:]:
        paired = [
            row[version] - row[RULES_VERSION]
            for row in rows
            if row[version] is not None and row[RULES_VERSION] is not None
        ]
        differences[version] = {
            "paired_count": len(paired),
            "mean_signed_change": round(mean(paired), 3) if paired else None,
            "mean_absolute_change": round(mean(abs(value) for value in paired), 3)
            if paired
            else None,
            "changed_by_at_least_one_point": sum(abs(value) >= 1 for value in paired),
        }
    return {
        "method": "Recompute all versions at identical sampled UTC times using the current local database contents; historical provider revisions may have changed inputs since original snapshots.",
        "sampled_times": len(times),
        "station_count": len(stations),
        "evaluation_count": len(rows),
        "first_time_utc": _utc(times[0]).isoformat(),
        "last_time_utc": _utc(times[-1]).isoformat(),
        "versions": comparison,
        "versus_v1_0": differences,
        "v1_2_partial_count": sum(row["v1_2_confidence"] == "partial" for row in rows),
        "pressure_trend_coverage": sum(
            row["pressure_change_6h_hpa"] is not None for row in rows
        ),
        "pressure_absolute_coverage": sum(
            row["pressure_hpa"] is not None for row in rows
        ),
        "outcome_evaluation": None,
        "accuracy_note": "Score differences and pressure coverage do not establish catch prediction accuracy. Outcome evaluation needs real effort-normalized trips including zero-catch trips.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-times",
        type=int,
        default=72,
        help="Evenly spaced evaluation times (2–1000)",
    )
    parser.add_argument("--station", help="Optional official station ID")
    arguments = parser.parse_args()
    if not 2 <= arguments.max_times <= 1000:
        parser.error("--max-times must be between 2 and 1000")
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        parser.error(
            "Set DATABASE_URL to an explicit local PostgreSQL or SQLite URL; production is not allowed"
        )
    parsed = make_url(database_url)
    if not parsed.drivername.startswith("sqlite") and parsed.host not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        parser.error(
            "The database host must be localhost or a SQLite file; production is not allowed"
        )
    print(json.dumps(analyze(arguments.max_times, arguments.station), indent=2))


if __name__ == "__main__":
    main()
