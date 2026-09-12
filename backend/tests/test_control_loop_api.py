"""Tests for control loop REST API endpoints."""

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


class TestControlLoopAPI:
    """Test suite for GET /api/control/loop/status and POST /api/control/loop/step."""

    @REQUIRES_SUMO
    def test_get_control_loop_status(self, client: TestClient) -> None:
        """1. GET /api/control/loop/status returns valid status representation."""
        res = client.get("/api/control/loop/status")
        assert res.status_code == 200

        data = res.json()
        assert "is_running" in data
        assert "current_cycle" in data
        assert "step_interval" in data
        assert "cycle_delay" in data
        assert "error_policy" in data
        assert "decision_engine" in data

    @REQUIRES_SUMO
    def test_post_control_loop_step(self, client: TestClient) -> None:
        """2. POST /api/control/loop/step executes a closed-loop cycle and returns report."""
        res = client.post("/api/control/loop/step")
        assert res.status_code == 200

        data = res.json()
        assert data["success"] is True
        assert data["cycle"] >= 1
        assert "states" in data
        assert set(data["states"].keys()) == {"I1", "I2", "I3", "I4"}
        assert "simulation_time" in data
        assert data["simulation_time"] >= 0.0

    @REQUIRES_SUMO
    def test_repeated_loop_steps_advance_cycle_and_time(self, client: TestClient) -> None:
        """3. Calling /step multiple times increments cycle counter and simulation time."""
        res1 = client.post("/api/control/loop/step")
        assert res1.status_code == 200
        cycle1 = res1.json()["cycle"]
        t1 = res1.json()["simulation_time"]

        res2 = client.post("/api/control/loop/step")
        assert res2.status_code == 200
        cycle2 = res2.json()["cycle"]
        t2 = res2.json()["simulation_time"]

        assert cycle2 == cycle1 + 1
        assert t2 == t1 + 1.0
