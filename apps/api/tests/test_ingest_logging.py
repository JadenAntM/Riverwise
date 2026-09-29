import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _ingest_log(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    return importlib.import_module("jobs.ingest.ingest")._log


def test_successful_ingest_events_use_stdout(capsys, monkeypatch) -> None:
    _ingest_log(monkeypatch)("source_complete", source="wsc", station_id="01FB001")

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "level": "info",
        "event": "source_complete",
        "source": "wsc",
        "station_id": "01FB001",
    }


def test_failed_ingest_events_use_stderr(capsys, monkeypatch) -> None:
    _ingest_log(monkeypatch)("source_failed", source="wsc", station_id="01FB001", error="test")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "level": "error",
        "event": "source_failed",
        "source": "wsc",
        "station_id": "01FB001",
        "error": "test",
    }
