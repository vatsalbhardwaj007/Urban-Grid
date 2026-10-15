"""Analytics Service Layer for Urban Grid (M4).

This module provides a decoupled, API-ready service orchestrating M4 analytics
calculations, time-series aggregations, and baseline comparisons over canonical M2
TrafficState snapshot feeds.

Integrates with:
- M2 interface: dict[str, TrafficState] (e.g. from GET /api/traffic-state)
- M4 adapter: analytics/adapters/traffic_state_adapter.py
- M4 core math: analytics/core/metrics_calculator.py
- M4 comparator: analytics/core/baseline_comparator.py
"""

from typing import Any, Mapping, Sequence

from analytics.adapters.traffic_state_adapter import (
    UNSUPPORTED_TRAFFIC_STATE_METRICS,
    extract_intersection_snapshot,
    extract_run_metrics,
)
from analytics.core.baseline_comparator import compare_runs as core_compare_runs
from analytics.core.metrics_calculator import (
    average_queue_length,
    average_speed,
    maximum_queue_length,
)


def _is_single_traffic_state(obj: Any) -> bool:
    """Check if the object represents a single TrafficState rather than a dict of them."""
    if isinstance(obj, Mapping):
        return "lane_features" in obj or ("intersection_id" in obj and "timestamp" in obj)
    return hasattr(obj, "lane_features") or (
        hasattr(obj, "intersection_id") and hasattr(obj, "timestamp")
    )


def _normalize_snapshot_input(snapshot: Any) -> dict[str, Any]:
    """Normalize input into a dictionary mapping intersection_id to TrafficState.

    Accepts:
    - dict[str, TrafficState]: Standard M2 return format
    - TrafficState: Single intersection object/dict
    - None or empty collection: Handled safely
    """
    if not snapshot:
        return {}

    if _is_single_traffic_state(snapshot):
        int_id = getattr(snapshot, "intersection_id", None)
        if int_id is None and isinstance(snapshot, Mapping):
            int_id = snapshot.get("intersection_id", "default")
        return {str(int_id or "default"): snapshot}

    if isinstance(snapshot, Mapping):
        return {str(k): v for k, v in snapshot.items()}

    return {}


