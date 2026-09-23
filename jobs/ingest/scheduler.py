#!/usr/bin/env python3
import json
import logging
import signal
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402
from ingest import ingest_live  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("riverwise.scheduler")
stop_event = threading.Event()


def _log(event: str, **fields: object) -> None:
    logger.info(
        json.dumps({"event": event, **fields}, default=str, separators=(",", ":"))
    )


def _seconds_until_next_run(now: datetime) -> float:
    next_run = (now + timedelta(hours=1)).replace(minute=10, second=0, microsecond=0)
    if now.minute < 10:
        next_run = now.replace(minute=10, second=0, microsecond=0)
    return max(1, (next_run - now).total_seconds())


def _stop(_signum, _frame) -> None:
    stop_event.set()


def run_once() -> None:
    evaluation_time = datetime.now(UTC)
    _log("scheduled_ingest_started", evaluation_time=evaluation_time)
    with SessionLocal() as session:
        ingest_live(session, evaluation_time)
    _log("scheduled_ingest_finished", evaluation_time=evaluation_time)


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    run_once()
    while not stop_event.is_set():
        delay = _seconds_until_next_run(datetime.now(UTC))
        _log("scheduler_waiting", next_run_in_seconds=int(delay))
        if stop_event.wait(delay):
            break
        run_once()
    _log("scheduler_stopped")


if __name__ == "__main__":
    main()
