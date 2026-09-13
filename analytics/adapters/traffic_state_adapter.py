"""TrafficState Adapter Layer for Urban Grid (M4).

This module bridges M2's canonical TrafficState data structure to M4's
standardized metrics calculator and baseline comparator.

Canonical M2 TrafficState Structure:
    TrafficState
    ├── timestamp
    ├── intersection_id
    ├── lane_features[]
    │   ├── lane_id
    │   ├── vehicle_count
    │   ├── mean_speed
    │   ├── queue_length
    │   ├── occupancy
    │   ├── arrival_rate
    │   ├── density
    │   └── flow
    ├── total_queue
    ├── mean_speed
    ├── arrival_rate
    ├── density
    ├── signal_phase
    └── green_remaining

Design Rules:
1. Zero SUMO/TraCI dependency.
2. Safe access handling both dictionary mappings and objects with attributes.
3. Safe empty input and zero-division handling.
4. Transparent documentation of metrics that cannot be calculated from instantaneous
   TrafficState snapshots alone.
"""

from typing import Any, Mapping, Sequence

from analytics.core.baseline_comparator import MetricComparison, compare_runs
from analytics.core.metrics_calculator import (
    average_queue_length,
    average_speed,
    maximum_queue_length,
    vehicle_count,
)

# Explicit documentation of metrics that CANNOT be calculated from
# instantaneous TrafficState snapshots without additional telemetry.
UNSUPPORTED_TRAFFIC_STATE_METRICS: dict[str, str] = {
    "average_delay": (
        "TrafficState provides instantaneous spatial speeds and queue states at "
        "an intersection, but does NOT track individual vehicle trip start/end times "
        "or compare against free-flow trip travel times. End-to-end delay requires "
        "vehicle trip completion logs."
    ),
    "travel_time": (
        "Trip travel time requires vehicle-level origin-destination trajectory tracking, "
        "which is outside the scope of intersection-level instantaneous TrafficState snapshots."
    ),
    "average_travel_time": (
        "Average travel time requires vehicle trip completion records across routes, "
        "which is outside the scope of intersection-level instantaneous TrafficState snapshots."
    ),
}


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Safely extract a field from either a dictionary or an object."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def extract_lane_metrics(state: Any) -> list[dict[str, Any]]:
    """Extract and sanitize lane-level features from a TrafficState snapshot.

    Args:
        state: A TrafficState dictionary or object.

    Returns:
        A list of standardized dictionaries for each lane feature.
        Returns an empty list if lane_features is missing or empty.
    """
    raw_lanes = _get_field(state, "lane_features", [])
    if not raw_lanes:
        return []

    sanitized_lanes: list[dict[str, Any]] = []
    for lane in raw_lanes:
        sanitized_lanes.append(
            {
                "lane_id": str(_get_field(lane, "lane_id", "unknown")),
                "vehicle_count": int(_get_field(lane, "vehicle_count", 0) or 0),
                "mean_speed": float(_get_field(lane, "mean_speed", 0.0) or 0.0),
                "queue_length": float(_get_field(lane, "queue_length", 0.0) or 0.0),
                "occupancy": float(_get_field(lane, "occupancy", 0.0) or 0.0),
                "arrival_rate": float(_get_field(lane, "arrival_rate", 0.0) or 0.0),
                "density": float(_get_field(lane, "density", 0.0) or 0.0),
                "flow": float(_get_field(lane, "flow", 0.0) or 0.0),
            }
        )

    return sanitized_lanes


