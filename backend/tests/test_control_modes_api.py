"""REST API integration tests for control mode endpoints.

Verifies:
- GET /api/control/mode defaults to AUTO
- POST /api/control/mode transitions AUTO -> MANUAL -> EMERGENCY -> AUTO
- POST /api/control/mode rejects invalid mode with 422
- GET /api/control/loop/status reflects updated mode
- Signal actuation permission checks based on mode
"""

from __future__ import annotations

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


class TestControlModesAPI:
    """Test suite for GET /api/control/mode and POST /api/control/mode."""

    @REQUIRES_SUMO
    def test_get_control_mode_default_auto(self, client: TestClient) -> None:
        """1. GET /api/control/mode returns AUTO as initial default."""
        res = client.get("/api/control/mode")
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "AUTO"
        assert "description" in data
        assert data["previous_mode"] is None

    @REQUIRES_SUMO
    def test_post_control_mode_transitions(self, client: TestClient) -> None:
        """2. POST /api/control/mode updates mode through AUTO -> MANUAL -> EMERGENCY -> AUTO."""
        # 1. Transition to MANUAL
        res = client.post("/api/control/mode", json={"mode": "MANUAL"})
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "MANUAL"
        assert data["previous_mode"] == "AUTO"

        # Verify GET reflects MANUAL
        res_get = client.get("/api/control/mode")
        assert res_get.status_code == 200
        assert res_get.json()["mode"] == "MANUAL"

        # Verify loop status reports MANUAL
        res_status = client.get("/api/control/loop/status")
        assert res_status.status_code == 200
        assert res_status.json()["mode"] == "MANUAL"

        # 2. Transition to EMERGENCY
        res_emg = client.post("/api/control/mode", json={"mode": "EMERGENCY"})
        assert res_emg.status_code == 200
        assert res_emg.json()["mode"] == "EMERGENCY"
        assert res_emg.json()["previous_mode"] == "MANUAL"

        # 3. Transition back to AUTO
        res_auto = client.post("/api/control/mode", json={"mode": "AUTO"})
        assert res_auto.status_code == 200
        assert res_auto.json()["mode"] == "AUTO"
        assert res_auto.json()["previous_mode"] == "EMERGENCY"

    @REQUIRES_SUMO
    def test_post_control_mode_invalid_rejected(self, client: TestClient) -> None:
        """3. POST /api/control/mode with invalid mode returns HTTP 422 Unprocessable Entity."""
        res = client.post("/api/control/mode", json={"mode": "INVALID_MODE"})
        assert res.status_code == 422

    @REQUIRES_SUMO
    def test_manual_signal_allowed_in_manual_mode(self, client: TestClient) -> None:
        """4. Operator manual signal actions succeed via /api/control/signal during MANUAL mode."""
        # Set to MANUAL
        client.post("/api/control/mode", json={"mode": "MANUAL"})

        payload = {
            "target": "I1",
            "green_duration": 40.0,
            "source": "MANUAL",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/signal", json=payload)
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["source"] == "MANUAL"

    @REQUIRES_SUMO
    def test_ai_signal_rejected_in_manual_mode(self, client: TestClient) -> None:
        """5. AI signal actions sent via /api/control/signal are rejected with 403 in MANUAL mode."""
        # Set to MANUAL
        client.post("/api/control/mode", json={"mode": "MANUAL"})

        payload = {
            "target": "I1",
            "green_duration": 40.0,
            "source": "AI",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/signal", json=payload)
        assert res.status_code == 403
        assert "restricted in manual" in res.json()["detail"].lower()

    @REQUIRES_SUMO
    def test_ai_signal_rejected_in_emergency_mode(self, client: TestClient) -> None:
        """6. AI signal actions sent via /api/control/signal are rejected with 403 in EMERGENCY mode."""
        # Set to EMERGENCY
        client.post("/api/control/mode", json={"mode": "EMERGENCY"})

        payload = {
            "target": "I1",
            "green_duration": 40.0,
            "source": "AI",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        res = client.post("/api/control/signal", json=payload)
        assert res.status_code == 403
        assert "cannot override emergency" in res.json()["detail"].lower()
