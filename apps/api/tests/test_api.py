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


def test_station_list_includes_all_verified_gauges(client: TestClient) -> None:
    response = client.get("/api/v1/stations")
    assert response.status_code == 200
    assert {station["id"] for station in response.json()} == {
        "01FB001",
        "01FB003",
        "01FC002",
    }


def test_known_station_without_observations_is_explicit(client: TestClient) -> None:
    response = client.get("/api/v1/stations/01FC002")
    assert response.status_code == 200
    assert response.json()["latest_flow"] is None
    assert response.json()["score"]["status"] == "insufficient_data"


def test_ingestion_status_reports_sources_and_station_freshness(client: TestClient) -> None:
    response = client.get("/api/v1/ingestion")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schedule"] == "hourly"
    assert len(payload["stations"]) == 3
    assert payload["sources"][0]["source"] == "offline_fixtures"
    assert payload["sources"][0]["station_id"] == "01FB001"


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