def extract_intersection_snapshot(state: Any) -> dict[str, Any]:
    """Process a single TrafficState snapshot into standardized intersection metrics.

    Reuses core functions from metrics_calculator for robust mathematical handling.

    Args:
        state: A single TrafficState dictionary or object.

    Returns:
        A dictionary containing intersection-level and aggregated lane metrics.
    """
    lanes = extract_lane_metrics(state)

    lane_speeds = [l["mean_speed"] for l in lanes]
    lane_queues = [l["queue_length"] for l in lanes]
    lane_vehicles = [l["vehicle_count"] for l in lanes]
    lane_densities = [l["density"] for l in lanes]
    lane_arrivals = [l["arrival_rate"] for l in lanes]
    lane_flows = [l["flow"] for l in lanes]
    lane_occupancies = [l["occupancy"] for l in lanes]

    # Intersection-level vehicle count: sum of lanes if not directly given
    total_vehicles = sum(lane_vehicles)

    # Intersection-level mean speed: prioritize state's mean_speed; fallback to lane avg
    state_mean_speed = _get_field(state, "mean_speed")
    if state_mean_speed is not None:
        mean_spd = float(state_mean_speed)
    else:
        mean_spd = average_speed(lane_speeds)

    # Intersection total queue: prioritize state's total_queue; fallback to sum of queues
    state_total_queue = _get_field(state, "total_queue")
    if state_total_queue is not None:
        total_q = float(state_total_queue)
    else:
        total_q = sum(lane_queues)

    # Mean and max queue across lanes
    mean_q = average_queue_length(lane_queues)
    max_q = maximum_queue_length(lane_queues)

    # Arrival rate & density: prioritize state fields; fallback to lane aggregations
    state_arrival_rate = _get_field(state, "arrival_rate")
    arrival_rt = (
        float(state_arrival_rate)
        if state_arrival_rate is not None
        else sum(lane_arrivals)
    )

    state_density = _get_field(state, "density")
    dens = (
        float(state_density)
        if state_density is not None
        else (round(sum(lane_densities) / len(lane_densities), 4) if lane_densities else 0.0)
    )

    total_fl = round(sum(lane_flows), 4)
    avg_occ = (
        round(sum(lane_occupancies) / len(lane_occupancies), 4)
        if lane_occupancies
        else 0.0
    )

    return {
        "timestamp": _get_field(state, "timestamp", 0.0),
        "intersection_id": str(_get_field(state, "intersection_id", "")),
        "signal_phase": _get_field(state, "signal_phase"),
        "green_remaining": _get_field(state, "green_remaining"),
        "vehicle_count": total_vehicles,
        "mean_speed": round(mean_spd, 4),
        "total_queue": round(total_q, 4),
        "mean_queue": round(mean_q, 4),
        "maximum_queue": round(max_q, 4),
        "arrival_rate": round(arrival_rt, 4),
        "density": round(dens, 4),
        "flow": total_fl,
        "occupancy": avg_occ,
        "lane_features": lanes,
    }


def extract_run_metrics(states: Sequence[Any]) -> dict[str, float]:
    """Aggregate a sequence of TrafficState snapshots representing an experiment run.

    Computes standardized summary metrics across all timesteps in the run.

    Args:
        states: A sequence of TrafficState snapshots over time.

    Returns:
        Dictionary mapping metric names to their aggregated float values.
        Returns all zeros if states is empty.
    """
    if not states:
        return {
            "vehicle_count": 0.0,
            "mean_speed": 0.0,
            "total_queue": 0.0,
            "mean_queue": 0.0,
            "peak_queue": 0.0,
            "density": 0.0,
            "arrival_rate": 0.0,
            "flow": 0.0,
            "occupancy": 0.0,
        }

    processed_snapshots = [extract_intersection_snapshot(s) for s in states]

    speeds = [s["mean_speed"] for s in processed_snapshots]
    total_queues = [s["total_queue"] for s in processed_snapshots]
    mean_queues = [s["mean_queue"] for s in processed_snapshots]
    vehicles = [float(s["vehicle_count"]) for s in processed_snapshots]
    densities = [s["density"] for s in processed_snapshots]
    arrivals = [s["arrival_rate"] for s in processed_snapshots]
    flows = [s["flow"] for s in processed_snapshots]
    occupancies = [s["occupancy"] for s in processed_snapshots]

    n = float(len(processed_snapshots))

    return {
        "vehicle_count": round(sum(vehicles) / n, 4),
        "mean_speed": average_speed(speeds),
        "total_queue": average_queue_length(total_queues),
        "mean_queue": average_queue_length(mean_queues),
        "peak_queue": maximum_queue_length(total_queues),
        "density": round(sum(densities) / n, 4),
        "arrival_rate": round(sum(arrivals) / n, 4),
        "flow": round(sum(flows) / n, 4),
        "occupancy": round(sum(occupancies) / n, 4),
    }


def compare_traffic_state_runs(
    baseline_states: Sequence[Any],
    urban_grid_states: Sequence[Any],
    directions: Mapping[str, Any] | None = None,
) -> dict[str, MetricComparison]:
    """Compare a Baseline run and an Urban Grid run derived from TrafficState streams.

    Preserves existing direction-aware improvement logic:
    - Lower is better: total_queue, mean_queue, peak_queue, density, occupancy
    - Higher is better: mean_speed, flow, vehicle_count, arrival_rate

    Args:
        baseline_states: Sequence of TrafficState snapshots for the baseline run.
        urban_grid_states: Sequence of TrafficState snapshots for the Urban Grid run.
        directions: Optional mapping of custom metric directions.

    Returns:
        Dictionary mapping metric names to their MetricComparison results.
    """
    baseline_metrics = extract_run_metrics(baseline_states)
    urban_grid_metrics = extract_run_metrics(urban_grid_states)

    return compare_runs(
        baseline_metrics=baseline_metrics,
        urban_grid_metrics=urban_grid_metrics,
        directions=directions,
    )
