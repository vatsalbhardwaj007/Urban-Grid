"""Evaluation of the trained congestion predictor on held-out samples.

Consumes the same supervised samples produced by ``training_data.build_training_data``
and scored by ``train.train_baseline``, reusing the exact preprocessing
pipeline (``build_feature_vector``). The model is treated as a black box: no
training, no internal data splitting, and no new congestion definition occur
here. Inputs are validated and results are deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from ai.prediction.train import TrainingResult, build_feature_vector
from ai.prediction.training_data import LABEL_NAME

DECISION_THRESHOLD = 0.5


@dataclass
class ConfusionMatrix:
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int


@dataclass
class EvaluationResult:
    precision: float
    recall: float
    f1: float
    confusion_matrix: ConfusionMatrix
    sample_count: int
    positive_count: int
    negative_count: int


def evaluate(
    training_result: TrainingResult,
    samples: Sequence[Mapping],
) -> EvaluationResult:
    """Score a trained predictor against labeled samples.

    Each sample must map ``features`` (the 19 extracted features) to the model
    input and ``congested_within_5min`` (0 or 1) to the ground-truth label.
    Predicted labels come from the model's class-1 probability with the fixed
    ``DECISION_THRESHOLD`` of 0.5. Precision, recall, and F1 are 0.0 whenever
    their denominator is zero (e.g. no predicted positives or no actual
    positives), keeping the result well-defined and deterministic.
    """
    if not isinstance(training_result, TrainingResult):
        raise ValueError("training_result must be a TrainingResult")
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)):
        raise ValueError("samples must be a sequence of labeled sample mappings")
    if not samples:
        raise ValueError("no evaluation samples provided")

    rows: list[list[float]] = []
    labels: list[int] = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping):
            raise ValueError(f"samples[{index}] must be a mapping")
        features = sample.get("features")
        rows.append(build_feature_vector(features))
        if LABEL_NAME not in sample:
            raise ValueError(f"samples[{index}] missing label '{LABEL_NAME}'")
        labels.append(
            _require_binary_label(sample[LABEL_NAME], f"samples[{index}].{LABEL_NAME}")
        )

    classes = training_result.model.classes_
    if classes.size != 2 or sorted(classes.tolist()) != [0, 1]:
        raise ValueError("model must be a binary classifier with classes [0, 1]")

    X = np.asarray(rows, dtype=np.float64)
    proba = training_result.model.predict_proba(X)
    if (
        not isinstance(proba, np.ndarray)
        or proba.ndim != 2
        or proba.shape[0] != len(samples)
        or proba.shape[1] != 2
    ):
        raise ValueError(
            "model predict_proba returned an unexpected shape; expected (n_samples, 2)"
        )

    class_one_index = int(np.where(classes == 1)[0][0])
    predicted = (proba[:, class_one_index] >= DECISION_THRESHOLD).astype(int)
    true = np.asarray(labels, dtype=np.int32)

    tp = int(np.sum((true == 1) & (predicted == 1)))
    tn = int(np.sum((true == 0) & (predicted == 0)))
    fp = int(np.sum((true == 0) & (predicted == 1)))
    fn = int(np.sum((true == 1) & (predicted == 0)))

    precision = tp / (tp + fp) if tp + fp > 0 else 0.0
    recall = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0

    return EvaluationResult(
        precision=precision,
        recall=recall,
        f1=f1,
        confusion_matrix=ConfusionMatrix(
            true_positive=tp,
            true_negative=tn,
            false_positive=fp,
            false_negative=fn,
        ),
        sample_count=len(samples),
        positive_count=int(np.sum(true == 1)),
        negative_count=int(np.sum(true == 0)),
    )


def _require_binary_label(value, context: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be 0 or 1, got {type(value).__name__}")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be 0 or 1, got " + repr(value))
    if value not in (0, 1):
        raise ValueError(f"{context} must be 0 or 1, got " + repr(value))
    return int(value)