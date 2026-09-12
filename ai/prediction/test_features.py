import copy
import math

import pytest

from ai.prediction.features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    IMPUTATION_VALUE,
    extract_features,
)

STATE_REQUIRED_KEYS = (
    "timestamp",
    "intersection_id",
    "lane_features",
    "total_queue",
    "mean_speed",
    "arrival_rate",
    "density",
    "signal_phase",
    "green_remaining",
)

LANE_REQUIRED_KEYS = (
    "lane_id",
    "vehicle_count",
    "mean_speed",
    "queue_length",
    "occupancy",
    "arrival_rate",
    "density",
    "flow",
)

STATE_NUMERIC_FIELDS = {
    "total_queue": "int_total_queue",
    "mean_speed": "int_mean_speed",
    "arrival_rate": "int_arrival_rate",
    "density": "int_density",
    "green_remaining": "green_remaining",
}

LANE_NUMERIC_FIELDS = {
    "vehicle_count": ("lane_vehicle_count_sum", "lane_vehicle_count_avg"),
    "mean_speed": ("lane_mean_speed_avg", "lane_mean_speed_min"),
    "queue_length": ("lane_queue_length_sum", "lane_queue_length_max"),
    "occupancy": ("lane_occupancy_avg", "lane_occupancy_max"),
    "arrival_rate": ("lane_arrival_rate_sum",),
    "density": ("lane_density_avg", "lane_density_max"),
    "flow": ("lane_flow_sum",),
}

LANE_AGGREGATE_NAMES = (
    "lane_vehicle_count_sum",
    "lane_vehicle_count_avg",
    "lane_mean_speed_avg",
    "lane_mean_speed_min",
    "lane_queue_length_sum",
    "lane_queue_length_max",
    "lane_occupancy_avg",
    "lane_occupancy_max",
    "lane_arrival_rate_sum",
    "lane_density_avg",
    "lane_density_max",
    "lane_flow_sum",
)


def _state(**overrides):
    state = {
        "timestamp": 1700000000,
        "intersection_id": "INT-001",
        "lane_features": [
            {
                "lane_id": "L1",
                "vehicle_count": 5,
                "mean_speed": 30.0,
                "queue_length": 3,
                "occupancy": 0.4,
                "arrival_rate": 2.0,
                "density": 0.25,
                "flow": 60.0,
            },
            {
                "lane_id": "L2",
                "vehicle_count": 3,
                "mean_speed": 20.0,
                "queue_length": 1,
                "occupancy": 0.2,
                "arrival_rate": 1.0,
                "density": 0.15,
                "flow": 40.0,
            },
        ],
        "total_queue": 4,
        "mean_speed": 25.0,
        "arrival_rate": 3.0,
        "density": 0.2,
        "signal_phase": "GREEN",
        "green_remaining": 15,
    }
    state.update(overrides)
    return state


def _all_finite(out):
    return all(math.isfinite(value) for name, value in out.items() if name != "signal_phase")


@pytest.mark.parametrize("phase", ["RED", "YELLOW", "GREEN"])
def test_canonical_state_returns_exact_features(phase):
    state = _state(signal_phase=phase)
    out = extract_features(state)
    assert len(out) == 19
    assert list(out.keys()) == list(FEATURE_NAMES)
    assert FEATURE_VERSION == "v1"
    assert out["signal_phase"] == phase
    assert isinstance(out["signal_phase"], str)
    for name, value in out.items():
        if name != "signal_phase":
            assert isinstance(value, float)
            assert math.isfinite(value)


def test_feature_order_matches_feature_names():
    out = extract_features(_state())
    assert list(out.keys()) == list(FEATURE_NAMES)
    assert len(FEATURE_NAMES) == 19
    assert len(set(FEATURE_NAMES)) == 19


def test_lane_aggregation_math():
    out = extract_features(_state())
    assert out["lane_count"] == pytest.approx(2.0)
    assert out["lane_vehicle_count_sum"] == pytest.approx(8.0)
    assert out["lane_vehicle_count_avg"] == pytest.approx(4.0)
    assert out["lane_mean_speed_avg"] == pytest.approx(25.0)
    assert out["lane_mean_speed_min"] == pytest.approx(20.0)
    assert out["lane_queue_length_sum"] == pytest.approx(4.0)
    assert out["lane_queue_length_max"] == pytest.approx(3.0)
    assert out["lane_occupancy_avg"] == pytest.approx(0.3)
    assert out["lane_occupancy_max"] == pytest.approx(0.4)
    assert out["lane_arrival_rate_sum"] == pytest.approx(3.0)
    assert out["lane_density_avg"] == pytest.approx(0.2)
    assert out["lane_density_max"] == pytest.approx(0.25)
    assert out["lane_flow_sum"] == pytest.approx(100.0)


