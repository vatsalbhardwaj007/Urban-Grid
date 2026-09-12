"""Baseline vs. Urban Grid A/B comparison engine.

This module provides reusable comparison logic to evaluate performance differences
between a baseline simulation run (e.g., fixed-time signals) and an Urban Grid run
(e.g., AI-optimized signals) on the same scenario demand.

Metric directionality is strictly respected:
- Lower is better: delay, queue length, travel time
- Higher is better: speed, throughput, vehicle count
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


class MetricDirection(str, Enum):
    """Directionality of improvement for traffic metrics."""

    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"
    NEUTRAL = "neutral"


# Canonical registry mapping standard metric names to their improvement direction.
METRIC_DIRECTION_REGISTRY: dict[str, MetricDirection] = {
    # Lower is better (congestion, delays, queues)
    "average_delay": MetricDirection.LOWER_IS_BETTER,
    "delay": MetricDirection.LOWER_IS_BETTER,
    "average_queue_length": MetricDirection.LOWER_IS_BETTER,
    "maximum_queue_length": MetricDirection.LOWER_IS_BETTER,
    "queue_length": MetricDirection.LOWER_IS_BETTER,
    "total_queue": MetricDirection.LOWER_IS_BETTER,
    "mean_queue": MetricDirection.LOWER_IS_BETTER,
    "peak_queue": MetricDirection.LOWER_IS_BETTER,
    "density": MetricDirection.LOWER_IS_BETTER,
    "average_density": MetricDirection.LOWER_IS_BETTER,
    "occupancy": MetricDirection.LOWER_IS_BETTER,
    "average_occupancy": MetricDirection.LOWER_IS_BETTER,
    "travel_time": MetricDirection.LOWER_IS_BETTER,
    "average_travel_time": MetricDirection.LOWER_IS_BETTER,
    "waiting_time": MetricDirection.LOWER_IS_BETTER,
    # Higher is better (mobility, throughput, speeds)
    "average_speed": MetricDirection.HIGHER_IS_BETTER,
    "mean_speed": MetricDirection.HIGHER_IS_BETTER,
    "average_mean_speed": MetricDirection.HIGHER_IS_BETTER,
    "speed": MetricDirection.HIGHER_IS_BETTER,
    "throughput": MetricDirection.HIGHER_IS_BETTER,
    "flow": MetricDirection.HIGHER_IS_BETTER,
    "total_flow": MetricDirection.HIGHER_IS_BETTER,
    "average_flow": MetricDirection.HIGHER_IS_BETTER,
    "completed_vehicles": MetricDirection.HIGHER_IS_BETTER,
    # Neutral / Informational context metrics (not optimization KPIs)
    "arrival_rate": MetricDirection.NEUTRAL,
    "average_arrival_rate": MetricDirection.NEUTRAL,
    "vehicle_count": MetricDirection.NEUTRAL,
    "average_vehicle_count": MetricDirection.NEUTRAL,
}


@dataclass(frozen=True)
class MetricComparison:
    """Represents a comparative measurement between Baseline and Urban Grid runs.

    Attributes:
        metric_name: Name of the evaluated metric.
        baseline_value: Numeric value observed in the baseline run.
        urban_grid_value: Numeric value observed in the Urban Grid run.
        delta: Raw numeric difference (urban_grid_value - baseline_value).
        percentage_improvement: Normalized improvement percentage. Positive indicates
            better performance under Urban Grid; negative indicates regression.
            For NEUTRAL metrics, this is 0.0 (no optimization percentage).
        direction: Metric directionality ('lower_is_better', 'higher_is_better', 'neutral').
        is_improved: True if Urban Grid outperformed Baseline, False if regressed,
            or None for NEUTRAL context metrics that are not optimization KPIs.
    """

    metric_name: str
    baseline_value: float
    urban_grid_value: float
    delta: float
    percentage_improvement: float
    direction: MetricDirection
    is_improved: bool | None

    def to_dict(self) -> dict[str, Any]:
        """Convert comparison dataclass to a plain dictionary."""
        result = asdict(self)
        result["direction"] = self.direction.value
        return result


def resolve_metric_direction(
    metric_name: str,
    explicit_direction: MetricDirection | str | None = None,
) -> MetricDirection:
    """Determine the optimization direction for a given metric.

    Args:
        metric_name: Name of the metric.
        explicit_direction: Optional explicit direction override.

    Returns:
        The MetricDirection enum value. Defaults to HIGHER_IS_BETTER if uncatalogued.
    """
    if explicit_direction:
        if isinstance(explicit_direction, MetricDirection):
            return explicit_direction
        clean = str(explicit_direction).lower().strip()
        if clean in ("lower_is_better", "lower", "min", "minimize"):
            return MetricDirection.LOWER_IS_BETTER
        if clean in ("neutral", "none", "info", "informational"):
            return MetricDirection.NEUTRAL
        return MetricDirection.HIGHER_IS_BETTER

    normalized_key = metric_name.lower().strip()
    return METRIC_DIRECTION_REGISTRY.get(normalized_key, MetricDirection.HIGHER_IS_BETTER)


def calculate_percentage_improvement(
    baseline_value: float,
    urban_grid_value: float,
    direction: MetricDirection,
) -> float:
    """Calculate the percentage improvement of Urban Grid over Baseline.

    For HIGHER_IS_BETTER metrics (e.g. speed, throughput):
        improvement = ((urban_grid - baseline) / baseline) * 100%

    For LOWER_IS_BETTER metrics (e.g. delay, queue length):
        improvement = ((baseline - urban_grid) / baseline) * 100%
        (A decrease in delay yields a positive improvement percentage).

    For NEUTRAL metrics (e.g. vehicle_count, arrival_rate):
        Returns 0.0% (informational context, not optimization KPI).

    Safe zero-division handling:
    - If baseline is 0.0 and urban_grid is 0.0, improvement is 0.0%.
    - If baseline is 0.0 and urban_grid is non-zero, returns 0.0% to avoid division
      by zero while the raw delta accurately captures the absolute change.

    Args:
        baseline_value: The baseline numeric score.
        urban_grid_value: The Urban Grid numeric score.
        direction: MetricDirection enum indicating if higher, lower, or neutral.

    Returns:
        Percentage improvement as a float rounded to 2 decimal places.
    """
    if direction == MetricDirection.NEUTRAL or baseline_value == 0.0:
        return 0.0

    if direction == MetricDirection.HIGHER_IS_BETTER:
        pct = ((urban_grid_value - baseline_value) / abs(baseline_value)) * 100.0
    else:
        pct = ((baseline_value - urban_grid_value) / abs(baseline_value)) * 100.0

    return round(pct, 2)


def compare_metric(
    metric_name: str,
    baseline_value: float | int,
    urban_grid_value: float | int,
    direction: MetricDirection | str | None = None,
) -> MetricComparison:
    """Compare a single metric between Baseline and Urban Grid runs.

    Args:
        metric_name: Identifier of the metric (e.g., 'average_speed', 'average_delay').
        baseline_value: Baseline run observation.
        urban_grid_value: Urban Grid run observation.
        direction: Optional directionality override.

    Returns:
        MetricComparison object with delta, percentage improvement, and status.
    """
    base_f = float(baseline_value)
    ug_f = float(urban_grid_value)

    dir_enum = resolve_metric_direction(metric_name, direction)
    delta = round(ug_f - base_f, 4)
    improvement_pct = calculate_percentage_improvement(base_f, ug_f, dir_enum)

    if dir_enum == MetricDirection.NEUTRAL:
        is_improved = None
    elif dir_enum == MetricDirection.LOWER_IS_BETTER:
        is_improved = ug_f < base_f
    else:
        is_improved = ug_f > base_f

    return MetricComparison(
        metric_name=metric_name,
        baseline_value=round(base_f, 4),
        urban_grid_value=round(ug_f, 4),
        delta=delta,
        percentage_improvement=improvement_pct,
        direction=dir_enum,
        is_improved=is_improved,
    )


def compare_runs(
    baseline_metrics: Mapping[str, float | int],
    urban_grid_metrics: Mapping[str, float | int],
    directions: Mapping[str, MetricDirection | str] | None = None,
) -> dict[str, MetricComparison]:
    """Compare all overlapping metrics between Baseline and Urban Grid runs.

    Args:
        baseline_metrics: Key-value map of baseline metric results.
        urban_grid_metrics: Key-value map of Urban Grid metric results.
        directions: Optional map specifying custom directionality per metric.

    Returns:
        Dictionary mapping metric names to their MetricComparison results.
    """
    directions = directions or {}
    results: dict[str, MetricComparison] = {}

    common_keys = set(baseline_metrics.keys()) & set(urban_grid_metrics.keys())
    for key in sorted(common_keys):
        results[key] = compare_metric(
            metric_name=key,
            baseline_value=baseline_metrics[key],
            urban_grid_value=urban_grid_metrics[key],
            direction=directions.get(key),
        )

    return results
