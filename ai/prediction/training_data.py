"""Chronological TrafficState v1 -> supervised training samples.

Each sample's features (X) come only from the current TrafficState. The
label y reflects congestion observed strictly in future TrafficState
records of the same intersection within a fixed horizon. No future
information ever leaks into the feature vector.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

from ai.prediction.features import VALID_SIGNAL_PHASES, extract_features

LABEL_NAME = "congested_within_5min"
HORIZON_SECONDS = 300.0

_REQUIRED_STATE_KEYS = (
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

_NUMERIC_STATE_FIELDS = (
    "total_queue",
    "mean_speed",
    "arrival_rate",
    "density",
    "green_remaining",
)


def build_training_data(
    records: Sequence[dict],
    *,
    is_congested: Callable[[dict], bool],
    horizon_seconds: float = HORIZON_SECONDS,
) -> list[dict]:
    """Convert chronological TrafficState v1 records into supervised samples.

    Features are produced by ``features.extract_features`` from the current
    record only. The label is 1 when at least one strictly future record of
    the same intersection within ``(current_ts, current_ts + horizon_seconds]``
    satisfies ``is_congested``, otherwise 0. Records with no future record in
    the window are excluded (no label is invented).

    Returns a list (sorted by intersection_id then timestamp) of dicts with
    keys: ``timestamp``, ``intersection_id``, ``features`` (the 19 feature
    values), and ``congested_within_5min`` (0 or 1). The input is never
    mutated.
    """
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ValueError("records must be a sequence of TrafficState mappings")
    if not callable(is_congested):
        raise TypeError("is_congested must be callable")
    if (
        isinstance(horizon_seconds, bool)
        or not isinstance(horizon_seconds, (int, float))
        or not math.isfinite(float(horizon_seconds))
        or horizon_seconds <= 0
    ):
        raise ValueError("horizon_seconds must be a positive finite number")

    for index, record in enumerate(records):
        _require_valid_record(record, index)

    by_intersection: dict[str, list[dict]] = {}
    for record in records:
        by_intersection.setdefault(record["intersection_id"], []).append(record)

    samples: list[dict] = []
    for intersection_id, group in by_intersection.items():
        group.sort(key=lambda record: record["timestamp"])
        timestamps = [record["timestamp"] for record in group]
        if len(set(timestamps)) != len(timestamps):
            raise ValueError(f"duplicate timestamp(s) for intersection '{intersection_id}'")
        for index, current in enumerate(group):
            horizon_max = current["timestamp"] + horizon_seconds
            future: list[dict] = []
            for candidate in group[index + 1 :]:
                if candidate["timestamp"] > horizon_max:
                    break
                future.append(candidate)
            if not future:
                continue
            features = extract_features(current)
            label = 1 if any(is_congested(record) for record in future) else 0
            samples.append(
                {
                    "timestamp": current["timestamp"],
                    "intersection_id": intersection_id,
                    "features": features,
                    LABEL_NAME: label,
                }
            )

    samples.sort(key=lambda sample: (sample["intersection_id"], sample["timestamp"]))
    return samples


def _require_valid_record(record, index) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"records[{index}] must be a mapping")
    missing = [key for key in _REQUIRED_STATE_KEYS if key not in record]
    if missing:
        raise ValueError(
            "records[" + str(index) + "] missing required field(s): " + ", ".join(missing)
        )
    if not isinstance(record["intersection_id"], str):
        raise ValueError(f"records[{index}] field 'intersection_id' must be a string")
    timestamp = record["timestamp"]
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise ValueError(f"records[{index}] field 'timestamp' must be a number")
    if not math.isfinite(float(timestamp)):
        raise ValueError(f"records[{index}] field 'timestamp' must be finite")
    phase = record["signal_phase"]
    if not isinstance(phase, str) or phase not in VALID_SIGNAL_PHASES:
        raise ValueError(
            f"records[{index}] field 'signal_phase' must be one of RED, YELLOW, GREEN"
        )
    for field in _NUMERIC_STATE_FIELDS:
        _require_numeric(record[field], f"records[{index}].{field}")


def _require_numeric(value, field) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"field '{field}' must be numeric, got {type(value).__name__}")
