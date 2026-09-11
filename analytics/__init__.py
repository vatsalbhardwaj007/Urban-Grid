"""Urban Grid - Traffic Analytics & Data Layer (M4).

This package provides pure-Python measurement and analytics algorithms for traffic metrics
and baseline comparison, designed to be decoupled from SUMO/TraCI and API frameworks.
"""

from analytics.core.metrics_calculator import (
    average_delay,
    average_queue_length,
    average_speed,
    maximum_queue_length,
    throughput,
    vehicle_count,
)
from analytics.core.baseline_comparator import (
    MetricComparison,
    MetricDirection,
    compare_metric,
    compare_runs,
)

__all__ = [
    "average_delay",
    "average_queue_length",
    "average_speed",
    "maximum_queue_length",
    "throughput",
    "vehicle_count",
    "MetricComparison",
    "MetricDirection",
    "compare_metric",
    "compare_runs",
]
