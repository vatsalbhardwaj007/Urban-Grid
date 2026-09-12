import copy

import numpy as np
import pytest

from ai.prediction.features import FEATURE_NAMES, FEATURE_VERSION, extract_features
from ai.prediction.predict import (
    DEFAULT_MODEL_VERSION,
    HIGH_SEVERITY,
    HIGH_SEVERITY_MIN_PROBABILITY,
    LOW_SEVERITY,
    LOW_SEVERITY_MAX_PROBABILITY,
    MEDIUM_SEVERITY,
    PredictionResult,
    predict,
)
from ai.prediction.train import (
    FEATURE_COLUMNS,
    SIGNAL_PHASE_VALUES,
    build_feature_vector,
    train_baseline,
)
from ai.prediction.training_data import LABEL_NAME, HORIZON_SECONDS

SEVERITIES = {LOW_SEVERITY, MEDIUM_SEVERITY, HIGH_SEVERITY}


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


def _features(signal_phase="GREEN", **overrides):
    features = {
        "int_total_queue": 4.0,
        "int_mean_speed": 25.0,
        "int_arrival_rate": 3.0,
        "int_density": 0.2,
        "signal_phase": signal_phase,
        "green_remaining": 15.0,
        "lane_count": 2.0,
        "lane_vehicle_count_sum": 8.0,
        "lane_vehicle_count_avg": 4.0,
        "lane_mean_speed_avg": 25.0,
        "lane_mean_speed_min": 20.0,
        "lane_queue_length_sum": 4.0,
        "lane_queue_length_max": 3.0,
        "lane_occupancy_avg": 0.3,
        "lane_occupancy_max": 0.4,
        "lane_arrival_rate_sum": 3.0,
        "lane_density_avg": 0.2,
        "lane_density_max": 0.25,
        "lane_flow_sum": 100.0,
    }
    features.update(overrides)
    return features


def _sample(label, signal_phase="GREEN", **overrides):
    return {
        "timestamp": 1000,
        "intersection_id": "INT-001",
        "features": _features(signal_phase=signal_phase, **overrides),
        LABEL_NAME: label,
    }


def _varied_samples(n=24):
    samples = []
    for i in range(n):
        congested = i % 2 == 1
        samples.append(
            _sample(
                label=int(congested),
                signal_phase=SIGNAL_PHASE_VALUES[i % len(SIGNAL_PHASE_VALUES)],
                int_total_queue=10.0 if congested else 2.0,
                lane_mean_speed_min=6.0 if congested else 32.0,
                lane_queue_length_sum=12.0 if congested else 2.0,
            )
        )
    return samples


@pytest.fixture(scope="module")
def training_result():
    return train_baseline(_varied_samples())


def _as_matrix(traffic_state):
    return np.asarray([build_feature_vector(extract_features(traffic_state))], dtype=np.float64)


def test_successful_prediction(training_result):
    result = predict(training_result, _state())
    assert isinstance(result, PredictionResult)
    assert isinstance(result.probability, float)
    assert result.severity in SEVERITIES
    assert result.feature_version == FEATURE_VERSION
    assert result.model_version == DEFAULT_MODEL_VERSION
    assert result.horizon_seconds == HORIZON_SECONDS


def test_probability_between_zero_and_one(training_result):
    for i in range(8):
        state = _state(signal_phase=SIGNAL_PHASE_VALUES[i % 3], int_total_queue=float(i))
        result = predict(training_result, state)
        assert 0.0 <= result.probability <= 1.0


def test_class_one_probability_is_used(training_result):
    state = _state(total_queue=10, mean_speed=8.0)
    result = predict(training_result, state)
    expected = float(training_result.model.predict_proba(_as_matrix(state))[0, 1])
    assert result.probability == pytest.approx(expected)


