"""Canonical TrafficState v1 -> ML-ready feature extraction.

Transforms a canonical TrafficState v1 mapping into a stable, fixed-width
19-feature mapping consumed by the M1 congestion prediction pipeline.
"""

from __future__ import annotations

import math

FEATURE_VERSION = "v1"

FEATURE_NAMES = (
    "int_total_queue",
    "int_mean_speed",
    "int_arrival_rate",
    "int_density",
    "signal_phase",
    "green_remaining",
    "lane_count",
    "lane_vehicle_count_sum",
    "lane_vehicle_count_avg",
    "lane_mean_speed_avg",
    "lane_mean_speed_min",
    "lane_queue_length_sum",
    "lane_queue_length_max",
    "lane_occupancy_avg",
    "lane_occupancy_max",
    "lane_arrival_rate_sum",
    "lane_density_avg",
    "lane_density_max",
    "lane_flow_sum",
)

IMPUTATION_VALUE = 0.0

VALID_SIGNAL_PHASES = frozenset({"RED", "YELLOW", "GREEN"})

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

_REQUIRED_LANE_KEYS = (
    "lane_id",
    "vehicle_count",
    "mean_speed",
    "queue_length",
    "occupancy",
    "arrival_rate",
    "density",
    "flow",
)

_NUMERIC_STATE_FIELDS = (
    "total_queue",
    "mean_speed",
    "arrival_rate",
    "density",
    "green_remaining",
)

_NUMERIC_LANE_FIELDS = (
    "vehicle_count",
    "mean_speed",
    "queue_length",
    "occupancy",
    "arrival_rate",
    "density",
    "flow",
)

_LANE_AGGREGATE_FEATURES = (
    "lane_vehicle_count_sum",
    "lane_vehicle_count_avg",
    "lane_mean_speed_avg",
    "lane_mean_speed_min",
    "lane_queue_length_sum",
    "lane_queue_length_max",
    "lane_occupancy_avg",
    "lane_occupancy_max",
    "lane_arrival_rate_sum",
    "lane_density_avg",
    "lane_density_max",
    "lane_flow_sum",
)

_BOUNDS = {
    "total_queue": (0.0, None),
    "mean_speed": (0.0, None),
    "arrival_rate": (0.0, None),
    "density": (0.0, None),
    "green_remaining": (0.0, None),
    "vehicle_count": (0.0, None),
    "queue_length": (0.0, None),
    "occupancy": (0.0, 1.0),
    "flow": (0.0, None),
}


def extract_features(traffic_state: dict) -> dict[str, float | str]:
    """Validate and transform a canonical TrafficState v1 dict into the
    stable 19-feature mapping.

    The returned dict has keys exactly equal to ``FEATURE_NAMES`` in the
    same order. All values are ``float`` except ``signal_phase``, which is
    preserved verbatim as the canonical RED/YELLOW/GREEN string. The input
    mapping is never mutated.
    """
    _validate_state(traffic_state)
    scalars = {
        "int_total_queue": _sanitize_number(traffic_state["total_queue"], "total_queue"),
        "int_mean_speed": _sanitize_number(traffic_state["mean_speed"], "mean_speed"),
        "int_arrival_rate": _sanitize_number(traffic_state["arrival_rate"], "arrival_rate"),
        "int_density": _sanitize_number(traffic_state["density"], "density"),
        "signal_phase": traffic_state["signal_phase"],
        "green_remaining": _sanitize_number(traffic_state["green_remaining"], "green_remaining"),
    }
    aggregations = _aggregate_lanes(traffic_state["lane_features"])
    values = {**scalars, **aggregations}
    return {name: values[name] for name in FEATURE_NAMES}


def _validate_state(traffic_state) -> None:
    if not isinstance(traffic_state, dict):
        raise ValueError("traffic_state must be a mapping")
    missing = [key for key in _REQUIRED_STATE_KEYS if key not in traffic_state]
    if missing:
        raise ValueError("missing required canonical field(s): " + ", ".join(missing))
    lane_features = traffic_state["lane_features"]
    if not isinstance(lane_features, list):
        raise ValueError("lane_features must be a list")
    for index, lane in enumerate(lane_features):
        _validate_lane(lane, index)
    for field in _NUMERIC_STATE_FIELDS:
        _require_numeric(traffic_state[field], field)
    _require_signal_phase(traffic_state["signal_phase"])


def _validate_lane(lane, index) -> None:
    if not isinstance(lane, dict):
        raise ValueError(f"lane_features[{index}] must be a mapping")
    missing = [key for key in _REQUIRED_LANE_KEYS if key not in lane]
    if missing:
        raise ValueError(
            "lane_features[" + str(index) + "] missing required field(s): " + ", ".join(missing)
        )
    for field in _NUMERIC_LANE_FIELDS:
        _require_numeric(lane[field], "lane_features[" + str(index) + "]." + field)


def _require_numeric(value, field) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"field '{field}' must be numeric, got {type(value).__name__}")


def _require_signal_phase(value) -> None:
    if not isinstance(value, str) or value not in VALID_SIGNAL_PHASES:
        raise ValueError(f"field 'signal_phase' must be one of RED, YELLOW, GREEN, got {value!r}")


def _sanitize_number(value, field) -> float:
    lower, upper = _BOUNDS.get(field, (0.0, None))
    result = float(value)
    if not math.isfinite(result):
        return IMPUTATION_VALUE
    if result < lower:
        result = lower
    if upper is not None and result > upper:
        result = upper
    return result


def _aggregate_lanes(lane_features) -> dict[str, float]:
    lane_count = float(len(lane_features))
    features = {"lane_count": lane_count}
    if lane_count == 0.0:
        for name in _LANE_AGGREGATE_FEATURES:
            features[name] = IMPUTATION_VALUE
        return features

    values_by_field = {
        field: [_sanitize_number(lane[field], field) for lane in lane_features]
        for field in _NUMERIC_LANE_FIELDS
    }

    features["lane_vehicle_count_sum"] = sum(values_by_field["vehicle_count"])
    features["lane_vehicle_count_avg"] = _mean(values_by_field["vehicle_count"])
    features["lane_mean_speed_avg"] = _mean(values_by_field["mean_speed"])
    features["lane_mean_speed_min"] = min(values_by_field["mean_speed"])
    features["lane_queue_length_sum"] = sum(values_by_field["queue_length"])
    features["lane_queue_length_max"] = max(values_by_field["queue_length"])
    features["lane_occupancy_avg"] = _mean(values_by_field["occupancy"])
    features["lane_occupancy_max"] = max(values_by_field["occupancy"])
    features["lane_arrival_rate_sum"] = sum(values_by_field["arrival_rate"])
    features["lane_density_avg"] = _mean(values_by_field["density"])
    features["lane_density_max"] = max(values_by_field["density"])
    features["lane_flow_sum"] = sum(values_by_field["flow"])
    return features


def _mean(values: list) -> float:
    return sum(values) / len(values)