class AnalyticsService:
    """Orchestrates traffic analytics calculations on M2 TrafficState streams."""

    @staticmethod
    def process_snapshot(snapshot: Any) -> dict[str, Any]:
        """Process a single simulation timestep containing one or more intersection states.

        Args:
            snapshot: A dictionary mapping intersection_id to TrafficState
                (e.g., dict[str, TrafficState]), or a single TrafficState object.

        Returns:
            A JSON-serializable dictionary with per-intersection metrics and
            a network-wide summary.
        """
        normalized = _normalize_snapshot_input(snapshot)

        if not normalized:
            return {
                "timestamp": 0.0,
                "intersection_count": 0,
                "intersections": {},
                "network_summary": {
                    "vehicle_count": 0,
                    "mean_speed": 0.0,
                    "total_queue": 0.0,
                    "mean_queue": 0.0,
                    "maximum_queue": 0.0,
                    "density": 0.0,
                    "arrival_rate": 0.0,
                    "flow": 0.0,
                    "occupancy": 0.0,
                },
                "unsupported_metrics": dict(UNSUPPORTED_TRAFFIC_STATE_METRICS),
            }

        intersections_processed: dict[str, dict[str, Any]] = {}
        ts_val = 0.0

        for int_id, state in normalized.items():
            processed = extract_intersection_snapshot(state)
            intersections_processed[int_id] = processed
            if processed.get("timestamp"):
                ts_val = float(processed["timestamp"])

        # Compute network-wide aggregations across all intersections in this timestep
        all_snapshots = list(intersections_processed.values())
        speeds = [s["mean_speed"] for s in all_snapshots]
        total_queues = [s["total_queue"] for s in all_snapshots]
        mean_queues = [s["mean_queue"] for s in all_snapshots]
        max_queues = [s["maximum_queue"] for s in all_snapshots]
        densities = [s["density"] for s in all_snapshots]
        occupancies = [s["occupancy"] for s in all_snapshots]

        network_vehicle_count = sum(s["vehicle_count"] for s in all_snapshots)
        network_arrival_rate = round(sum(s["arrival_rate"] for s in all_snapshots), 4)
        network_flow = round(sum(s["flow"] for s in all_snapshots), 4)

        n = float(len(all_snapshots))
        network_summary = {
            "vehicle_count": network_vehicle_count,
            "mean_speed": average_speed(speeds),
            "total_queue": round(sum(total_queues), 4),
            "mean_queue": average_queue_length(mean_queues),
            "maximum_queue": maximum_queue_length(max_queues),
            "density": round(sum(densities) / n, 4) if n > 0 else 0.0,
            "arrival_rate": network_arrival_rate,
            "flow": network_flow,
            "occupancy": round(sum(occupancies) / n, 4) if n > 0 else 0.0,
        }

        return {
            "timestamp": ts_val,
            "intersection_count": len(intersections_processed),
            "intersections": intersections_processed,
            "network_summary": network_summary,
            "unsupported_metrics": dict(UNSUPPORTED_TRAFFIC_STATE_METRICS),
        }

    @staticmethod
    def process_run(run_snapshots: Sequence[Any]) -> dict[str, Any]:
        """Process a sequence of repeated simulation timesteps representing a full run.

        Workflow:
            TrafficState snapshots
                    ↓
            M4 adapter
                    ↓
            per-timestep metrics
                    ↓
            run aggregation
                    ↓
            standardized analytics result

        Args:
            run_snapshots: Sequence of snapshot dictionaries (dict[str, TrafficState])
                or individual TrafficState snapshots over time.

        Returns:
            A JSON-serializable dictionary with aggregated run metrics,
            per-intersection run summaries, time-series points, and unsupported notes.
        """
        if not run_snapshots:
            return {
                "timestep_count": 0,
                "network_summary": {
                    "vehicle_count": 0.0,
                    "mean_speed": 0.0,
                    "total_queue": 0.0,
                    "mean_queue": 0.0,
                    "peak_queue": 0.0,
                    "density": 0.0,
                    "arrival_rate": 0.0,
                    "flow": 0.0,
                    "occupancy": 0.0,
                },
                "intersections": {},
                "time_series": [],
                "unsupported_metrics": dict(UNSUPPORTED_TRAFFIC_STATE_METRICS),
            }

        # Step 1: Process each timestep
        processed_timesteps: list[dict[str, Any]] = []
        intersection_timesteps: dict[str, list[dict[str, Any]]] = {}

        for step in run_snapshots:
            step_analytics = AnalyticsService.process_snapshot(step)
            processed_timesteps.append(step_analytics)

            for int_id, int_data in step_analytics["intersections"].items():
                if int_id not in intersection_timesteps:
                    intersection_timesteps[int_id] = []
                intersection_timesteps[int_id].append(int_data)

        # Step 2: Per-intersection run aggregation
        intersections_summary: dict[str, dict[str, Any]] = {}
        for int_id, states in intersection_timesteps.items():
            intersections_summary[int_id] = {
                "intersection_id": int_id,
                "timesteps_observed": len(states),
                "metrics": extract_run_metrics(states),
            }

        # Step 3: Network-wide run aggregation across all timesteps
        time_series_points: list[dict[str, Any]] = []
        net_speeds: list[float] = []
        net_total_queues: list[float] = []
        net_mean_queues: list[float] = []
        net_max_queues: list[float] = []
        net_densities: list[float] = []
        net_arrivals: list[float] = []
        net_flows: list[float] = []
        net_occupancies: list[float] = []
        net_vehicle_counts: list[float] = []

        for step in processed_timesteps:
            ns = step["network_summary"]
            ts = step["timestamp"]

            time_series_points.append(
                {
                    "timestamp": ts,
                    **ns,
                }
            )

            net_speeds.append(ns["mean_speed"])
            net_total_queues.append(ns["total_queue"])
            net_mean_queues.append(ns["mean_queue"])
            net_max_queues.append(ns["maximum_queue"])
            net_densities.append(ns["density"])
            net_arrivals.append(ns["arrival_rate"])
            net_flows.append(ns["flow"])
            net_occupancies.append(ns["occupancy"])
            net_vehicle_counts.append(float(ns["vehicle_count"]))

        n = float(len(processed_timesteps))
        network_run_summary = {
            "vehicle_count": round(sum(net_vehicle_counts) / n, 4),
            "mean_speed": average_speed(net_speeds),
            "total_queue": average_queue_length(net_total_queues),
            "mean_queue": average_queue_length(net_mean_queues),
            "peak_queue": maximum_queue_length(net_total_queues),
            "density": round(sum(net_densities) / n, 4),
            "arrival_rate": round(sum(net_arrivals) / n, 4),
            "flow": round(sum(net_flows) / n, 4),
            "occupancy": round(sum(net_occupancies) / n, 4),
        }

        return {
            "timestep_count": len(processed_timesteps),
            "network_summary": network_run_summary,
            "intersections": intersections_summary,
            "time_series": time_series_points,
            "unsupported_metrics": dict(UNSUPPORTED_TRAFFIC_STATE_METRICS),
        }

    @staticmethod
    def compare_runs(
        baseline_run: Sequence[Any],
        urban_grid_run: Sequence[Any],
    ) -> dict[str, Any]:
        """Orchestrate baseline vs. Urban Grid comparison across two independent simulation runs.

        Standardized result structure ready for GET /api/analytics/compare:
        - Direction-aware delta and percentage improvement
        - Neutral context metrics preserved without false KPI scoring
        - Unsupported metrics clearly cataloged

        Args:
            baseline_run: Sequence of snapshots representing the baseline run.
            urban_grid_run: Sequence of snapshots representing the Urban Grid run.

        Returns:
            JSON-serializable comparison dictionary.
        """
        baseline_analytics = AnalyticsService.process_run(baseline_run)
        urban_grid_analytics = AnalyticsService.process_run(urban_grid_run)

        # Network-level summary comparison
        raw_net_comp = core_compare_runs(
            baseline_metrics=baseline_analytics["network_summary"],
            urban_grid_metrics=urban_grid_analytics["network_summary"],
        )
        network_comparison = {k: v.to_dict() for k, v in raw_net_comp.items()}

        # Per-intersection comparison
        intersection_comparisons: dict[str, dict[str, Any]] = {}
        common_intersections = set(baseline_analytics["intersections"].keys()) & set(
            urban_grid_analytics["intersections"].keys()
        )

        for int_id in sorted(common_intersections):
            base_int_metrics = baseline_analytics["intersections"][int_id]["metrics"]
            ug_int_metrics = urban_grid_analytics["intersections"][int_id]["metrics"]
            int_comp = core_compare_runs(base_int_metrics, ug_int_metrics)
            intersection_comparisons[int_id] = {k: v.to_dict() for k, v in int_comp.items()}

        return {
            "comparison_summary": network_comparison,
            "intersection_comparisons": intersection_comparisons,
            "baseline_summary": baseline_analytics["network_summary"],
            "urban_grid_summary": urban_grid_analytics["network_summary"],
            "timestep_counts": {
                "baseline": baseline_analytics["timestep_count"],
                "urban_grid": urban_grid_analytics["timestep_count"],
            },
            "unsupported_metrics": dict(UNSUPPORTED_TRAFFIC_STATE_METRICS),
        }


# Convenience module-level aliases
analyze_snapshot = AnalyticsService.process_snapshot
analyze_run = AnalyticsService.process_run
compare_analytics_runs = AnalyticsService.compare_runs
