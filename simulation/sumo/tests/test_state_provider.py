"""Automated test suite for TrafficStateProvider."""

from __future__ import annotations

import pytest

from shared.schemas.traffic_state import TrafficState
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import (
    TraCIBridge,
    TraCIBridgeError,
    is_sumo_available,
)

REQUIRES_SUMO = pytest.mark.skipif(
    not is_sumo_available(),
    reason="SUMO executable or traci package is unavailable in this environment.",
)


# =============================================================================
# Disconnected & Validation Error Tests
# =============================================================================


def test_provider_disconnected_bridge_raises_error() -> None:
    """Operations on an unstarted/disconnected bridge must raise TraCIBridgeError."""
    bridge = TraCIBridge()
    assert not bridge.is_connected
    provider = TrafficStateProvider(bridge)

    with pytest.raises(TraCIBridgeError, match="must be connected"):
        _ = provider.simulation_time

    with pytest.raises(TraCIBridgeError, match="must be connected"):
        _ = provider.intersection_ids

    with pytest.raises(TraCIBridgeError, match="must be connected"):
        provider.get_state("I1")

    with pytest.raises(TraCIBridgeError, match="must be connected"):
        provider.get_all_states()

    with pytest.raises(TraCIBridgeError, match="must be connected"):
        provider.step_and_get_states()


@REQUIRES_SUMO
def test_provider_invalid_intersection_id_rejected() -> None:
    """Requesting an invalid or non-monitored intersection ID raises ValueError."""
    with TraCIBridge() as bridge:
        provider = TrafficStateProvider(bridge)

        with pytest.raises(ValueError, match="Invalid intersection ID 'INVALID_INT'"):
            provider.get_state("INVALID_INT")

        with pytest.raises(ValueError, match="Invalid intersection ID ''"):
            provider.get_state("")


# =============================================================================
# Real SUMO Integration Tests: Provider Operations
# =============================================================================


@REQUIRES_SUMO
def test_provider_initialization_with_working_bridge() -> None:
    """1. Provider initializes with a working TraCI bridge and exposes properties."""
    with TraCIBridge() as bridge:
        provider = TrafficStateProvider(bridge)
        assert provider.bridge is bridge
        assert provider.is_connected
        assert provider.simulation_time == 0.0
        assert set(provider.intersection_ids) == {"I1", "I2", "I3", "I4"}


@REQUIRES_SUMO
def test_get_state_single_intersection() -> None:
    """2 & 4. get_state('I1') returns a canonical TrafficState with matching intersection_id."""
    with TraCIBridge() as bridge:
        provider = TrafficStateProvider(bridge)
        state_i1 = provider.get_state("I1")

        assert isinstance(state_i1, TrafficState)
        assert state_i1.intersection_id == "I1"


@REQUIRES_SUMO
def test_get_state_all_four_intersections() -> None:
    """3 & 4. get_state works for all four intersections (I1, I2, I3, I4)."""
    with TraCIBridge() as bridge:
        provider = TrafficStateProvider(bridge)

        for iid in ["I1", "I2", "I3", "I4"]:
            state = provider.get_state(iid)
            assert isinstance(state, TrafficState)
            assert state.intersection_id == iid


@REQUIRES_SUMO
def test_timestamp_matches_sumo_simulation_time() -> None:
    """5. State timestamp strictly matches SUMO simulation time across step increments."""
    with TraCIBridge() as bridge:
        provider = TrafficStateProvider(bridge)

        # t = 0.0
        assert provider.get_state("I1").timestamp == 0.0

        # t = 3.0
        bridge.step_many(3)
        assert provider.get_state("I1").timestamp == 3.0

        # t = 7.0
        bridge.step_many(4)
        assert provider.get_state("I2").timestamp == 7.0


