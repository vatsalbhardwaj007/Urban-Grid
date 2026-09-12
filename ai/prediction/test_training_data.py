import copy

import pytest

from ai.prediction.features import FEATURE_NAMES, extract_features
from ai.prediction.training_data import HORIZON_SECONDS, LABEL_NAME, build_training_data


def _is_congested(state):
    return state["total_queue"] > 5


def _state(timestamp=1000, intersection_id="INT-001", **overrides):
    state = {
        "timestamp": timestamp,
        "intersection_id": intersection_id,
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


def test_future_congestion_within_horizon_labels_one():
    out = build_training_data(
        [_state(timestamp=1000), _state(timestamp=1120, total_queue=8)],
        is_congested=_is_congested,
    )
    assert len(out) == 1
    assert out[0]["timestamp"] == 1000
    assert out[0][LABEL_NAME] == 1


def test_no_future_congestion_labels_zero():
    out = build_training_data(
        [_state(timestamp=1000), _state(timestamp=1120)],
        is_congested=_is_congested,
    )
    assert len(out) == 1
    assert out[0][LABEL_NAME] == 0


def test_congestion_exactly_at_horizon_labels_one():
    out = build_training_data(
        [_state(timestamp=1000), _state(timestamp=1000 + HORIZON_SECONDS, total_queue=9)],
        is_congested=_is_congested,
    )
    assert len(out) == 1
    assert out[0][LABEL_NAME] == 1


def test_congestion_after_horizon_ignored():
    out = build_training_data(
        [
            _state(timestamp=1000),
            _state(timestamp=1010),
            _state(timestamp=1301, total_queue=9),
        ],
        is_congested=_is_congested,
    )
    assert out[0]["timestamp"] == 1000
    assert out[0][LABEL_NAME] == 0
    assert out[1]["timestamp"] == 1010
    assert out[1][LABEL_NAME] == 1


def test_insufficient_future_data_excluded():
    assert build_training_data([_state(timestamp=1000)], is_congested=_is_congested) == []
    out = build_training_data(
        [_state(timestamp=0), _state(timestamp=301, total_queue=9)],
        is_congested=_is_congested,
    )
    assert out == []


def test_multiple_intersections_remain_isolated():
    out = build_training_data(
        [
            _state(timestamp=1000, intersection_id="A"),
            _state(timestamp=1100, intersection_id="B", total_queue=9),
            _state(timestamp=1200, intersection_id="A"),
        ],
        is_congested=_is_congested,
    )
    assert len(out) == 1
    assert out[0]["intersection_id"] == "A"
    assert out[0][LABEL_NAME] == 0


def test_unordered_input_equals_sorted_input():
    records = [
        _state(timestamp=1000),
        _state(timestamp=1050),
        _state(timestamp=1120, total_queue=8),
    ]
    sorted_result = build_training_data(records, is_congested=_is_congested)
    shuffled_result = build_training_data(list(reversed(records)), is_congested=_is_congested)
    assert shuffled_result == sorted_result


def test_duplicate_timestamps_raise():
    with pytest.raises(ValueError):
        build_training_data(
            [_state(timestamp=1000), _state(timestamp=1000, total_queue=9)],
            is_congested=_is_congested,
        )


def test_same_timestamp_different_intersections_allowed():
    out = build_training_data(
        [
            _state(timestamp=1000, intersection_id="A"),
            _state(timestamp=1100, intersection_id="A"),
            _state(timestamp=1000, intersection_id="B"),
            _state(timestamp=1100, intersection_id="B", total_queue=9),
        ],
        is_congested=_is_congested,
    )
    assert len(out) == 2
    assert out[0]["intersection_id"] == "A"
    assert out[0][LABEL_NAME] == 0
    assert out[1]["intersection_id"] == "B"
    assert out[1][LABEL_NAME] == 1


def test_current_features_contain_no_future_values():
    current = _state(timestamp=1000, total_queue=4, mean_speed=25.0)
    future = _state(timestamp=1100, total_queue=12, mean_speed=1.0)
    seen = []

    def _spy(state):
        seen.append(state)
        return state["total_queue"] > 5

    out = build_training_data([current, future], is_congested=_spy)
    assert len(out) == 1
    features = out[0]["features"]
    assert features["int_total_queue"] == pytest.approx(4.0)
    assert features["int_mean_speed"] == pytest.approx(25.0)
    assert list(features.keys()) == list(FEATURE_NAMES)
    assert seen == [future]
    assert not any(record is current for record in seen)


@pytest.mark.parametrize("phase", ["RED", "YELLOW", "GREEN"])
def test_signal_phase_preserved_unchanged(phase):
    out = build_training_data(
        [_state(timestamp=1000, signal_phase=phase), _state(timestamp=1100)],
        is_congested=_is_congested,
    )
    assert out[0]["features"]["signal_phase"] == phase
    assert isinstance(out[0]["features"]["signal_phase"], str)


def test_deterministic_repeated_execution():
    records = [
        _state(timestamp=1000, intersection_id="A"),
        _state(timestamp=1050, intersection_id="B"),
        _state(timestamp=1100, intersection_id="A", total_queue=7),
        _state(timestamp=1150, intersection_id="B"),
    ]
    first = build_training_data(records, is_congested=_is_congested)
    second = build_training_data(records, is_congested=_is_congested)
    assert first == second
    snapshot = copy.deepcopy(records)
    build_training_data(records, is_congested=_is_congested)
    assert records == snapshot


def test_reuses_extract_features():
    current = _state(timestamp=1000)
    out = build_training_data([current, _state(timestamp=1100)], is_congested=_is_congested)
    assert out[0]["features"] == extract_features(current)


def test_missing_required_key_raises():
    record = _state(timestamp=1000)
    del record["density"]
    with pytest.raises(ValueError):
        build_training_data([record, _state(timestamp=1100)], is_congested=_is_congested)


def test_non_numeric_timestamp_raises():
    with pytest.raises(ValueError):
        build_training_data([_state(timestamp="later")], is_congested=_is_congested)
    with pytest.raises(ValueError):
        build_training_data([_state(timestamp=float("nan"))], is_congested=_is_congested)


def test_non_string_intersection_id_raises():
    with pytest.raises(ValueError):
        build_training_data(
            [_state(timestamp=1000, intersection_id=123)], is_congested=_is_congested
        )


def test_invalid_signal_phase_raises():
    with pytest.raises(ValueError):
        build_training_data(
            [_state(timestamp=1000, signal_phase="purple")], is_congested=_is_congested
        )


def test_empty_and_single_record_inputs():
    assert build_training_data([], is_congested=_is_congested) == []
    assert build_training_data([_state(timestamp=1000)], is_congested=_is_congested) == []


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        build_training_data("not-a-sequence", is_congested=_is_congested)
    with pytest.raises(TypeError):
        build_training_data([_state(timestamp=1000)], is_congested="not-callable")
    with pytest.raises(ValueError):
        build_training_data(
            [_state(timestamp=1000)], is_congested=_is_congested, horizon_seconds=0
        )
    with pytest.raises(ValueError):
        build_training_data(
            [_state(timestamp=1000)], is_congested=_is_congested, horizon_seconds=float("nan")
        )


def test_sample_structure_and_label_name():
    out = build_training_data(
        [_state(timestamp=1000), _state(timestamp=1100, total_queue=7)],
        is_congested=_is_congested,
    )
    assert len(out) == 1
    sample = out[0]
    assert set(sample.keys()) == {"timestamp", "intersection_id", "features", LABEL_NAME}
    assert len(sample["features"]) == 19
    assert list(sample["features"].keys()) == list(FEATURE_NAMES)
    assert "timestamp" not in sample["features"]
    assert "intersection_id" not in sample["features"]
    assert sample[LABEL_NAME] in (0, 1)
    assert isinstance(sample["timestamp"], (int, float))
    assert isinstance(sample["intersection_id"], str)
    assert sample[LABEL_NAME] == 1
