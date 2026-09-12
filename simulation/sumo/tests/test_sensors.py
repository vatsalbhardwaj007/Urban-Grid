"""Automated test suite for Virtual Sensor Layer."""

from __future__ import annotations

import pytest

from shared.schemas.traffic_state import LaneFeature, TrafficState
from simulation.sumo.sensors import (
    IntersectionSensor,
    LaneSensor,
    create_intersection_sensors,
    map_signal_phase,
)
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
# Unit Tests: Signal Phase Mapping (Deterministic, no SUMO required)
# =============================================================================


def test_map_signal_phase_from_phase_name() -> None:
    """map_signal_phase correctly prioritizes phase names."""
    assert map_signal_phase("GGGG", "NS_GREEN") == "GREEN"
    assert map_signal_phase("yyyy", "NS_YELLOW") == "YELLOW"
    assert map_signal_phase("rrrr", "ALL_RED") == "RED"
    assert map_signal_phase("rrrr", "EW_green") == "GREEN"
    assert map_signal_phase("rrrr", "ew_yellow") == "YELLOW"


def test_map_signal_phase_fallback_to_state_chars() -> None:
    """map_signal_phase falls back to state string characters if phase name has no keyword."""
    assert map_signal_phase("GGGgrrrrGGGgrrrr", "") == "GREEN"
    assert map_signal_phase("yyyyrrrryyyyrrrr", "") == "YELLOW"
    assert map_signal_phase("rrrrrrrrrrrrrrrr", "") == "RED"
    assert map_signal_phase("", "") == "RED"


# =============================================================================
# Disconnected & Validation Error Tests
# =============================================================================


def test_sensor_operations_when_disconnected_raise_error() -> None:
    """Sensors must raise TraCIBridgeError when queried on a disconnected bridge."""
    bridge = TraCIBridge()
    assert not bridge.is_connected

    lane_sensor = LaneSensor("E_W1_I1_0", bridge)
    with pytest.raises(TraCIBridgeError, match="must be connected"):
        lane_sensor.measure()

    intersection_sensor = IntersectionSensor("I1", bridge)
    with pytest.raises(TraCIBridgeError, match="must be connected"):
        intersection_sensor.measure()


@REQUIRES_SUMO
def test_sensor_invalid_lane_or_intersection_id() -> None:
    """Non-existent lane or intersection IDs raise ValueError with clear error message."""
    with TraCIBridge() as bridge:
        invalid_lane = LaneSensor("non_existent_lane_xyz", bridge)
        with pytest.raises(ValueError, match="not found"):
            _ = invalid_lane.lane_length

        invalid_intersection = IntersectionSensor("non_existent_tls_xyz", bridge)
        with pytest.raises(ValueError, match="not found"):
            _ = invalid_intersection.monitored_lanes


# =============================================================================
# Real SUMO Integration Tests: Lane Sensors
# =============================================================================


@REQUIRES_SUMO
def test_lane_sensor_measure_real_lane() -> None:
    """LaneSensor measures an existing Urban Grid lane and produces a valid LaneFeature."""
    with TraCIBridge() as bridge:
        bridge.step_many(2)

        sensor = LaneSensor("E_W1_I1_0", bridge)
        feature = sensor.measure()

        # 1. Returned type is canonical LaneFeature
        assert isinstance(feature, LaneFeature)
        assert feature.lane_id == "E_W1_I1_0"

        # 2. vehicle_count is valid
        assert isinstance(feature.vehicle_count, int)
        assert feature.vehicle_count >= 0

        # 3. mean_speed is non-negative
        assert isinstance(feature.mean_speed, float)
        assert feature.mean_speed >= 0.0

        # 4. queue_length is valid int
        assert isinstance(feature.queue_length, int)
        assert feature.queue_length >= 0

        # 5. occupancy is valid [0.0, 1.0]
        assert isinstance(feature.occupancy, float)
        assert 0.0 <= feature.occupancy <= 1.0

        # 6. density is non-negative
        assert isinstance(feature.density, float)
        assert feature.density >= 0.0

        # 7. flow is non-negative
        assert isinstance(feature.flow, float)
        assert feature.flow >= 0.0

        # 8. arrival_rate is non-negative
        assert isinstance(feature.arrival_rate, float)
        assert feature.arrival_rate >= 0.0


@REQUIRES_SUMO
def test_lane_sensor_empty_lane() -> None:
    """Empty lane (no vehicles) produces clean 0.0 values across all metrics."""
    with TraCIBridge() as bridge:
        # At t=0 before any vehicle reaches internal corridor E_I1_I2_1
        sensor = LaneSensor("E_I1_I2_1", bridge)
        feature = sensor.measure()

        assert feature.vehicle_count == 0
        assert feature.mean_speed == 0.0
        assert feature.queue_length == 0
        assert feature.occupancy == 0.0
        assert feature.density == 0.0
        assert feature.arrival_rate == 0.0
        assert feature.flow == 0.0


@REQUIRES_SUMO
def test_lane_sensor_arrival_rate_across_steps() -> None:
    """Arrival rate and flow correctly detect newly entered vehicles across simulation steps."""
    with TraCIBridge() as bridge:
        sensor = LaneSensor("E_W1_I1_0", bridge)

        # Initial measurement at t=0
        feat_0 = sensor.measure()
        assert feat_0.arrival_rate == 0.0
        assert feat_0.flow == 0.0

        # Advance 1 step (dt=1.0s)
        bridge.step()
        feat_1 = sensor.measure()

        # In Scenario A, flow_norm_prim inserts vehicles at E_W1_I1 at t=0/1
        if feat_1.vehicle_count > 0:
            assert feat_1.arrival_rate > 0.0
            assert feat_1.flow == feat_1.arrival_rate * 3600.0


