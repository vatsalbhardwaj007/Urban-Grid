"""Validation tests for canonical TrafficState v1 contract."""

import pytest
from pydantic import ValidationError

from shared.schemas.traffic_state import LaneFeature, TrafficState


def _make_valid_lane_feature(**overrides) -> dict:
    """Helper creating valid LaneFeature kwargs."""
    data = {
        "lane_id": "lane_north_0",
        "vehicle_count": 8,
        "mean_speed": 11.2,
        "queue_length": 3,
        "occupancy": 0.22,
        "arrival_rate": 0.45,
        "density": 18.5,
        "flow": 32.0,
    }
    data.update(overrides)
    return data


def _make_valid_traffic_state(**overrides) -> dict:
    """Helper creating valid TrafficState kwargs."""
    data = {
        "timestamp": 1710001200.0,
        "intersection_id": "int_market_5th",
        "lane_features": [LaneFeature(**_make_valid_lane_feature())],
        "total_queue": 3,
        "mean_speed": 11.2,
        "arrival_rate": 0.45,
        "density": 18.5,
        "signal_phase": "GREEN",
        "green_remaining": 22.5,
    }
    data.update(overrides)
    return data


class TestTrafficStateContract:
    """Test suite for canonical TrafficState and LaneFeature models."""

    def test_valid_complete_traffic_state(self):
        """1. A valid complete TrafficState can be created."""
        lane_data = _make_valid_lane_feature()
        lane = LaneFeature(**lane_data)
        state_data = _make_valid_traffic_state(lane_features=[lane])
        state = TrafficState(**state_data)

        assert state.timestamp == 1710001200.0
        assert state.intersection_id == "int_market_5th"
        assert len(state.lane_features) == 1
        assert state.total_queue == 3
        assert state.mean_speed == 11.2
        assert state.arrival_rate == 0.45
        assert state.density == 18.5
        assert state.signal_phase == "GREEN"
        assert state.green_remaining == 22.5

    def test_traffic_state_multiple_lane_features(self):
        """2. A valid TrafficState can contain multiple LaneFeature objects."""
        lanes = [
            LaneFeature(**_make_valid_lane_feature(lane_id="lane_north_0", vehicle_count=5, queue_length=2)),
            LaneFeature(**_make_valid_lane_feature(lane_id="lane_north_1", vehicle_count=8, queue_length=4)),
            LaneFeature(**_make_valid_lane_feature(lane_id="lane_south_0", vehicle_count=3, queue_length=1)),
            LaneFeature(**_make_valid_lane_feature(lane_id="lane_east_0", vehicle_count=0, queue_length=0)),
        ]
        state = TrafficState(**_make_valid_traffic_state(
            lane_features=lanes,
            total_queue=7,
        ))

        assert len(state.lane_features) == 4
        assert [lf.lane_id for lf in state.lane_features] == [
            "lane_north_0",
            "lane_north_1",
            "lane_south_0",
            "lane_east_0",
        ]
        assert state.total_queue == 7

    @pytest.mark.parametrize(
        "missing_field",
        [
            "timestamp",
            "intersection_id",
            "lane_features",
            "total_queue",
            "mean_speed",
            "arrival_rate",
            "density",
            "signal_phase",
            "green_remaining",
        ],
    )
    def test_traffic_state_missing_required_fields_rejected(self, missing_field: str):
        """3a. Missing required fields in TrafficState are rejected."""
        data = _make_valid_traffic_state()
        del data[missing_field]
        with pytest.raises(ValidationError) as exc_info:
            TrafficState(**data)
        assert missing_field in str(exc_info.value)

    @pytest.mark.parametrize(
        "missing_field",
        [
            "lane_id",
            "vehicle_count",
            "mean_speed",
            "queue_length",
            "occupancy",
            "arrival_rate",
            "density",
            "flow",
        ],
    )
    def test_lane_feature_missing_required_fields_rejected(self, missing_field: str):
        """3b. Missing required fields in LaneFeature are rejected."""
        data = _make_valid_lane_feature()
        del data[missing_field]
        with pytest.raises(ValidationError) as exc_info:
            LaneFeature(**data)
        assert missing_field in str(exc_info.value)

    @pytest.mark.parametrize(
        "field_name,invalid_value",
        [
            ("timestamp", "not_a_float"),
            ("total_queue", "not_an_int"),
            ("total_queue", 3.7),  # Non-integer float for integer field
            ("mean_speed", "fast"),
            ("arrival_rate", [0.5]),
            ("density", {"val": 10}),
            ("lane_features", "not_a_list"),
            ("green_remaining", "infinite"),
        ],
    )
    def test_incorrect_field_types_rejected(self, field_name: str, invalid_value):
        """4. Incorrect field types are rejected where Pydantic validation requires it."""
        data = _make_valid_traffic_state(**{field_name: invalid_value})
        with pytest.raises(ValidationError):
            TrafficState(**data)

    @pytest.mark.parametrize(
        "field_name,negative_value",
        [
            ("timestamp", -0.1),
            ("total_queue", -1),
            ("mean_speed", -5.0),
            ("arrival_rate", -0.01),
            ("density", -1.0),
            ("green_remaining", -0.5),
        ],
    )
    def test_traffic_state_negative_values_rejected(self, field_name: str, negative_value):
        """5a. Negative values for non-negative TrafficState metrics are rejected."""
        data = _make_valid_traffic_state(**{field_name: negative_value})
        with pytest.raises(ValidationError) as exc_info:
            TrafficState(**data)
        assert "greater_than_equal" in str(exc_info.value) or "greater than or equal to 0" in str(exc_info.value)

    @pytest.mark.parametrize(
        "field_name,negative_value",
        [
            ("vehicle_count", -1),
            ("mean_speed", -2.5),
            ("queue_length", -3),
            ("occupancy", -0.1),
            ("arrival_rate", -0.2),
            ("density", -0.05),
            ("flow", -10.0),
        ],
    )
    def test_lane_feature_negative_values_rejected(self, field_name: str, negative_value):
        """5b. Negative values for non-negative LaneFeature metrics are rejected."""
        data = _make_valid_lane_feature(**{field_name: negative_value})
        with pytest.raises(ValidationError) as exc_info:
            LaneFeature(**data)
        assert "greater_than_equal" in str(exc_info.value) or "greater than or equal to 0" in str(exc_info.value)

    def test_zero_boundary_values_accepted(self):
        """5c. Zero values are valid boundaries for non-negative metrics."""
        zero_lane = LaneFeature(
            lane_id="lane_empty",
            vehicle_count=0,
            mean_speed=0.0,
            queue_length=0,
            occupancy=0.0,
            arrival_rate=0.0,
            density=0.0,
            flow=0.0,
        )
        zero_state = TrafficState(
            timestamp=0.0,
            intersection_id="int_zero",
            lane_features=[zero_lane],
            total_queue=0,
            mean_speed=0.0,
            arrival_rate=0.0,
            density=0.0,
            signal_phase="RED",
            green_remaining=0.0,
        )
        assert zero_state.total_queue == 0
        assert zero_state.green_remaining == 0.0
        assert zero_state.lane_features[0].vehicle_count == 0

    def test_green_remaining_float_seconds(self):
        """6. green_remaining is accepted as a float and represents seconds."""
        # Exact float seconds with fractional precision
        state = TrafficState(**_make_valid_traffic_state(green_remaining=14.75))
        assert isinstance(state.green_remaining, float)
        assert state.green_remaining == 14.75

        # Boundary at 0.0 seconds
        state_zero = TrafficState(**_make_valid_traffic_state(green_remaining=0.0))
        assert state_zero.green_remaining == 0.0

        # Negative seconds rejected
        with pytest.raises(ValidationError):
            TrafficState(**_make_valid_traffic_state(green_remaining=-1.0))

    def test_nested_lane_feature_validation(self):
        """7. Nested LaneFeature validation works correctly."""
        # Nested dict with negative metric inside list
        invalid_nested_data = _make_valid_traffic_state(
            lane_features=[
                _make_valid_lane_feature(lane_id="lane_valid"),
                _make_valid_lane_feature(lane_id="lane_invalid", vehicle_count=-5),
            ]
        )
        with pytest.raises(ValidationError) as exc_info:
            TrafficState(**invalid_nested_data)
        assert "lane_features" in str(exc_info.value)
        assert "greater_than_equal" in str(exc_info.value) or "greater than or equal to 0" in str(exc_info.value)

        # Missing required nested field
        missing_nested = _make_valid_traffic_state(
            lane_features=[{"lane_id": "incomplete_lane"}]
        )
        with pytest.raises(ValidationError) as exc_info:
            TrafficState(**missing_nested)
        assert "lane_features" in str(exc_info.value)

    def test_serialized_field_names_canonical(self):
        """8. The serialized/output field names remain exactly the canonical names."""
        lane = LaneFeature(**_make_valid_lane_feature())
        state = TrafficState(**_make_valid_traffic_state(lane_features=[lane]))

        expected_state_keys = [
            "timestamp",
            "intersection_id",
            "lane_features",
            "total_queue",
            "mean_speed",
            "arrival_rate",
            "density",
            "signal_phase",
            "green_remaining",
        ]
        expected_lane_keys = [
            "lane_id",
            "vehicle_count",
            "mean_speed",
            "queue_length",
            "occupancy",
            "arrival_rate",
            "density",
            "flow",
        ]

        # Check Python dict serialization
        state_dump = state.model_dump()
        assert list(state_dump.keys()) == expected_state_keys

        lane_dump = state_dump["lane_features"][0]
        assert list(lane_dump.keys()) == expected_lane_keys

        # Check JSON serialization keys
        import json
        json_data = json.loads(state.model_dump_json())
        assert list(json_data.keys()) == expected_state_keys
        assert list(json_data["lane_features"][0].keys()) == expected_lane_keys

    # --- Signal Phase Constraints Tests ---

    @pytest.mark.parametrize("valid_phase", ["RED", "YELLOW", "GREEN"])
    def test_signal_phase_canonical_values_accepted(self, valid_phase: str):
        """Confirmed: RED, YELLOW, GREEN are accepted."""
        state = TrafficState(**_make_valid_traffic_state(signal_phase=valid_phase))
        assert state.signal_phase == valid_phase

    @pytest.mark.parametrize("lowercase_phase", ["red", "yellow", "green"])
    def test_signal_phase_lowercase_rejected(self, lowercase_phase: str):
        """Confirmed: Lowercase values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TrafficState(**_make_valid_traffic_state(signal_phase=lowercase_phase))
        assert "signal_phase" in str(exc_info.value)

    @pytest.mark.parametrize("numeric_phase", ["0", "1", "2", 0, 1, 2])
    def test_signal_phase_numeric_rejected(self, numeric_phase):
        """Confirmed: Numeric values and numeric string IDs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TrafficState(**_make_valid_traffic_state(signal_phase=numeric_phase))
        assert "signal_phase" in str(exc_info.value)

    @pytest.mark.parametrize(
        "arbitrary_phase",
        [
            "R",
            "Y",
            "G",
            "P0",
            "P1",
            "P2",
            "ALL_RED",
            "N_S_GREEN",
            "BLUE",
            "FLASHING_YELLOW",
            "",
        ],
    )
    def test_signal_phase_arbitrary_strings_rejected(self, arbitrary_phase: str):
        """Confirmed: Abbreviations, phase IDs, and arbitrary strings are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TrafficState(**_make_valid_traffic_state(signal_phase=arbitrary_phase))
        assert "signal_phase" in str(exc_info.value)