@pytest.mark.parametrize("missing_key", STATE_REQUIRED_KEYS)
def test_missing_state_required_key_raises(missing_key):
    state = _state()
    del state[missing_key]
    with pytest.raises(ValueError):
        extract_features(state)


@pytest.mark.parametrize("missing_key", LANE_REQUIRED_KEYS)
def test_missing_lane_required_field_raises(missing_key):
    state = _state()
    del state["lane_features"][0][missing_key]
    with pytest.raises(ValueError):
        extract_features(state)


@pytest.mark.parametrize("field", list(STATE_NUMERIC_FIELDS))
def test_non_numeric_state_field_raises(field):
    state = _state()
    state[field] = "abc"
    with pytest.raises(ValueError):
        extract_features(state)


@pytest.mark.parametrize("field", list(LANE_NUMERIC_FIELDS))
def test_non_numeric_lane_field_raises(field):
    state = _state()
    state["lane_features"][0][field] = "abc"
    with pytest.raises(ValueError):
        extract_features(state)


@pytest.mark.parametrize("field", list(STATE_NUMERIC_FIELDS))
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_state_nan_and_inf_imputed(field, bad):
    state = _state()
    state[field] = bad
    out = extract_features(state)
    assert out[STATE_NUMERIC_FIELDS[field]] == pytest.approx(IMPUTATION_VALUE)
    assert _all_finite(out)


@pytest.mark.parametrize("field", list(LANE_NUMERIC_FIELDS))
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_lane_nan_and_inf_imputed(field, bad):
    state = _state()
    for lane in state["lane_features"]:
        lane[field] = bad
    out = extract_features(state)
    for feature in LANE_NUMERIC_FIELDS[field]:
        assert out[feature] == pytest.approx(IMPUTATION_VALUE)
    assert _all_finite(out)


def test_state_domain_clamps():
    state = _state(
        total_queue=-3,
        mean_speed=-5.0,
        arrival_rate=-1.0,
        density=-2.0,
        green_remaining=-1,
    )
    out = extract_features(state)
    assert out["int_total_queue"] == 0.0
    assert out["int_mean_speed"] == 0.0
    assert out["int_arrival_rate"] == 0.0
    assert out["int_density"] == 0.0
    assert out["green_remaining"] == 0.0


def test_lane_domain_clamps():
    state = _state()
    state["lane_features"][0]["vehicle_count"] = -2
    state["lane_features"][0]["occupancy"] = 1.5
    state["lane_features"][1]["occupancy"] = -0.5
    out = extract_features(state)
    assert out["lane_vehicle_count_sum"] == pytest.approx(3.0)
    assert out["lane_vehicle_count_avg"] == pytest.approx(1.5)
    assert out["lane_occupancy_avg"] == pytest.approx(0.5)
    assert out["lane_occupancy_max"] == pytest.approx(1.0)


def test_empty_lane_features_yields_zero_aggregates():
    state = _state(lane_features=[])
    out = extract_features(state)
    assert out["lane_count"] == 0.0
    for name in LANE_AGGREGATE_NAMES:
        assert out[name] == pytest.approx(IMPUTATION_VALUE)
    assert _all_finite(out)


@pytest.mark.parametrize("phase", ["RED", "YELLOW", "GREEN"])
def test_signal_phase_is_preserved(phase):
    out = extract_features(_state(signal_phase=phase))
    assert out["signal_phase"] == phase
    assert isinstance(out["signal_phase"], str)


@pytest.mark.parametrize("invalid", ["red", "PURPLE", "", "GREEN ", "yellow", 123, None])
def test_invalid_signal_phase_raises(invalid):
    with pytest.raises(ValueError):
        extract_features(_state(signal_phase=invalid))


def test_deterministic_and_pure():
    state = _state()
    snapshot = copy.deepcopy(state)
    first = extract_features(state)
    second = extract_features(state)
    assert first == second
    assert state == snapshot


def test_metadata_fields_excluded():
    assert "timestamp" not in FEATURE_NAMES
    assert "intersection_id" not in FEATURE_NAMES
