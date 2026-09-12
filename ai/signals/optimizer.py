"""Signal-green recommendation from a policy score for M1.

Blueprint concept:

    green = clamp(base_green + k * score, min_green, max_green)

The recommendation is a deterministic policy decision, NOT a safety-certified
traffic-signal controller, and it never interacts with SUMO/TraCI. Minimum and
maximum green always bound the output; an optional ``current_green`` acts as a
floor so an already-running green is never cut back below its current
allocation (still subject to the bounds). No amber/all-red phase sequencing is
modelled here.
"""

from __future__ import annotations

import math

DEFAULT_GAIN = 1.0
DEFAULT_MIN_GREEN = 5.0
DEFAULT_MAX_GREEN = 60.0


def recommended_green(
    score: float,
    *,
    base_green: float,
    gain: float = DEFAULT_GAIN,
    min_green: float = DEFAULT_MIN_GREEN,
    max_green: float = DEFAULT_MAX_GREEN,
    current_green: float | None = None,
) -> float:
    """Return the recommended green duration in seconds, bounded to [min, max].

    ``score`` must be finite and >= 0 (see ``policy.signal_pressure_score``).
    ``base_green``, ``gain``, ``min_green``, ``max_green`` must be finite and
    >= 0 with ``min_green <= max_green``. ``current_green``, when provided,
    must be finite and >= 0 and prevents the recommendation from dropping
    below the currently allocated green. The output is always a finite float
    in [min_green, max_green].
    """
    _require_finite_non_negative(score, "score")
    _require_finite_non_negative(base_green, "base_green")
    _require_finite_non_negative(gain, "gain")
    _require_finite_non_negative(min_green, "min_green")
    _require_finite_non_negative(max_green, "max_green")
    if min_green > max_green:
        raise ValueError("min_green must be <= max_green")
    if current_green is not None:
        _require_finite_non_negative(current_green, "current_green")

    candidate = base_green + gain * score
    if current_green is not None and candidate < current_green:
        candidate = current_green

    green = min(max(candidate, min_green), max_green)
    if not math.isfinite(green):
        raise ValueError("recommended green must be finite")

    return float(green)


def _require_finite_non_negative(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")