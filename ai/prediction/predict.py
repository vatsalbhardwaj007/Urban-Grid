"""Online inference for the M1 congestion prediction pipeline.

Turns a canonical TrafficState v1 into a congestion probability using a
trained ``TrainingResult``. The exact feature preprocessing used during
training is reused verbatim: ``features.extract_features`` produces the
19 canonical features, and ``train.build_feature_vector`` applies the
same one-hot ``signal_phase`` encoding and column order as ``train.py``.
No part of the preprocessing layout is re-derived here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from ai.prediction.features import extract_features
from ai.prediction.train import TrainingResult, build_feature_vector
from ai.prediction.training_data import HORIZON_SECONDS

DEFAULT_MODEL_VERSION = "xgboost-baseline-v1"

LOW_SEVERITY = "LOW"
MEDIUM_SEVERITY = "MEDIUM"
HIGH_SEVERITY = "HIGH"

LOW_SEVERITY_MAX_PROBABILITY = 0.33
HIGH_SEVERITY_MIN_PROBABILITY = 0.66


@dataclass
class PredictionResult:
    probability: float
    severity: str
    horizon_seconds: float
    feature_version: str
    model_version: str


def predict(
    training_result: TrainingResult,
    traffic_state: Mapping[str, object],
    *,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> PredictionResult:
    """Predict the probability of congestion within the label horizon.

    ``traffic_state`` must be a canonical TrafficState v1 mapping; it is
    validated by ``extract_features`` and is never mutated. The returned
    ``probability`` is the model's probability of class 1 (congested).
    """
    features = extract_features(traffic_state)
    vector = build_feature_vector(features)
    X = np.asarray([vector], dtype=np.float64)
    proba = training_result.model.predict_proba(X)[0]

    class_one_index = int(np.where(training_result.model.classes_ == 1)[0][0])
    probability = float(proba[class_one_index])

    return PredictionResult(
        probability=probability,
        severity=_severity(probability),
        horizon_seconds=HORIZON_SECONDS,
        feature_version=training_result.feature_version,
        model_version=model_version,
    )


def _severity(probability: float) -> str:
    if probability < LOW_SEVERITY_MAX_PROBABILITY:
        return LOW_SEVERITY
    if probability < HIGH_SEVERITY_MIN_PROBABILITY:
        return MEDIUM_SEVERITY
    return HIGH_SEVERITY