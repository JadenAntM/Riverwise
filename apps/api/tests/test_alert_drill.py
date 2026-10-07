"""Tests the isolated drill target; no external monitor or email is contacted."""

import importlib

import pytest
from conftest import ROOT
from fastapi.testclient import TestClient


def drill_module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    return importlib.import_module("scripts.phase2_alert_drill")


def test_drill_threshold_and_recovery_head_matches_get(monkeypatch, tmp_path):
    drill = drill_module(monkeypatch)
    state_file = tmp_path / "state.json"
    with TestClient(drill.create_drill_app(state_file)) as client:
        for state, status in [
            ("healthy", 200),
            ("two-failures", 200),
            ("degraded", 503),
            ("healthy", 200),
        ]:
            drill.write_state(state_file, state)
            response = client.get("/api/v1/operational-health")
            assert response.status_code == status
            body = response.json()
            assert body["production"] is False
            assert body["fixture_evaluation_at_utc"].startswith("2026-09-23")
            assert bool(body["alerts"]) == (status == 503)
            if status == 503:
                assert len(body["alerts"]) == 1
                assert body["alerts"][0]["key"] == "repeated_failure:wsc:01FB003"
            head = client.head("/api/v1/operational-health")
            assert head.status_code == status
            assert head.content == b""
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("contents", [None, "bad-json", '{"state":"unknown"}'])
def test_drill_broken_state_is_not_healthy(monkeypatch, tmp_path, contents):
    drill = drill_module(monkeypatch)
    state_file = tmp_path / "state.json"
    if contents is not None:
        state_file.write_text(contents)
    with TestClient(drill.create_drill_app(state_file)) as client:
        assert client.head("/api/v1/operational-health").status_code == 503
        assert (
            client.get("/api/v1/operational-health").json()["status"] == "drill_configuration_error"
        )