@REQUIRES_SUMO
def test_lane_features_populated_correctly() -> None:
    """6. lane_features contains 8 valid incoming lanes with non-negative metrics."""
    with TraCIBridge() as bridge:
        bridge.step_many(2)
        provider = TrafficStateProvider(bridge)
        state = provider.get_state("I1")

        assert len(state.lane_features) == 8
        for lf in state.lane_features:
            assert isinstance(lf.lane_id, str)
            assert not lf.lane_id.startswith(":")
            assert lf.vehicle_count >= 0
            assert lf.mean_speed >= 0.0
            assert lf.queue_length >= 0
            assert 0.0 <= lf.occupancy <= 1.0
            assert lf.density >= 0.0
            assert lf.flow >= 0.0
            assert lf.arrival_rate >= 0.0


@REQUIRES_SUMO
def test_signal_phase_is_strictly_canonical() -> None:
    """7. signal_phase is strictly one of RED, YELLOW, GREEN."""
    with TraCIBridge() as bridge:
        provider = TrafficStateProvider(bridge)

        for _ in range(35):
            for iid in ["I1", "I2", "I3", "I4"]:
                state = provider.get_state(iid)
                assert state.signal_phase in {"RED", "YELLOW", "GREEN"}
                assert state.green_remaining >= 0.0
                if state.signal_phase != "GREEN":
                    assert state.green_remaining == 0.0
            bridge.step()


@REQUIRES_SUMO
def test_get_all_states_returns_all_four_with_identical_timestamp() -> None:
    """8 & 9. get_all_states() returns all 4 intersections with identical simulation timestamp."""
    with TraCIBridge() as bridge:
        bridge.step_many(4)
        provider = TrafficStateProvider(bridge)

        states = provider.get_all_states()
        assert set(states.keys()) == {"I1", "I2", "I3", "I4"}

        # Verify all four states share the exact same timestamp
        timestamps = {s.timestamp for s in states.values()}
        assert len(timestamps) == 1
        assert timestamps.pop() == 4.0

        # Verify simulation time was not advanced during get_all_states
        assert bridge.simulation_time == 4.0


@REQUIRES_SUMO
def test_step_and_get_states_advancement() -> None:
    """10 & 11. step_and_get_states() advances simulation exactly once and returns states at new time."""
    with TraCIBridge() as bridge:
        provider = TrafficStateProvider(bridge)
        assert bridge.simulation_time == 0.0

        # Advance 1 step
        states_1 = provider.step_and_get_states(1)
        assert bridge.simulation_time == 1.0
        for state in states_1.values():
            assert state.timestamp == 1.0

        # Advance 3 steps
        states_4 = provider.step_and_get_states(3)
        assert bridge.simulation_time == 4.0
        for state in states_4.values():
            assert state.timestamp == 4.0

        # Calling with 0 steps does not advance
        states_still_4 = provider.step_and_get_states(0)
        assert bridge.simulation_time == 4.0
        for state in states_still_4.values():
            assert state.timestamp == 4.0


@REQUIRES_SUMO
def test_traffic_state_serialization_from_provider() -> None:
    """14. TrafficState instances returned by provider cleanly serialize to dict and JSON."""
    with TraCIBridge() as bridge:
        bridge.step_many(2)
        provider = TrafficStateProvider(bridge)

        state = provider.get_state("I1")
        data_dict = state.model_dump()
        assert isinstance(data_dict, dict)
        assert data_dict["intersection_id"] == "I1"
        assert len(data_dict["lane_features"]) == 8

        # JSON round-trip validation
        json_str = state.model_dump_json()
        assert isinstance(json_str, str)
        recreated = TrafficState.model_validate_json(json_str)
        assert recreated == state


@REQUIRES_SUMO
def test_provider_context_manager() -> None:
    """Provider supports context manager delegation to the bridge."""
    bridge = TraCIBridge()
    provider = TrafficStateProvider(bridge)
    assert not bridge.is_connected

    with provider:
        assert provider.is_connected
        state = provider.get_state("I1")
        assert state.timestamp == 0.0

    assert not provider.is_connected
    assert not bridge.is_connected


@REQUIRES_SUMO
def test_provider_reset() -> None:
    """Calling reset() clears sensor temporal state without error."""
    with TraCIBridge() as bridge:
        provider = TrafficStateProvider(bridge)
        bridge.step_many(2)
        _ = provider.get_all_states()
        provider.reset()
        # Next measurement runs cleanly with reset state
        states = provider.get_all_states()
        assert len(states) == 4
