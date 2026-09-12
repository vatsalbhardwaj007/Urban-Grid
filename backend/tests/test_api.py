"""Integration and unit tests for Urban Grid FastAPI REST API."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import stop_simulation
from backend.api.main import app
from shared.schemas.traffic_state import TrafficState
from simulation.sumo.traci_bridge import is_sumo_available

REQUIRES_SUMO = pytest.mark.skipif(
    not is_sumo_available(),
    reason="SUMO executable or traci package is unavailable in this environment.",
)


@pytest.fixture
def client():
    """Create a TestClient with clean startup and teardown lifecycle."""
    with TestClient(app) as test_client:
        yield test_client
    stop_simulation()


# =============================================================================
# API Endpoint Tests
# =============================================================================


def test_fastapi_app_imports_successfully() -> None:
    """1. FastAPI application instance imports and is configured properly."""
    assert isinstance(app, FastAPI)
    assert app.title == "Urban Grid API"


@REQUIRES_SUMO
def test_get_health_endpoint(client: TestClient) -> None:
    """2. GET /health confirms backend process is alive and reports simulation status."""
    res = client.get("/health")
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "ok"
    assert data["simulation_connected"] is True
    assert isinstance(data["simulation_time"], (int, float))
    assert data["simulation_time"] >= 0.0


@REQUIRES_SUMO
def test_get_intersections(client: TestClient) -> None:
    """3. GET /api/intersections returns the 4 known Urban Grid intersections."""
    res = client.get("/api/intersections")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, list)
    assert set(data) == {"I1", "I2", "I3", "I4"}


@REQUIRES_SUMO
def test_get_traffic_state_i1_returns_200(client: TestClient) -> None:
    """4. GET /api/traffic-state/I1 returns HTTP 200."""
    res = client.get("/api/traffic-state/I1")
    assert res.status_code == 200


@REQUIRES_SUMO
def test_i1_state_matches_canonical_traffic_state_structure(client: TestClient) -> None:
    """5. Returned I1 payload strictly validates against canonical TrafficState."""
    res = client.get("/api/traffic-state/I1")
    assert res.status_code == 200

    data = res.json()
    # Validate against canonical Pydantic model
    state = TrafficState.model_validate(data)
    assert state.intersection_id == "I1"
    assert state.timestamp >= 0.0
    assert len(state.lane_features) == 8
    assert state.total_queue >= 0
    assert state.mean_speed >= 0.0
    assert state.density >= 0.0
    assert state.signal_phase in {"RED", "YELLOW", "GREEN"}
    assert state.green_remaining >= 0.0


@REQUIRES_SUMO
def test_all_four_intersections_individually_return_valid_traffic_state(client: TestClient) -> None:
    """6. I1-I4 each return valid canonical TrafficState objects."""
    for iid in ["I1", "I2", "I3", "I4"]:
        res = client.get(f"/api/traffic-state/{iid}")
        assert res.status_code == 200

        state = TrafficState.model_validate(res.json())
        assert state.intersection_id == iid
        assert len(state.lane_features) == 8


@REQUIRES_SUMO
def test_get_all_traffic_states(client: TestClient) -> None:
    """7. GET /api/traffic-state returns all four intersection states."""
    res = client.get("/api/traffic-state")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"I1", "I2", "I3", "I4"}

    for iid, raw_state in data.items():
        state = TrafficState.model_validate(raw_state)
        assert state.intersection_id == iid


@REQUIRES_SUMO
def test_all_returned_states_share_same_timestamp(client: TestClient) -> None:
    """8. All states returned by GET /api/traffic-state share the exact same timestamp."""
    res = client.get("/api/traffic-state")
    assert res.status_code == 200

    data = res.json()
    timestamps = {state["timestamp"] for state in data.values()}
    assert len(timestamps) == 1


@REQUIRES_SUMO
def test_invalid_intersection_returns_404(client: TestClient) -> None:
    """9. Requesting an unknown intersection returns HTTP 404."""
    res = client.get("/api/traffic-state/UNKNOWN_INTERSECTION")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@REQUIRES_SUMO
def test_signal_phase_is_only_canonical(client: TestClient) -> None:
    """10. Signal phase across all intersections is strictly RED, YELLOW, or GREEN."""
    res = client.get("/api/traffic-state")
    assert res.status_code == 200

    for state in res.json().values():
        assert state["signal_phase"] in {"RED", "YELLOW", "GREEN"}


@REQUIRES_SUMO
def test_reading_state_does_not_advance_sumo(client: TestClient) -> None:
    """11. Reading state via GET requests does not advance the SUMO simulation clock."""
    res1 = client.get("/api/traffic-state")
    t1 = res1.json()["I1"]["timestamp"]

    res2 = client.get("/api/traffic-state/I1")
    t2 = res2.json()["timestamp"]

    res3 = client.get("/api/traffic-state")
    t3 = res3.json()["I1"]["timestamp"]

    assert t1 == t2 == t3


@REQUIRES_SUMO
def test_step_endpoint_advances_simulation(client: TestClient) -> None:
    """12. POST /api/simulation/step advances simulation by requested steps."""
    res_before = client.get("/api/traffic-state")
    t_start = res_before.json()["I1"]["timestamp"]

    # Step by 1 (default)
    res_step1 = client.post("/api/simulation/step")
    assert res_step1.status_code == 200
    t_step1 = res_step1.json()["I1"]["timestamp"]
    assert t_step1 == t_start + 1.0

    # Step by 2
    res_step2 = client.post("/api/simulation/step", json={"steps": 2})
    assert res_step2.status_code == 200
    t_step2 = res_step2.json()["I1"]["timestamp"]
    assert t_step2 == t_step1 + 2.0


@REQUIRES_SUMO
def test_simulation_shutdown_clean() -> None:
    """13. Simulation shutdown terminates TraCI cleanly and allows re-connection."""
    with TestClient(app) as test_client:
        res = test_client.get("/health")
        assert res.status_code == 200
        assert res.json()["simulation_connected"] is True

    # Shutdown called via fixture / lifespan
    stop_simulation()

    # Verify subsequent client launch can reconnect smoothly
    with TestClient(app) as test_client2:
        res2 = test_client2.get("/health")
        assert res2.status_code == 200
        assert res2.json()["simulation_connected"] is True
