"""Automated test suite for TraCIBridge."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from simulation.sumo.traci_bridge import (
    TraCIBridge,
    TraCIBridgeError,
    find_sumo_binary,
    is_sumo_available,
)

SUMO_CFG_PATH = Path(__file__).resolve().parent.parent / "urban_grid.sumocfg"
REQUIRES_SUMO = pytest.mark.skipif(
    not is_sumo_available(),
    reason="SUMO executable or traci package is unavailable in this environment.",
)
REQUIRES_SUMO_GUI = pytest.mark.skipif(
    not is_sumo_available(use_gui=True),
    reason="SUMO-GUI executable or traci package is unavailable in this environment.",
)


# =============================================================================
# Binary Resolution & Static Error Tests (Do not require running SUMO)
# =============================================================================


@REQUIRES_SUMO
def test_find_sumo_binary_headless() -> None:
    """find_sumo_binary resolves an existing sumo executable."""
    bin_path = find_sumo_binary(use_gui=False)
    assert bin_path is not None
    assert Path(bin_path).exists()
    assert "sumo" in Path(bin_path).name.lower()


@REQUIRES_SUMO_GUI
def test_find_sumo_binary_gui() -> None:
    """find_sumo_binary resolves an existing sumo-gui executable."""
    bin_path = find_sumo_binary(use_gui=True)
    assert bin_path is not None
    assert Path(bin_path).exists()
    assert "sumo-gui" in Path(bin_path).name.lower()


def test_find_sumo_binary_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """find_sumo_binary raises TraCIBridgeError if binary cannot be resolved."""
    # Hide sumolib, SUMO_HOME, and PATH
    monkeypatch.setattr("simulation.sumo.traci_bridge.sumolib", None)
    monkeypatch.delenv("SUMO_HOME", raising=False)
    monkeypatch.setenv("PATH", "")

    with pytest.raises(TraCIBridgeError, match="could not be located"):
        find_sumo_binary(use_gui=False)


def test_operations_before_connect_raise_error() -> None:
    """Calling inspection or stepping methods prior to connect() must raise TraCIBridgeError."""
    bridge = TraCIBridge()
    assert not bridge.is_connected

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.step()

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.step_many(3)

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        _ = bridge.simulation_time

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        _ = bridge.current_time

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        _ = bridge.has_active_vehicles

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_vehicle_ids()

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_vehicle_state("non_existent_vehicle")

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_all_vehicles()

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_lane_ids()

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_lane_state("E_W1_I1_0")

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_all_lanes()

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_lane_vehicle_count("E_W1_I1_0")

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_lane_vehicle_ids("E_W1_I1_0")

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_traffic_light_ids()

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_traffic_light_state("I1")

    with pytest.raises(TraCIBridgeError, match="Bridge is not connected"):
        bridge.get_all_traffic_lights()


def test_close_when_not_connected_is_safe() -> None:
    """Repeated close() on an unstarted or already closed bridge must not fail."""
    bridge = TraCIBridge()
    assert not bridge.is_connected
    bridge.close()
    assert not bridge.is_connected
    bridge.close()  # Repeated call
    assert not bridge.is_connected


def test_start_missing_config_raises_file_not_found() -> None:
    """Starting with a non-existent configuration path raises FileNotFoundError."""
    invalid_path = Path("simulation/sumo/non_existent_config.sumocfg")
    bridge = TraCIBridge(config_path=invalid_path)
    with pytest.raises(FileNotFoundError):
        bridge.start()
    assert not bridge.is_connected
    bridge.close()


# =============================================================================
# Live Simulation Tests (Require local SUMO installation)
# =============================================================================


@REQUIRES_SUMO
def test_bridge_lifecycle_and_idempotent_close() -> None:
    """Bridge starts SUMO, connects TraCI, closes cleanly, and handles repeat close."""
    bridge = TraCIBridge(config_path=SUMO_CFG_PATH)
    try:
        assert not bridge.is_connected
        bridge.start()
        assert bridge.is_connected
        assert bridge.simulation_time == 0.0

        # Repeated start while already connected should be a no-op
        bridge.start()
        assert bridge.is_connected
    finally:
        bridge.close()

    assert not bridge.is_connected
    # Second close must be safe
    bridge.close()
    assert not bridge.is_connected


@REQUIRES_SUMO
def test_context_manager_lifecycle() -> None:
    """TraCIBridge works as a context manager and auto-closes on exit."""
    with TraCIBridge(config_path=SUMO_CFG_PATH) as bridge:
        assert bridge.is_connected
        assert bridge.current_time == 0.0
        bridge.step()
        assert bridge.current_time == 1.0

    assert not bridge.is_connected


@REQUIRES_SUMO
def test_simulation_stepping() -> None:
    """Single step and multi-step advancement properly update simulation time."""
    with TraCIBridge(config_path=SUMO_CFG_PATH) as bridge:
        assert bridge.simulation_time == 0.0

        # Single step
        t1 = bridge.step()
        assert t1 == 1.0
        assert bridge.simulation_time == 1.0

        # Step many
        t5 = bridge.step_many(4)
        assert t5 == 5.0
        assert bridge.simulation_time == 5.0

        # Non-positive steps are no-op
        t_same = bridge.step_many(0)
        assert t_same == 5.0
        t_neg = bridge.step_many(-2)
        assert t_neg == 5.0


@REQUIRES_SUMO
def test_vehicle_state_retrieval() -> None:
    """Live vehicle IDs, speeds, lane IDs, and states are correctly observable."""
    with TraCIBridge(config_path=SUMO_CFG_PATH) as bridge:
        # Advance 2 steps so that initial flows enter the network
        bridge.step_many(2)

        veh_ids = bridge.get_vehicle_ids()
        assert len(veh_ids) > 0, "Expected vehicles to be present after initial steps"

        # Check individual vehicle state
        sample_vid = veh_ids[0]
        v_state = bridge.get_vehicle_state(sample_vid)
        assert v_state["vehicle_id"] == sample_vid
        assert isinstance(v_state["speed"], float)
        assert v_state["speed"] >= 0.0
        assert isinstance(v_state["lane_id"], str)
        assert len(v_state["lane_id"]) > 0
        assert isinstance(v_state["lane_position"], float)
        assert isinstance(v_state["route_id"], str)
        assert isinstance(v_state["type_id"], str)
        assert isinstance(v_state["waiting_time"], float)

        # Check all vehicles batch retrieval
        all_vehicles = bridge.get_all_vehicles()
        assert len(all_vehicles) == len(veh_ids)
        retrieved_ids = [v["vehicle_id"] for v in all_vehicles]
        assert retrieved_ids == veh_ids


@REQUIRES_SUMO
def test_lane_state_retrieval() -> None:
    """Lanes, lane-level vehicle counts, speeds, and occupancies are observable."""
    with TraCIBridge(config_path=SUMO_CFG_PATH) as bridge:
        bridge.step_many(2)

        # Normal lanes (internal excluded)
        lanes = bridge.get_lane_ids(include_internal=False)
        assert len(lanes) == 48, f"Expected 48 network lanes (24 edges * 2 lanes), got {len(lanes)}"
        assert not any(lid.startswith(":") for lid in lanes)

        # Internal lanes parameter check
        all_lane_ids = bridge.get_lane_ids(include_internal=True)
        assert len(all_lane_ids) >= len(lanes)

        # Inspect individual lane state
        sample_lane = lanes[0]
        lane_state = bridge.get_lane_state(sample_lane)
        assert lane_state["lane_id"] == sample_lane
        assert isinstance(lane_state["vehicle_count"], int)
        assert lane_state["vehicle_count"] >= 0
        assert isinstance(lane_state["mean_speed"], float)
        assert lane_state["mean_speed"] >= 0.0
        assert isinstance(lane_state["occupancy"], float)
        assert isinstance(lane_state["length"], float)
        assert lane_state["length"] > 0.0
        assert isinstance(lane_state["max_speed"], float)
        assert lane_state["max_speed"] > 0.0
        assert isinstance(lane_state["vehicle_ids"], list)

        # Direct vehicle count and ID methods
        v_count = bridge.get_lane_vehicle_count(sample_lane)
        v_ids = bridge.get_lane_vehicle_ids(sample_lane)
        assert v_count == lane_state["vehicle_count"]
        assert len(v_ids) == v_count

        # All lanes batch
        all_lanes = bridge.get_all_lanes(include_internal=False)
        assert len(all_lanes) == len(lanes)


@REQUIRES_SUMO
def test_traffic_light_state_retrieval() -> None:
    """Traffic light IDs, signal states, phase names, and remaining times are observable."""
    with TraCIBridge(config_path=SUMO_CFG_PATH) as bridge:
        tls_ids = bridge.get_traffic_light_ids()
        assert set(tls_ids) == {"I1", "I2", "I3", "I4"}

        # Check initial state at t=0
        state_i1 = bridge.get_traffic_light_state("I1")
        assert state_i1["tls_id"] == "I1"
        assert state_i1["phase_name"] == "NS_GREEN"
        assert state_i1["state"] == "GGGgrrrrGGGgrrrr"
        assert state_i1["phase_duration"] == 31.0
        assert state_i1["remaining_phase_time"] == 31.0
        assert state_i1["next_switch"] == 31.0

        # Advance 10 steps and verify remaining phase time decreases accurately
        bridge.step_many(10)
        state_i1_t10 = bridge.get_traffic_light_state("I1")
        assert state_i1_t10["phase_name"] == "NS_GREEN"
        assert state_i1_t10["remaining_phase_time"] == 21.0

        # Batch retrieval for all traffic lights
        all_tls = bridge.get_all_traffic_lights()
        assert len(all_tls) == 4
        all_ids = {tls["tls_id"] for tls in all_tls}
        assert all_ids == {"I1", "I2", "I3", "I4"}


@REQUIRES_SUMO_GUI
def test_gui_mode_execution() -> None:
    """TraCIBridge correctly launches SUMO-GUI when use_gui=True and shuts down cleanly."""
    with TraCIBridge(config_path=SUMO_CFG_PATH, use_gui=True) as bridge:
        assert bridge.is_connected
        assert bridge.simulation_time == 0.0
        bridge.step()
        assert bridge.simulation_time == 1.0

    assert not bridge.is_connected


@REQUIRES_SUMO
def test_multi_bridge_sequential_execution() -> None:
    """Multiple bridges can run sequentially without port/label collisions or process leaks."""
    for i in range(2):
        with TraCIBridge(config_path=SUMO_CFG_PATH, label=f"seq_test_{i}") as bridge:
            assert bridge.is_connected
            bridge.step_many(3)
            assert bridge.simulation_time == 3.0
            assert len(bridge.get_vehicle_ids()) > 0
        assert not bridge.is_connected
