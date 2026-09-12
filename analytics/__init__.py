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

from analytics.adapters.traffic_state_adapter import (
    UNSUPPORTED_TRAFFIC_STATE_METRICS,
    compare_traffic_state_runs,
    extract_intersection_snapshot,
    extract_lane_metrics,
    extract_run_metrics,
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
    "UNSUPPORTED_TRAFFIC_STATE_METRICS",
    "compare_traffic_state_runs",
    "extract_intersection_snapshot",
    "extract_lane_metrics",
    "extract_run_metrics",
]
