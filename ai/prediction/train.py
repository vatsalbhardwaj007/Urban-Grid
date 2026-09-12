"""XGBoost baseline trainer for the M1 congestion prediction pipeline.

Consumes supervised samples produced by ``training_data.build_training_data``
and fits a minimal, deterministic binary classifier (binary:logistic).

The trained model and the exact feature/preprocessing representation are
returned together in ``TrainingResult`` so the later inference stage can
reproduce the same input layout deterministically. ``signal_phase`` is
expanded into three binary indicator columns (RED/YELLOW/GREEN); no
numerical ordering is imposed on the canonical categories.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import xgboost as xgb

from ai.prediction.features import FEATURE_NAMES, FEATURE_VERSION
from ai.prediction.training_data import LABEL_NAME

SIGNAL_PHASE_VALUE = "signal_phase"
SIGNAL_PHASE_VALUES = ("RED", "YELLOW", "GREEN")
SIGNAL_PHASES = frozenset(SIGNAL_PHASE_VALUES)

_N_ESTIMATORS = 100


def _build_feature_columns() -> tuple[str, ...]:
    columns: list[str] = []
    for name in FEATURE_NAMES:
        if name == SIGNAL_PHASE_VALUE:
            columns.extend(
                f"{SIGNAL_PHASE_VALUE}_{phase}" for phase in SIGNAL_PHASE_VALUES
            )
        else:
            columns.append(name)
    return tuple(columns)


FEATURE_COLUMNS = _build_feature_columns()


@dataclass
class TrainingResult:
    """Outcome of a baseline training run.

    ``model`` is the fitted classifier. The remaining fields document the
    exact preprocessing contract so that inference reproduces the identical
    feature representation without re-deriving it. In particular:

    * ``feature_version`` is the source feature schema version (``features.py``).
    * ``feature_columns`` is the exact column order of the NumPy ``X`` matrix
      the model was trained on; inference must build input rows in this order.
    * ``signal_phase_categories`` is the canonical (un-encoded) category order;
      each phase maps to a deterministic one-hot indicator column
      ``signal_phase_<category>`` with exactly one 1.0 and the rest 0.0, and
      no numerical ordering is imposed on the categories.
    """

    model: xgb.XGBClassifier
    feature_version: str
    feature_columns: tuple[str, ...]
    signal_phase_categories: tuple[str, ...]
    random_state: int
    n_samples: int


def build_feature_vector(features: Mapping[str, float | str]) -> list[float]:
    """Encode the 19 extracted features into the training column layout.

    ``signal_phase`` (RED/YELLOW/GREEN) expands into three binary indicator
    columns in canonical order; the other 18 features are passed through as
    floats. The result length and order always match ``FEATURE_COLUMNS``.
    """
    if not isinstance(features, Mapping):
        raise ValueError("features must be a mapping")
    missing = [name for name in FEATURE_NAMES if name not in features]
    if missing:
        raise ValueError("features missing field(s): " + ", ".join(missing))
    vector: list[float] = []
    for name in FEATURE_NAMES:
        value = features[name]
        if name == SIGNAL_PHASE_VALUE:
            if not isinstance(value, str) or value not in SIGNAL_PHASES:
                raise ValueError(
                    "feature 'signal_phase' must be one of RED, YELLOW, GREEN, got "
                    + repr(value)
                )
            vector.extend(
                1.0 if value == phase else 0.0 for phase in SIGNAL_PHASE_VALUES
            )
        else:
            vector.append(_require_real_number(value, f"feature '{name}'"))
    return vector


def train_baseline(samples: Sequence[Mapping], *, random_state: int = 0) -> TrainingResult:
    """Train a minimal, deterministic XGBoost binary classifier on samples.

    Each sample must map ``features`` (the 19 extracted features) to the
    model input ``X`` and ``congested_within_5min`` (0 or 1) to the label
    ``y``. Malformed samples, non-binary labels, an empty set, or a set
    containing only one class are rejected with a clear ``ValueError``
    instead of producing an obscure training error.

    No train/validation split is performed here: evaluation is the
    responsibility of the later ``evaluate.py`` component.
    """
    if not isinstance(random_state, int):
        raise ValueError("random_state must be an integer")
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)):
        raise ValueError("samples must be a sequence of training sample mappings")

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

    if not rows:
        raise ValueError("no training samples provided")

    negatives = labels.count(0)
    positives = labels.count(1)
    if negatives == 0 or positives == 0:
        raise ValueError(
            "training requires both label classes (0 and 1); "
            f"found {negatives} negatives and {positives} positives"
        )

    X = np.asarray(rows, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int32)

    model = xgb.XGBClassifier(
        n_estimators=_N_ESTIMATORS,
        objective="binary:logistic",
        random_state=random_state,
        n_jobs=1,
        verbosity=0,
        tree_method="hist",
    )
    model.fit(X, y)

    return TrainingResult(
        model=model,
        feature_version=FEATURE_VERSION,
        feature_columns=FEATURE_COLUMNS,
        signal_phase_categories=SIGNAL_PHASE_VALUES,
        random_state=random_state,
        n_samples=len(rows),
    )


def _require_real_number(value, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be numeric, got {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{context} must be finite")
    return result


def _require_binary_label(value, context: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be 0 or 1, got {type(value).__name__}")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be 0 or 1, got " + repr(value))
    if value not in (0, 1):
        raise ValueError(f"{context} must be 0 or 1, got " + repr(value))
    return int(value)