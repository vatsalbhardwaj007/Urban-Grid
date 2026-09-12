import copy

import numpy as np
import pytest
import xgboost as xgb

from ai.prediction.features import FEATURE_NAMES
from ai.prediction.training_data import LABEL_NAME
from ai.prediction.train import (
    FEATURE_COLUMNS,
    SIGNAL_PHASE_VALUES,
    TrainingResult,
    build_feature_vector,
    train_baseline,
)


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


def _expected_columns():
    columns = []
    for name in FEATURE_NAMES:
        if name == "signal_phase":
            columns.extend(f"signal_phase_{phase}" for phase in SIGNAL_PHASE_VALUES)
        else:
            columns.append(name)
    return tuple(columns)


def test_valid_binary_dataset_trains():
    samples = _varied_samples()
    result = train_baseline(samples)
    assert isinstance(result, TrainingResult)
    assert result.n_samples == len(samples)
    assert result.feature_version == "v1"


def test_model_is_binary_xgb_classifier():
    samples = _varied_samples()
    result = train_baseline(samples)
    assert isinstance(result.model, xgb.XGBClassifier)
    assert list(result.model.classes_) == [0, 1]
    X = np.asarray(
        [build_feature_vector(sample["features"]) for sample in samples], dtype=np.float64
    )
    proba = result.model.predict_proba(X)
    assert proba.shape == (len(samples), 2)


def test_feature_columns_respect_feature_names_order():
    result = train_baseline(_varied_samples())
    assert result.feature_columns == _expected_columns()
    assert len(result.feature_columns) == len(FEATURE_NAMES) + len(SIGNAL_PHASE_VALUES) - 1


@pytest.mark.parametrize("phase", ["RED", "YELLOW", "GREEN"])
def test_signal_phase_encoded_without_ordering(phase):
    vector = build_feature_vector(_features(signal_phase=phase))
    assert len(vector) == len(FEATURE_COLUMNS)
    row = dict(zip(FEATURE_COLUMNS, vector))
    for other in SIGNAL_PHASE_VALUES:
        expected = 1.0 if other == phase else 0.0
        assert row[f"signal_phase_{other}"] == expected


def test_invalid_signal_phase_in_training_data_fails():
    sample = _sample(1, signal_phase="PURPLE")
    with pytest.raises(ValueError, match="signal_phase"):
        train_baseline([_sample(0), sample])


def test_malformed_sample_fails_clearly():
    with pytest.raises(ValueError):
        train_baseline([object()])
    with pytest.raises(ValueError):
        train_baseline([{"features": "not-a-mapping", LABEL_NAME: 0}])
    with pytest.raises(ValueError):
        train_baseline([{"features": None, LABEL_NAME: 0}])


def test_missing_feature_field_fails_clearly():
    sample = _sample(0)
    del sample["features"]["int_density"]
    with pytest.raises(ValueError, match="int_density"):
        train_baseline([sample])


def test_missing_label_fails_clearly():
    sample = _sample(0)
    del sample[LABEL_NAME]
    with pytest.raises(ValueError):
        train_baseline([sample])


@pytest.mark.parametrize("label", [2, -1, "yes", None, True])
def test_non_binary_label_fails_clearly(label):
    with pytest.raises(ValueError):
        train_baseline([_sample(0), _sample(label)])


def test_empty_training_data_fails_clearly():
    with pytest.raises(ValueError):
        train_baseline([])


@pytest.mark.parametrize("label", [0, 1])
def test_single_class_rejected_clearly(label):
    with pytest.raises(ValueError):
        train_baseline([_sample(label) for _ in range(5)])


def test_training_deterministic_under_random_state():
    samples = _varied_samples()
    first = train_baseline(samples, random_state=0)
    second = train_baseline(samples, random_state=0)
    assert (
        first.model.get_booster().save_raw() == second.model.get_booster().save_raw()
    )
    X = np.asarray(
        [build_feature_vector(sample["features"]) for sample in samples], dtype=np.float64
    )
    np.testing.assert_array_equal(
        first.model.predict_proba(X), second.model.predict_proba(X)
    )


def test_original_samples_not_mutated():
    samples = _varied_samples()
    snapshot = copy.deepcopy(samples)
    train_baseline(samples)
    assert samples == snapshot