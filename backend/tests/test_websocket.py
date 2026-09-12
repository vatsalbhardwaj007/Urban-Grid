"""Tests for M2 live traffic WebSocket stream.

Architecture under test:
SUMO -> M2 -> WebSocket -> M3/M4
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import stop_simulation
from backend.api.main import app
from backend.api.websocket import get_connection_manager
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


class TestTrafficWebSocketStream:
    """Test suite for /ws/traffic WebSocket stream and event broadcasting."""

    @REQUIRES_SUMO
    def test_websocket_connection_succeeds(self, client: TestClient) -> None:
        """1. Client can successfully connect to /ws/traffic."""
        with client.websocket_connect("/ws/traffic") as ws:
            # Connection handshake succeeded if context manager is entered
            assert ws is not None

    @REQUIRES_SUMO
    def test_valid_traffic_update_event_received(self, client: TestClient) -> None:
        """2. Client immediately receives valid 'traffic.update' event upon connection."""
        with client.websocket_connect("/ws/traffic") as ws:
            event = ws.receive_json()
            assert isinstance(event, dict)
            assert event.get("event") == "traffic.update"
            assert "data" in event
            assert isinstance(event["data"], dict)

    @REQUIRES_SUMO
    def test_event_contains_valid_canonical_traffic_state(self, client: TestClient) -> None:
        """3. Event payload strictly validates against canonical TrafficState schema."""
        with client.websocket_connect("/ws/traffic") as ws:
            event = ws.receive_json()
            raw_state = event["data"]

            # Validate against canonical TrafficState Pydantic model
            state = TrafficState.model_validate(raw_state)
            assert state.intersection_id in {"I1", "I2", "I3", "I4"}
            assert state.timestamp >= 0.0
            assert len(state.lane_features) == 8
            assert state.total_queue >= 0
            assert state.mean_speed >= 0.0
            assert state.arrival_rate >= 0.0
            assert state.density >= 0.0
            assert state.signal_phase in {"RED", "YELLOW", "GREEN"}
            assert state.green_remaining >= 0.0

    @REQUIRES_SUMO
    def test_initial_snapshot_covers_all_intersections(self, client: TestClient) -> None:
        """4. Initial connection delivers state for all 4 intersections."""
        with client.websocket_connect("/ws/traffic") as ws:
            received_intersections = set()
            for _ in range(4):
                event = ws.receive_json()
                assert event["event"] == "traffic.update"
                state = TrafficState.model_validate(event["data"])
                received_intersections.add(state.intersection_id)

            assert received_intersections == {"I1", "I2", "I3", "I4"}

    @REQUIRES_SUMO
    def test_multiple_clients_can_connect(self, client: TestClient) -> None:
        """5. Multiple clients can connect simultaneously and both receive stream events."""
        with client.websocket_connect("/ws/traffic") as ws1:
            with client.websocket_connect("/ws/traffic") as ws2:
                # Both receive initial snapshots
                ev1 = ws1.receive_json()
                ev2 = ws2.receive_json()
                assert ev1["event"] == "traffic.update"
                assert ev2["event"] == "traffic.update"
                assert TrafficState.model_validate(ev1["data"])
                assert TrafficState.model_validate(ev2["data"])

    @REQUIRES_SUMO
    def test_simulation_step_broadcasts_to_connected_clients(self, client: TestClient) -> None:
        """6. Stepping simulation broadcasts new TrafficState with advanced timestamp."""
        with client.websocket_connect("/ws/traffic") as ws:
            # Drain 4 initial messages
            initial_states = [ws.receive_json() for _ in range(4)]
            t_initial = initial_states[0]["data"]["timestamp"]

            # Advance simulation via REST endpoint
            res = client.post("/api/simulation/step", json={"steps": 1})
            assert res.status_code == 200

            # WebSocket client receives step broadcast for the 4 intersections
            broadcast_states = [ws.receive_json() for _ in range(4)]
            for ev in broadcast_states:
                assert ev["event"] == "traffic.update"
                state = TrafficState.model_validate(ev["data"])
                assert state.timestamp == t_initial + 1.0

    @REQUIRES_SUMO
    def test_disconnect_cleanup_no_stale_clients(self, client: TestClient) -> None:
        """7. Disconnecting a client cleans up connection manager without leaking."""
        manager = get_connection_manager()
        count_before = manager.active_connections_count

        with client.websocket_connect("/ws/traffic") as ws:
            assert manager.active_connections_count == count_before + 1
            ws.receive_json()

        # After exiting context manager, client is disconnected
        assert manager.active_connections_count == count_before

    @REQUIRES_SUMO
    def test_malformed_client_message_does_not_crash_server(self, client: TestClient) -> None:
        """8. Malformed or invalid incoming messages do not crash server or stream."""
        with client.websocket_connect("/ws/traffic") as ws:
            # Drain one initial message
            ws.receive_json()

            # Send arbitrary malformed text
            ws.send_text("INVALID NON JSON TEXT")
            ws.send_text("{bad json: true}")
            ws.send_text(r'{"action": "unknown_action_xyz"}')

            # Server remains healthy and operational
            res = client.get("/health")
            assert res.status_code == 200
            assert res.json()["status"] == "ok"

    @REQUIRES_SUMO
    def test_client_ping_receives_pong(self, client: TestClient) -> None:
        """9. Client ping message receives pong response."""
        with client.websocket_connect("/ws/traffic") as ws:
            # Drain 4 initial state messages
            for _ in range(4):
                ws.receive_json()

            # Send ping
            ws.send_json({"action": "ping"})
            resp = ws.receive_json()
            assert resp == {"event": "pong"}

    @REQUIRES_SUMO
    def test_existing_rest_endpoints_continue_working(self, client: TestClient) -> None:
        """10. Existing REST traffic-state endpoints remain fully functional."""
        # /health
        res_health = client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json()["simulation_connected"] is True

        # /api/intersections
        res_intersections = client.get("/api/intersections")
        assert res_intersections.status_code == 200
        assert set(res_intersections.json()) == {"I1", "I2", "I3", "I4"}

        # /api/traffic-state/I1
        res_i1 = client.get("/api/traffic-state/I1")
        assert res_i1.status_code == 200
        state_i1 = TrafficState.model_validate(res_i1.json())
        assert state_i1.intersection_id == "I1"

        # /api/traffic-state
        res_all = client.get("/api/traffic-state")
        assert res_all.status_code == 200
        assert set(res_all.json().keys()) == {"I1", "I2", "I3", "I4"}

        # /api/simulation/step
        res_step = client.post("/api/simulation/step", json={"steps": 1})
        assert res_step.status_code == 200
        assert set(res_step.json().keys()) == {"I1", "I2", "I3", "I4"}
