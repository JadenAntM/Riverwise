#!/usr/bin/env python3
"""Fixture-only HTTP monitor drill. Never connects to an application database."""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.alerts import operational_findings  # noqa: E402
from app.database import Base  # noqa: E402
from app.ingestion import parse_wsc_csv, seed_station, upsert_hydro  # noqa: E402
from app.models import IngestRun  # noqa: E402

STATES = ("healthy", "two-failures", "degraded")
STATION_ID = "01FB003"


def drill_findings(state: str) -> tuple[datetime, list]:
    if state not in STATES:
        raise ValueError("Unknown drill state")
    seeds = json.loads((ROOT / "data/stations.json").read_text())
    seed = next(item for item in seeds if item["id"] == STATION_ID)
    rows = parse_wsc_csv(
        (ROOT / "tests/fixtures/wsc_additional_stations_sample.csv").read_text(),
        {item["id"] for item in seeds},
    )
    rows = [row for row in rows if row.station_id == STATION_ID]
    # Use the real fixture's own clock, never fabricate a present-day measurement.
    now = max(row.observed_at_utc for row in rows).astimezone(UTC)
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            seed_station(session, seed)
            upsert_hydro(session, rows, now)
            failures = {"healthy": 0, "two-failures": 2, "degraded": 3}[state]
            runs = [("open_meteo", "success", 5), ("wsc", "success", 4)]
            runs += [("wsc", "failed", minute) for minute in range(failures, 0, -1)]
            for source, status, minute in runs:
                when = now - timedelta(minutes=minute)
                session.add(
                    IngestRun(
                        started_at_utc=when,
                        ended_at_utc=when,
                        source=source,
                        station_id=STATION_ID,
                        status=status,
                        error_kind="provider_network" if status == "failed" else None,
                    )
                )
            session.commit()
            return now, operational_findings(session, now)
    finally:
        engine.dispose()


def write_state(path: Path, state: str) -> None:
    if state not in STATES:
        raise ValueError("Unknown drill state")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({"state": state}) + "\n")
    temporary.replace(path)


def create_drill_app(state_file: Path) -> FastAPI:
    app = FastAPI(title="Riverwise controlled alert-delivery drill")

    @app.get("/health")
    def health():
        return {"status": "ok", "drill": True, "production": False}

    def evaluate():
        try:
            state = json.loads(state_file.read_text())["state"]
            now, findings = drill_findings(state)
            return (503 if findings else 200), {
                "drill": True,
                "production": False,
                "state": state,
                "fixture_evaluation_at_utc": now.isoformat(),
                "status": "degraded" if findings else "ok",
                "alerts": [finding.__dict__ for finding in findings],
            }
        except (ValueError, KeyError, OSError, TypeError):
            # A broken drill must not report a healthy monitor target.
            return 503, {"drill": True, "status": "drill_configuration_error"}

    @app.get("/api/v1/operational-health")
    def operational_health():
        status, body = evaluate()
        return JSONResponse(status_code=status, content=body)

    @app.head("/api/v1/operational-health")
    def operational_health_head():
        status, _ = evaluate()
        return Response(status_code=status)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("serve", "set-state"))
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--state", choices=STATES, default="healthy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8013)
    args = parser.parse_args()
    if args.action == "set-state" or not args.state_file.exists():
        write_state(args.state_file, args.state)
    if args.action == "serve":
        import uvicorn

        uvicorn.run(create_drill_app(args.state_file), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
