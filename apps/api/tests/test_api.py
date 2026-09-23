from fastapi.testclient import TestClient


def test_station_vertical_slice(client: TestClient) -> None:
    response = client.get("/api/v1/stations/01FB001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "01FB001"
    assert payload["latest_flow"]["value"] == 8.1
    assert payload["latest_flow"]["unit"] == "m³/s"
    assert payload["latest_flow"]["observed_at_utc"].endswith("Z")
    assert payload["latest_flow"]["approval"] == "Provisional/Provisoire"
    assert payload["baseline_median_m3s"] is not None
    assert payload["latest_water_temperature"]["value"] == 11.15
    assert payload["seasonal_flow_percentile"] is not None
    assert payload["seasonal_sample_count"] == 42
    assert payload["seasonal_year_count"] == 6
    assert payload["candidate_score"]["rules_version"] == "v1.1.0-shadow"


def test_station_list_includes_all_verified_gauges(client: TestClient) -> None:
    response = client.get("/api/v1/stations")
    assert response.status_code == 200
    assert {station["id"] for station in response.json()} == {
        "01FB001",
        "01FB003",
        "01FC002",
        "01EO001",
        "01EF001",
        "01ED005",
    }


def test_known_station_without_observations_is_explicit(client: TestClient) -> None:
    response = client.get("/api/v1/stations/01FC002")
    assert response.status_code == 200
    assert response.json()["latest_flow"] is None
    assert response.json()["score"]["status"] == "insufficient_data"
    assert response.json()["candidate_score"]["status"] == "insufficient_data"


def test_ingestion_status_reports_sources_and_station_freshness(client: TestClient) -> None:
    response = client.get("/api/v1/ingestion")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schedule"] == "hourly"
    assert len(payload["stations"]) == 6
    assert payload["sources"][0]["source"] == "offline_fixtures"
    assert payload["sources"][0]["station_id"] == "01FB001"


def test_score_comparison_keeps_current_and_candidate_versions(client: TestClient) -> None:
    response = client.get("/api/v1/scores/compare")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 6
    first = payload[0]
    assert first["station_id"] == "01FB001"
    assert first["current_score"]["rules_version"] == "v1.0.0"
    assert first["candidate_score"]["rules_version"] == "v1.1.0-shadow"
    assert first["latest_water_temperature"]["unit"] == "°C"


def test_score_history_returns_both_versions_and_validates_window(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/stations/01FB001/score-history?days=7")
    assert response.status_code == 200
    payload = response.json()
    assert payload["station_id"] == "01FB001"
    assert {row["rules_version"] for row in payload["snapshots"]} == {
        "v1.0.0",
        "v1.1.0-shadow",
    }
    assert all(row["status"] == "available" for row in payload["snapshots"])

    unavailable = client.get("/api/v1/stations/01EO001/score-history?days=7")
    assert unavailable.status_code == 200
    assert all(row["value"] is None for row in unavailable.json()["snapshots"])
    assert all(row["confidence"] == "unavailable" for row in unavailable.json()["snapshots"])
    assert all(
        row["hydro_observed_at_utc"] is None
        for row in unavailable.json()["snapshots"]
    )
    assert client.get("/api/v1/stations/01FB001/score-history?days=14").status_code == 422


def test_reliability_reports_measured_metrics(client: TestClient) -> None:
    response = client.get("/api/v1/reliability?days=30")
    assert response.status_code == 200
    payload = response.json()
    assert payload["days"] == 30
    assert len(payload["stations"]) == 6
    first = payload["stations"][0]
    assert first["id"] == "01FB001"
    assert first["historical_daily_observation_count"] == 42
    assert first["candidate_snapshot_count"] == 1
    assert first["water_temperature_availability_pct"] == 100.0
    provider = payload["providers"][0]
    assert provider["attempts"] == 1
    assert provider["success_rate_pct"] == 100.0
    assert provider["revision_count"] == 0
    assert client.get("/api/v1/reliability?days=14").status_code == 422


def test_history_is_ordered_and_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/stations/01FB001/history?hours=48")
    assert response.status_code == 200
    observations = response.json()["observations"]
    timestamps = [item["observed_at_utc"] for item in observations]
    assert timestamps == sorted(timestamps)

    invalid = client.get("/api/v1/stations/01FB001/history?hours=169")
    assert invalid.status_code == 422


def test_unknown_station_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/stations/UNKNOWN").status_code == 404