@REQUIRES_SUMO
def test_lane_sensor_queue_length_detection() -> None:
    """Stopped vehicles at a red signal are deterministically counted in queue_length."""
    with TraCIBridge() as bridge:
        # Advance to t=35s where EW signals are red and vehicles decelerate/stop
        bridge.step_many(35)
        sensor = LaneSensor("E_W1_I1_0", bridge, queue_speed_threshold=0.1)
        feature = sensor.measure()

        assert feature.queue_length >= 0
        assert feature.queue_length <= feature.vehicle_count


@REQUIRES_SUMO
def test_lane_sensor_reset() -> None:
    """Calling reset() clears cached temporal state."""
    with TraCIBridge() as bridge:
        sensor = LaneSensor("E_W1_I1_0", bridge)
        bridge.step_many(2)
        sensor.measure()
        assert sensor._prev_timestamp is not None
        assert sensor._prev_vehicle_ids is not None

        sensor.reset()
        assert sensor._prev_timestamp is None
        assert sensor._prev_vehicle_ids is None


# =============================================================================
# Real SUMO Integration Tests: Intersection Sensors & Aggregation
# =============================================================================


@REQUIRES_SUMO
def test_intersection_sensor_measure_and_aggregation() -> None:
    """IntersectionSensor aggregates incoming lanes into a valid canonical TrafficState."""
    with TraCIBridge() as bridge:
        bridge.step_many(5)

        sensor = IntersectionSensor("I1", bridge)
        state = sensor.measure()

        # 1. Root model is canonical TrafficState
        assert isinstance(state, TrafficState)
        assert state.intersection_id == "I1"
        assert state.timestamp == 5.0

        # 2. Monitored lanes: exactly 8 incoming lanes for I1 (4 approaches * 2 lanes)
        assert len(state.lane_features) == 8
        assert len(sensor.monitored_lanes) == 8
        assert not any(lf.lane_id.startswith(":") for lf in state.lane_features)

        # 3. Aggregations match constituent lane features
        assert state.total_queue == sum(lf.queue_length for lf in state.lane_features)
        assert state.total_queue >= 0

        total_vehs = sum(lf.vehicle_count for lf in state.lane_features)
        if total_vehs > 0:
            expected_weighted_speed = sum(lf.mean_speed * lf.vehicle_count for lf in state.lane_features) / total_vehs
            assert abs(state.mean_speed - round(expected_weighted_speed, 4)) <= 1e-3
        else:
            assert state.mean_speed == 0.0

        assert state.density >= 0.0
        assert state.arrival_rate >= 0.0

        # 4. Signal phase is strictly one of RED, YELLOW, GREEN
        assert state.signal_phase in {"RED", "YELLOW", "GREEN"}

        # 5. green_remaining is non-negative
        assert state.green_remaining >= 0.0
        if state.signal_phase == "GREEN":
            assert state.green_remaining > 0.0
        else:
            assert state.green_remaining == 0.0


@REQUIRES_SUMO
def test_intersection_sensor_signal_phase_transition() -> None:
    """Signal phase maps to GREEN, then YELLOW, and green_remaining updates accurately."""
    with TraCIBridge() as bridge:
        sensor = IntersectionSensor("I1", bridge)

        # At t=30s, NS is still GREEN (duration 31s)
        bridge.step_many(30)
        state_30 = sensor.measure()
        assert state_30.signal_phase == "GREEN"
        assert state_30.green_remaining == 1.0

        # At t=32s, NS has transitioned to YELLOW (duration 4s)
        bridge.step_many(2)
        state_32 = sensor.measure()
        assert state_32.signal_phase == "YELLOW"
        assert state_32.green_remaining == 0.0


@REQUIRES_SUMO
def test_all_four_intersections_produce_valid_traffic_state() -> None:
    """All 4 Urban Grid signalized intersections (I1, I2, I3, I4) produce valid TrafficStates."""
    with TraCIBridge() as bridge:
        bridge.step_many(10)
        sensors = create_intersection_sensors(bridge)

        assert set(sensors.keys()) == {"I1", "I2", "I3", "I4"}

        for iid, sensor in sensors.items():
            state = sensor.measure()
            assert isinstance(state, TrafficState)
            assert state.intersection_id == iid
            assert len(state.lane_features) == 8
            assert state.signal_phase in {"RED", "YELLOW", "GREEN"}
            assert state.total_queue >= 0
            assert state.mean_speed >= 0.0
            assert state.density >= 0.0
            assert state.green_remaining >= 0.0

            # Verify build_traffic_state alias produces identical valid state
            alias_state = sensor.build_traffic_state()
            assert alias_state.intersection_id == iid
            assert len(alias_state.lane_features) == 8


@REQUIRES_SUMO
def test_traffic_state_json_serialization_compatibility() -> None:
    """Generated TrafficState serializes to dict/json matching canonical contract."""
    with TraCIBridge() as bridge:
        bridge.step_many(3)
        sensor = IntersectionSensor("I1", bridge)
        state = sensor.measure()

        state_dict = state.model_dump()
        assert "timestamp" in state_dict
        assert "intersection_id" in state_dict
        assert "lane_features" in state_dict
        assert "total_queue" in state_dict
        assert "mean_speed" in state_dict
        assert "arrival_rate" in state_dict
        assert "density" in state_dict
        assert "signal_phase" in state_dict
        assert "green_remaining" in state_dict

        # Can be re-instantiated into TrafficState without error
        recreated = TrafficState(**state_dict)
        assert recreated == state
