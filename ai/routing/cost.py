"""Future edge-cost calculation for M1 routing.

Concept from the Urban Grid Blueprint:

    future edge cost = free-flow travel time
                     + predicted queue delay
                     + predicted signal delay
                     + congestion penalty

Predicted/estimated components are supplied by the caller (the M1 side does
not pretend to have learned edge-level forecasts yet). Every component and
weight must be a finite, non-negative number; the result is therefore always
a finite, non-negative float and free-flow time forms the base cost.
"""

from __future__ import annotations

import math

DEFAULT_FREE_FLOW_WEIGHT = 1.0
DEFAULT_QUEUE_DELAY_WEIGHT = 1.0
DEFAULT_SIGNAL_DELAY_WEIGHT = 1.0
DEFAULT_CONGESTION_PENALTY_WEIGHT = 1.0

_COMPONENTS = (
    ("free_flow_time", "free_flow_weight", DEFAULT_FREE_FLOW_WEIGHT),
    ("queue_delay", "queue_delay_weight", DEFAULT_QUEUE_DELAY_WEIGHT),
    ("signal_delay", "signal_delay_weight", DEFAULT_SIGNAL_DELAY_WEIGHT),
    ("congestion_penalty", "congestion_penalty_weight", DEFAULT_CONGESTION_PENALTY_WEIGHT),
)


def future_edge_cost(
    free_flow_time: float,
    *,
    queue_delay: float = 0.0,
    signal_delay: float = 0.0,
    congestion_penalty: float = 0.0,
    free_flow_weight: float = DEFAULT_FREE_FLOW_WEIGHT,
    queue_delay_weight: float = DEFAULT_QUEUE_DELAY_WEIGHT,
    signal_delay_weight: float = DEFAULT_SIGNAL_DELAY_WEIGHT,
    congestion_penalty_weight: float = DEFAULT_CONGESTION_PENALTY_WEIGHT,
) -> float:
    """Compute future edge cost as the weighted sum of its four components.

    All component values and weights must be finite and non-negative or a
    ``ValueError`` is raised. The returned cost is the weighted free-flow time
    plus each weighted predicted component, preserving free-flow time as the
    base cost and never producing a negative, NaN, or infinite cost.
    """
    values = {
        "free_flow_time": free_flow_time,
        "queue_delay": queue_delay,
        "signal_delay": signal_delay,
        "congestion_penalty": congestion_penalty,
        "free_flow_weight": free_flow_weight,
        "queue_delay_weight": queue_delay_weight,
        "signal_delay_weight": signal_delay_weight,
        "congestion_penalty_weight": congestion_penalty_weight,
    }
    for name, value in values.items():
        _require_non_negative_finite(value, name)

    cost = 0.0
    for value_name, weight_name, _ in _COMPONENTS:
        cost += values[value_name] * values[weight_name]
    if not math.isfinite(cost):
        raise ValueError("resulting edge cost must be finite")

    return float(cost)


def _require_non_negative_finite(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")