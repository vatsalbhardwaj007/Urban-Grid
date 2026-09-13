"""Analytics Service Layer for Urban Grid (M4).

Provides an API-ready boundary between M2 TrafficState snapshots and M4 metric calculation
and comparison logic.
"""

from analytics.services.analytics_service import (
    AnalyticsService,
    analyze_run,
    analyze_snapshot,
    compare_analytics_runs,
)

__all__ = [
    "AnalyticsService",
    "analyze_run",
    "analyze_snapshot",
    "compare_analytics_runs",
]
