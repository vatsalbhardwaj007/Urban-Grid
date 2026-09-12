import numpy as np
import pytest

from ai.prediction.evaluate import (
    DECISION_THRESHOLD,
    ConfusionMatrix,
    EvaluationResult,
    evaluate,
)
from ai.prediction.train import (
    FEATURE_COLUMNS,
    SIGNAL_PHASE_VALUES,
    TrainingResult,
    build_feature_vector,
    train_baseline,
)
from ai.prediction.training_data import LABEL_NAME


class _StubModel:
    def __init__(self, probabilities, classes=(0, 1)):
        self._probabilities = probabilities
        self.classes_ = np.asarray(classes)

    def predict_proba(self, X):
        rows = len(X)
        probabilities = self._probabilities
        if callable(probabilities):
            return np.asarray([[1.0 - p, p] for p in probabilities(rows)])
        if rows != len(probabilities):
            return np.asarray([[1.0 - probabilities[0], probabilities[0]]])
        return np.asarray([[1.0 - p, p] for p in probabilities])


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


def _samples(labels):
    return [_sample(int(label)) for label in labels]


def _stub_result(probabilities):
    model = _StubModel(probabilities)
    n = len(probabilities) if not callable(probabilities) else 0
    return TrainingResult(
        model=model,
        feature_version="v1",
        feature_columns=FEATURE_COLUMNS,
        signal_phase_categories=SIGNAL_PHASE_VALUES,
        random_state=0,
        n_samples=n,
    )


def test_perfect_predictions():
    result = evaluate(_stub_result([1.0, 1.0, 1.0, 1.0]), _samples([1, 1, 1, 1]))
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f1 == 1.0
    assert result.confusion_matrix == ConfusionMatrix(4, 0, 0, 0)
    assert result.positive_count == 4
    assert result.negative_count == 0

    negative = evaluate(_stub_result([0.0, 0.0]), _samples([0, 0]))
    assert negative.precision == 0.0
    assert negative.recall == 0.0
    assert negative.f1 == 0.0
    assert negative.confusion_matrix == ConfusionMatrix(0, 2, 0, 0)


def test_false_positives():
    result = evaluate(_stub_result([1.0, 1.0, 1.0]), _samples([0, 0, 0]))
    assert result.confusion_matrix == ConfusionMatrix(0, 0, 3, 0)
    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.f1 == 0.0
    assert result.positive_count == 0
    assert result.negative_count == 3


def test_false_negatives():
    result = evaluate(_stub_result([0.0, 0.0]), _samples([1, 1]))
    assert result.confusion_matrix == ConfusionMatrix(0, 0, 0, 2)
    assert result.recall == 0.0
    assert result.precision == 0.0
    assert result.f1 == 0.0


def test_mixed_predictions():
    result = evaluate(_stub_result([0.9, 0.9, 0.1, 0.1]), _samples([1, 0, 0, 1]))
    assert result.confusion_matrix == ConfusionMatrix(1, 1, 1, 1)
    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(0.5)
    assert result.f1 == pytest.approx(0.5)
    assert result.sample_count == 4
    assert result.positive_count == 2
    assert result.negative_count == 2


def test_confusion_matrix_correctness():
    result = evaluate(
        _stub_result([0.99, 0.01, 0.9, 0.3, 0.2, 0.7]),
        _samples([1, 0, 1, 1, 0, 0]),
    )
    assert isinstance(result.confusion_matrix, ConfusionMatrix)
    assert result.confusion_matrix.true_positive == 2
    assert result.confusion_matrix.true_negative == 2
    assert result.confusion_matrix.false_positive == 1
    assert result.confusion_matrix.false_negative == 1
    assert (
        result.confusion_matrix.true_positive
        + result.confusion_matrix.true_negative
        + result.confusion_matrix.false_positive
        + result.confusion_matrix.false_negative
        == result.sample_count
    )
    assert result.sample_count == 6


def test_empty_input_rejected():
    with pytest.raises(ValueError):
        evaluate(_stub_result([]), [])


def test_mismatched_lengths_rejected():
    stub = _StubModel([0.9, 0.1])
    result = TrainingResult(
        model=stub,
        feature_version="v1",
        feature_columns=FEATURE_COLUMNS,
        signal_phase_categories=SIGNAL_PHASE_VALUES,
        random_state=0,
        n_samples=4,
    )
    with pytest.raises(ValueError):
        evaluate(result, _samples([1, 0, 1, 0]))


def test_invalid_labels_rejected():
    with pytest.raises(ValueError):
        evaluate(_stub_result([0.5, 0.5]), _samples([2, 0]))
    with pytest.raises(ValueError):
        evaluate(_stub_result([0.5, 0.5]), _samples([-1, 0]))
    with pytest.raises(ValueError):
        evaluate(_stub_result([0.5, 0.5]), [_sample(0), _sample(True)])
    with pytest.raises(ValueError):
        evaluate(_stub_result([0.5, 0.5]), [_sample(0), _sample(None)])


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        evaluate(None, _samples([1, 0]))
    with pytest.raises(ValueError):
        evaluate(_stub_result([0.5, 0.5]), "not-samples")
    with pytest.raises(ValueError):
        evaluate(_stub_result([0.5, 0.5]), [object()])
    sample = _sample(0)
    del sample[LABEL_NAME]
    with pytest.raises(ValueError):
        evaluate(_stub_result([0.5]), [sample])
    sample = _sample(0)
    del sample["features"]["int_density"]
    with pytest.raises(ValueError):
        evaluate(_stub_result([0.5]), [sample])


def test_decision_threshold_is_0_5():
    assert DECISION_THRESHOLD == 0.5
    result = evaluate(_stub_result([0.5]), _samples([1]))
    assert result.confusion_matrix.true_positive == 1


def test_deterministic_repeated_evaluation():
    samples = []
    for i in range(6):
        samples.append(
            _sample(
                label=i % 2,
                signal_phase=SIGNAL_PHASE_VALUES[i % len(SIGNAL_PHASE_VALUES)],
                int_total_queue=10.0 if i % 2 else 2.0,
            )
        )
    result = train_baseline(samples)
    first = evaluate(result, samples)
    second = evaluate(result, samples)
    assert first == second


def test_real_model_evaluation_through_existing_pipeline():
    samples = []
    for i in range(24):
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
    result = train_baseline(samples)
    evaluation = evaluate(result, samples)
    assert isinstance(evaluation, EvaluationResult)
    assert evaluation.sample_count == 24
    assert evaluation.positive_count == 12
    assert evaluation.negative_count == 12
    assert 0.0 <= evaluation.precision <= 1.0
    assert 0.0 <= evaluation.recall <= 1.0
    assert 0.0 <= evaluation.f1 <= 1.0
    assert (
        evaluation.confusion_matrix.true_positive + evaluation.confusion_matrix.false_negative
        == evaluation.positive_count
    )
    assert (
        evaluation.confusion_matrix.true_negative + evaluation.confusion_matrix.false_positive
        == evaluation.negative_count
    )