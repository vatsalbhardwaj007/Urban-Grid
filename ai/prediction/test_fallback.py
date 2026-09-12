import copy

import pytest

from ai.prediction.fallback import (
    DEFAULT_FALLBACK_MODEL_VERSION,
    DEFAULT_QUEUE_THRESHOLD,
    DEFAULT_SPEED_THRESHOLD,
    HIGH_SEVERITY,
    LOW_SEVERITY,
    FallbackPredictionResult,
    predict_fallback,
)
from ai.prediction.features import FEATURE_VERSION
from ai.prediction.training_data import HORIZON_SECONDS


def _state(signal_phase="GREEN", **overrides):
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
        "signal_phase": signal_phase,
        "green_remaining": 15,
    }
    state.update(overrides)
    return state


def test_non_congested_state():
    result = predict_fallback(_state())
    assert isinstance(result, FallbackPredictionResult)
    assert result.probability == 0.0
    assert result.severity == LOW_SEVERITY


def test_queue_threshold_triggers_congestion():
    result = predict_fallback(_state(total_queue=DEFAULT_QUEUE_THRESHOLD))
    assert result.probability == 1.0
    assert result.severity == HIGH_SEVERITY


def test_speed_threshold_triggers_congestion():
    result = predict_fallback(_state(mean_speed=DEFAULT_SPEED_THRESHOLD))
    assert result.probability == 1.0
    assert result.severity == HIGH_SEVERITY


def test_both_conditions_trigger_congestion():
    result = predict_fallback(_state(total_queue=12, mean_speed=5.0))
    assert result.probability == 1.0
    assert result.severity == HIGH_SEVERITY


def test_custom_thresholds():
    state = _state(total_queue=4, mean_speed=25.0)
    assert predict_fallback(state, queue_threshold=5.0).probability == 0.0
    assert predict_fallback(state, queue_threshold=4.0).probability == 1.0
    assert predict_fallback(state, speed_threshold=20.0).probability == 0.0
    assert predict_fallback(state, speed_threshold=25.0).probability == 1.0


@pytest.mark.parametrize("name", ["queue_threshold", "speed_threshold"])
def test_invalid_negative_thresholds(name):
    with pytest.raises(ValueError):
        predict_fallback(_state(), **{name: -1.0})


@pytest.mark.parametrize("name", ["queue_threshold", "speed_threshold"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "abc", True])
def test_invalid_nan_inf_thresholds(name, bad):
    with pytest.raises(ValueError):
        predict_fallback(_state(), **{name: bad})


def test_horizon_is_300_seconds():
    result = predict_fallback(_state())
    assert result.horizon_seconds == 300.0
    assert result.horizon_seconds == HORIZON_SECONDS


def test_feature_version_is_v1():
    result = predict_fallback(_state())
    assert result.feature_version == FEATURE_VERSION
    assert result.feature_version == "v1"


def test_model_version():
    assert predict_fallback(_state()).model_version == DEFAULT_FALLBACK_MODEL_VERSION
    assert (
        predict_fallback(_state(), model_version="fallback-experimental").model_version
        == "fallback-experimental"
    )


def test_input_traffic_state_not_mutated():
    state = _state()
    snapshot = copy.deepcopy(state)
    predict_fallback(state)
    assert state == snapshot


def test_invalid_traffic_state_rejected():
    missing_key = _state()
    del missing_key["total_queue"]
    with pytest.raises(ValueError):
        predict_fallback(missing_key)

    invalid_phase = _state(signal_phase="PURPLE")
    with pytest.raises(ValueError):
        predict_fallback(invalid_phase)

    with pytest.raises(ValueError):
        predict_fallback("not-a-state")

    with pytest.raises(ValueError):
        predict_fallback(None)


def test_deterministic_repeated_results():
    state = _state(total_queue=12, mean_speed=5.0)
    first = predict_fallback(state)
    second = predict_fallback(state)
    assert first == second


def test_empty_lane_features_uses_extract_features_behavior():
    state = _state(lane_features=[], total_queue=4, mean_speed=25.0)
    result = predict_fallback(state)
    assert result.probability == 0.0
    assert result.severity == LOW_SEVERITY

    congested = predict_fallback(_state(lane_features=[], total_queue=15, mean_speed=25.0))
    assert congested.probability == 1.0
    assert congested.severity == HIGH_SEVERITY