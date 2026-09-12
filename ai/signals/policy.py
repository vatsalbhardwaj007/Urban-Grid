"""Signal-pressure scoring for M1 signal policy.

Blueprint concept: an approach/intersection is scored from its queue length,
arrival rate, and downstream pressure/capacity. All components are supplied by
the caller (the M1 side does not invent SUMO data) and scored as:

    score = wq * normalized_queue
          + wa * normalized_arrival_rate
          + wd * downstream_pressure

The normalized queue and arrival-rate components must lie in [0, 1];
downstream pressure is any finite, non-negative value (e.g. a capacity-derived
ratio or a raw pressure). Every value and weight is validated, and the result
is deterministic.

Default weights are neutral (1.0) placeholders only; they are documented as
pending calibration and are NOT asserted as final Urban Grid weights.
"""

from __future__ import annotations

import math

DEFAULT_QUEUE_WEIGHT = 1.0
DEFAULT_ARRIVAL_RATE_WEIGHT = 1.0
DEFAULT_DOWNSTREAM_PRESSURE_WEIGHT = 1.0


def signal_pressure_score(
    *,
    normalized_queue: float,
    normalized_arrival_rate: float,
    downstream_pressure: float,
    queue_weight: float = DEFAULT_QUEUE_WEIGHT,
    arrival_rate_weight: float = DEFAULT_ARRIVAL_RATE_WEIGHT,
    downstream_pressure_weight: float = DEFAULT_DOWNSTREAM_PRESSURE_WEIGHT,
) -> float:
    """Compute the deterministic weighted signal-pressure score.

    ``normalized_queue`` and ``normalized_arrival_rate`` must be in [0, 1];
    ``downstream_pressure`` must be finite and >= 0. All weights must be finite
    and >= 0. A higher score indicates more pressure (more deserving of green).
    """
    _require_finite_non_negative(normalized_queue, "normalized_queue")
    if normalized_queue > 1.0:
        raise ValueError("normalized_queue must be <= 1.0 (normalized in [0, 1])")
    _require_finite_non_negative(normalized_arrival_rate, "normalized_arrival_rate")
    if normalized_arrival_rate > 1.0:
        raise ValueError("normalized_arrival_rate must be <= 1.0 (normalized in [0, 1])")
    _require_finite_non_negative(downstream_pressure, "downstream_pressure")

    weights = {
        "queue_weight": queue_weight,
        "arrival_rate_weight": arrival_rate_weight,
        "downstream_pressure_weight": downstream_pressure_weight,
    }
    for name, weight in weights.items():
        _require_finite_non_negative(weight, name)

    return float(
        queue_weight * normalized_queue
        + arrival_rate_weight * normalized_arrival_rate
        + downstream_pressure_weight * downstream_pressure
    )


def _require_finite_non_negative(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")