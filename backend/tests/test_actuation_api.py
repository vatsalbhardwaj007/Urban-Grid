"""Tests for M1 -> M2 Action ingestion REST endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import stop_simulation
from backend.api.main import app
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


class TestControlActionAPI:
    """Test suite for POST /api/control/signal and POST /api/control/route."""

    @REQUIRES_SUMO
    def test_post_control_signal_valid(self, client: TestClient) -> None:
        """1. POST /api/control/signal succeeds with valid SignalAction."""
        payload = {
            "target": "I1",
            "green_duration": 40.0,
            "source": "AI",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/signal", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["success"] is True
        assert data["target"] == "I1"
        assert data["applied_duration"] == 40.0
        assert data["source"] == "AI"
        assert "message" in data

    @REQUIRES_SUMO
    def test_post_control_signal_unknown_target_returns_400(self, client: TestClient) -> None:
        """2. POST /api/control/signal with unknown target returns HTTP 400."""
        payload = {
            "target": "I_UNKNOWN",
            "green_duration": 40.0,
            "source": "AI",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/signal", json=payload)
        assert res.status_code == 400
        assert "unknown" in res.json()["detail"].lower()

    @REQUIRES_SUMO
    def test_post_control_signal_invalid_duration_returns_400(self, client: TestClient) -> None:
        """3. POST /api/control/signal with out-of-bounds duration returns HTTP 400."""
        payload = {
            "target": "I1",
            "green_duration": 250.0,
            "source": "AI",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/signal", json=payload)
        assert res.status_code == 400
        assert "invalid" in res.json()["detail"].lower()

    @REQUIRES_SUMO
    def test_post_control_route_valid(self, client: TestClient) -> None:
        """4. POST /api/control/route succeeds with valid RouteAction."""
        # Step once to insert flow vehicles
        client.post("/api/simulation/step")

        payload = {
            "target": "flow_norm_prim.0",
            "route": ["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"],
            "source": "AI",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/route", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["success"] is True
        assert data["target"] == "flow_norm_prim.0"
        assert data["applied_route"] == ["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"]
        assert data["source"] == "AI"

    @REQUIRES_SUMO
    def test_post_control_route_unknown_vehicle_returns_400(self, client: TestClient) -> None:
        """5. POST /api/control/route with unknown vehicle returns HTTP 400."""
        payload = {
            "target": "nonexistent_vehicle_xyz",
            "route": ["E_W1_I1", "E_I1_I2"],
            "source": "MANUAL",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/route", json=payload)
        assert res.status_code == 400
        assert "not active" in res.json()["detail"].lower() or "not exist" in res.json()["detail"].lower()

    @REQUIRES_SUMO
    def test_post_control_route_unknown_edge_returns_400(self, client: TestClient) -> None:
        """6. POST /api/control/route with invalid edge returns HTTP 400."""
        client.post("/api/simulation/step")

        payload = {
            "target": "flow_norm_prim.0",
            "route": ["E_W1_I1", "E_UNKNOWN_EDGE"],
            "source": "AI",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/route", json=payload)
        assert res.status_code == 400
        assert "does not exist" in res.json()["detail"].lower()

    @REQUIRES_SUMO
    def test_post_control_route_disconnected_route_returns_400(self, client: TestClient) -> None:
        """7. POST /api/control/route with disconnected route returns HTTP 400."""
        client.post("/api/simulation/step")

        payload = {
            "target": "flow_norm_prim.0",
            "route": ["E_W1_I1", "E_I4_E4"],
            "source": "AI",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/route", json=payload)
        assert res.status_code == 400
        assert "cannot be applied" in res.json()["detail"].lower() or "no connection" in res.json()["detail"].lower()
