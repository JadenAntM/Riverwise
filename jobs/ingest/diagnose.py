#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from sqlalchemy import func, select, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402
from app.ingestion import parse_wsc_csv  # noqa: E402
from app.models import Station  # noqa: E402


def main() -> None:
    checks = {}
    fixture = ROOT / "tests" / "fixtures" / "wsc_01FB001_sample.csv"
    checks["fixture_rows"] = len(parse_wsc_csv(fixture.read_text(), {"01FB001"}))
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
        checks["database"] = "ok"
        checks["station_count"] = session.scalar(
            select(func.count()).select_from(Station)
        )
    checks["status"] = "ok"
    print(json.dumps(checks, separators=(",", ":")))


if __name__ == "__main__":
    main()
