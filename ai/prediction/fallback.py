"""Deterministic, non-ML congestion fallback for the M1 pipeline.

Used when the XGBoost model is unavailable or fails. A canonical
TrafficState v1 is validated and aggregated by ``features.extract_features``
(the same canonical layer used for training), then a fixed threshold rule
produces a fully deterministic probability. No ML, randomness, or external
state is involved.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from ai.prediction.features import FEATURE_VERSION, extract_features
from ai.prediction.training_data import HORIZON_SECONDS

DEFAULT_QUEUE_THRESHOLD = 10.0
DEFAULT_SPEED_THRESHOLD = 10.0
DEFAULT_FALLBACK_MODEL_VERSION = "deterministic-fallback-v1"

LOW_SEVERITY = "LOW"
HIGH_SEVERITY = "HIGH"


@dataclass
class FallbackPredictionResult:
    probability: float
    severity: str
    horizon_seconds: float
    feature_version: str
    model_version: str


def predict_fallback(
    traffic_state: Mapping[str, object],
    *,
    queue_threshold: float = DEFAULT_QUEUE_THRESHOLD,
    speed_threshold: float = DEFAULT_SPEED_THRESHOLD,
    model_version: str = DEFAULT_FALLBACK_MODEL_VERSION,
) -> FallbackPredictionResult:
    """Predict congestion with a fixed threshold rule.

    The state is congested when ``int_total_queue >= queue_threshold`` or
    ``int_mean_speed <= speed_threshold``, yielding probability 1.0 and
    severity HIGH; otherwise probability 0.0 and severity LOW. The input
    mapping is never mutated.
    """
    _validate_threshold(queue_threshold, "queue_threshold")
    _validate_threshold(speed_threshold, "speed_threshold")

    features = extract_features(traffic_state)

    congested = (
        features["int_total_queue"] >= queue_threshold
        or features["int_mean_speed"] <= speed_threshold
    )
    probability = 1.0 if congested else 0.0

    return FallbackPredictionResult(
        probability=probability,
        severity=HIGH_SEVERITY if congested else LOW_SEVERITY,
        horizon_seconds=HORIZON_SECONDS,
        feature_version=FEATURE_VERSION,
        model_version=model_version,
    )


def _validate_threshold(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite non-negative number")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")