def test_low_severity(training_result, monkeypatch):
    monkeypatch.setattr(
        training_result.model, "predict_proba", lambda X: np.array([[0.9, 0.1]])
    )
    result = predict(training_result, _state())
    assert result.probability == pytest.approx(0.1)
    assert result.severity == LOW_SEVERITY


def test_medium_severity(training_result, monkeypatch):
    monkeypatch.setattr(
        training_result.model, "predict_proba", lambda X: np.array([[0.5, 0.5]])
    )
    result = predict(training_result, _state())
    assert result.severity == MEDIUM_SEVERITY


def test_high_severity(training_result, monkeypatch):
    monkeypatch.setattr(
        training_result.model, "predict_proba", lambda X: np.array([[0.1, 0.9]])
    )
    result = predict(training_result, _state())
    assert result.severity == HIGH_SEVERITY


def test_severity_band_edge_cases(training_result, monkeypatch):
    monkeypatch.setattr(
        training_result.model,
        "predict_proba",
        lambda X: np.array([[1.0 - LOW_SEVERITY_MAX_PROBABILITY, LOW_SEVERITY_MAX_PROBABILITY]]),
    )
    assert predict(training_result, _state()).severity == MEDIUM_SEVERITY
    monkeypatch.setattr(
        training_result.model,
        "predict_proba",
        lambda X: np.array(
            [[1.0 - HIGH_SEVERITY_MIN_PROBABILITY, HIGH_SEVERITY_MIN_PROBABILITY]]
        ),
    )
    assert predict(training_result, _state()).severity == HIGH_SEVERITY


def test_horizon_is_300_seconds(training_result):
    result = predict(training_result, _state())
    assert result.horizon_seconds == 300.0
    assert result.horizon_seconds == HORIZON_SECONDS


def test_feature_version_is_preserved(training_result):
    result = predict(training_result, _state())
    assert result.feature_version == training_result.feature_version
    assert result.feature_version == FEATURE_VERSION
    assert FEATURE_VERSION == "v1"


def test_custom_model_version_is_preserved(training_result):
    result = predict(training_result, _state(), model_version="experimental-v2")
    assert result.model_version == "experimental-v2"


def test_canonical_state_not_mutated(training_result):
    state = _state()
    snapshot = copy.deepcopy(state)
    predict(training_result, state)
    assert state == snapshot


def test_invalid_traffic_state_rejected(training_result):
    missing_key = _state()
    del missing_key["total_queue"]
    with pytest.raises(ValueError):
        predict(training_result, missing_key)

    invalid_phase = _state(signal_phase="PURPLE")
    with pytest.raises(ValueError):
        predict(training_result, invalid_phase)

    with pytest.raises(ValueError):
        predict(training_result, "not-a-state")

    with pytest.raises(ValueError):
        predict(training_result, None)


@pytest.mark.parametrize("phase", ["RED", "YELLOW", "GREEN"])
def test_prediction_works_for_all_signal_phases(training_result, phase):
    result = predict(training_result, _state(signal_phase=phase))
    assert 0.0 <= result.probability <= 1.0
    vector = build_feature_vector(extract_features(_state(signal_phase=phase)))
    row = dict(zip(FEATURE_COLUMNS, vector))
    for other in SIGNAL_PHASE_VALUES:
        assert row[f"signal_phase_{other}"] == (1.0 if other == phase else 0.0)


def test_feature_ordering_matches_training_pipeline(training_result):
    state = _state()
    features = extract_features(state)
    assert list(features.keys()) == list(FEATURE_NAMES)
    vector = build_feature_vector(features)
    assert len(vector) == len(training_result.feature_columns)
    assert training_result.feature_columns == FEATURE_COLUMNS
    for column_name, value in zip(training_result.feature_columns, vector):
        assert isinstance(column_name, str)
        assert isinstance(value, float)
    model_result = predict(training_result, state)
    assert model_result.probability == pytest.approx(
        float(training_result.model.predict_proba(np.asarray([vector]))[0, 1])
    )