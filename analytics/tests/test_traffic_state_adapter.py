"""Unit tests for the M2 TrafficState adapter layer."""

from analytics.adapters.traffic_state_adapter import (
    UNSUPPORTED_TRAFFIC_STATE_METRICS,
    compare_traffic_state_runs,
    extract_intersection_snapshot,
    extract_lane_metrics,
    extract_run_metrics,
)
from analytics.core.baseline_comparator import MetricDirection
from analytics.tests.mock_data import (
    MOCK_TRAFFIC_STATE_BASELINE_STREAM,
    MOCK_TRAFFIC_STATE_EMPTY,
    MOCK_TRAFFIC_STATE_SINGLE,
    MOCK_TRAFFIC_STATE_URBAN_GRID_STREAM,
)


def test_extract_lane_metrics_normal():
    """Verify lane-level features are correctly extracted from TrafficState."""
    lanes = extract_lane_metrics(MOCK_TRAFFIC_STATE_SINGLE)
    assert len(lanes) == 2

    north = lanes[0]
    assert north["lane_id"] == "lane_north_0"
    assert north["vehicle_count"] == 4
    assert north["mean_speed"] == 12.0
    assert north["queue_length"] == 3.0
    assert north["occupancy"] == 0.25
    assert north["arrival_rate"] == 1.2
    assert north["density"] == 20.0
    assert north["flow"] == 15.0

    south = lanes[1]
    assert south["lane_id"] == "lane_south_0"
    assert south["vehicle_count"] == 6
    assert south["mean_speed"] == 14.0
    assert south["queue_length"] == 5.0
    assert south["occupancy"] == 0.35
    assert south["flow"] == 25.0


def test_extract_lane_metrics_empty():
    """Verify safe handling of missing or empty lane features."""
    assert extract_lane_metrics(MOCK_TRAFFIC_STATE_EMPTY) == []
    assert extract_lane_metrics({}) == []
    assert extract_lane_metrics(None) == []


def test_extract_intersection_snapshot_normal():
    """Verify intersection-level metrics computation and lane aggregation."""
    snapshot = extract_intersection_snapshot(MOCK_TRAFFIC_STATE_SINGLE)

    assert snapshot["timestamp"] == 10.0
    assert snapshot["intersection_id"] == "int_main_1"
    assert snapshot["signal_phase"] == 2
    assert snapshot["green_remaining"] == 15.5

    # Sum of lanes: 4 + 6 = 10
    assert snapshot["vehicle_count"] == 10
    # Direct intersection mean_speed: 13.0
    assert snapshot["mean_speed"] == 13.0
    # Direct intersection total_queue: 8.0
    assert snapshot["total_queue"] == 8.0
    # Mean queue across lanes: (3.0 + 5.0) / 2 = 4.0
    assert snapshot["mean_queue"] == 4.0
    # Max queue across lanes: max(3.0, 5.0) = 5.0
    assert snapshot["maximum_queue"] == 5.0
    # Flow: 15.0 + 25.0 = 40.0
    assert snapshot["flow"] == 40.0
    # Density: 25.0
    assert snapshot["density"] == 25.0
    # Arrival rate: 3.0
    assert snapshot["arrival_rate"] == 3.0
    # Average occupancy across lanes: (0.25 + 0.35) / 2 = 0.3
    assert snapshot["occupancy"] == 0.3
    assert len(snapshot["lane_features"]) == 2


def test_extract_intersection_snapshot_fallback():
    """Verify fallback to lane aggregations when top-level fields are None."""
    partial_state = {
        "timestamp": 5.0,
        "intersection_id": "int_fallback",
        "lane_features": [
            {
                "lane_id": "l0",
                "vehicle_count": 2,
                "mean_speed": 10.0,
                "queue_length": 2.0,
                "occupancy": 0.2,
                "arrival_rate": 1.0,
                "density": 10.0,
                "flow": 5.0,
            },
            {
                "lane_id": "l1",
                "vehicle_count": 4,
                "mean_speed": 20.0,
                "queue_length": 6.0,
                "occupancy": 0.4,
                "arrival_rate": 2.0,
                "density": 20.0,
                "flow": 15.0,
            },
        ],
        "total_queue": None,
        "mean_speed": None,
        "arrival_rate": None,
        "density": None,
    }

    snapshot = extract_intersection_snapshot(partial_state)
    # Mean speed derived from lanes: (10 + 20) / 2 = 15.0
    assert snapshot["mean_speed"] == 15.0
    # Total queue derived from sum: 2 + 6 = 8.0
    assert snapshot["total_queue"] == 8.0
    # Arrival rate derived from sum: 1.0 + 2.0 = 3.0
    assert snapshot["arrival_rate"] == 3.0
    # Density derived from average: (10 + 20) / 2 = 15.0
    assert snapshot["density"] == 15.0


def test_extract_intersection_snapshot_empty():
    """Verify safe zero handling for empty TrafficState."""
    snapshot = extract_intersection_snapshot(MOCK_TRAFFIC_STATE_EMPTY)
    assert snapshot["vehicle_count"] == 0
    assert snapshot["mean_speed"] == 0.0
    assert snapshot["total_queue"] == 0.0
    assert snapshot["mean_queue"] == 0.0
    assert snapshot["maximum_queue"] == 0.0
    assert snapshot["flow"] == 0.0
    assert snapshot["lane_features"] == []


def test_extract_run_metrics():
    """Verify run-level aggregation over multi-timestep streams."""
    baseline_metrics = extract_run_metrics(MOCK_TRAFFIC_STATE_BASELINE_STREAM)

    # 2 timesteps: total_queue = 16.0, 20.0 -> avg = 18.0
    assert baseline_metrics["total_queue"] == 18.0
    # peak_queue = max(16.0, 20.0) = 20.0
    assert baseline_metrics["peak_queue"] == 20.0
    # mean_speed = (8.0 + 7.0) / 2 = 7.5
    assert baseline_metrics["mean_speed"] == 7.5
    # vehicle_count = (18 + 22) / 2 = 20.0
    assert baseline_metrics["vehicle_count"] == 20.0
    # flow = (22.0 + 24.0) / 2 = 23.0
    assert baseline_metrics["flow"] == 23.0

    # Empty stream returns safe zeros
    empty_metrics = extract_run_metrics([])
    assert empty_metrics["mean_speed"] == 0.0
    assert empty_metrics["total_queue"] == 0.0
    assert empty_metrics["peak_queue"] == 0.0


def test_compare_traffic_state_runs():
    """Verify Baseline vs Urban Grid comparison using TrafficState streams."""
    comparison = compare_traffic_state_runs(
        baseline_states=MOCK_TRAFFIC_STATE_BASELINE_STREAM,
        urban_grid_states=MOCK_TRAFFIC_STATE_URBAN_GRID_STREAM,
    )

    # Check that key metrics were evaluated
    assert "mean_speed" in comparison
    assert "total_queue" in comparison
    assert "peak_queue" in comparison
    assert "flow" in comparison

    # Mean speed: baseline 7.5 -> urban grid 18.5
    # Delta: +11.0, Improvement: ((18.5 - 7.5) / 7.5) * 100 = +146.67%
    speed_res = comparison["mean_speed"]
    assert speed_res.delta == 11.0
    assert speed_res.percentage_improvement == 146.67
    assert speed_res.is_improved is True
    assert speed_res.direction == MetricDirection.HIGHER_IS_BETTER

    # Total queue: baseline 18.0 -> urban grid 4.0
    # Delta: -14.0, Improvement: ((18.0 - 4.0) / 18.0) * 100 = +77.78%
    queue_res = comparison["total_queue"]
    assert queue_res.delta == -14.0
    assert queue_res.percentage_improvement == 77.78
    assert queue_res.is_improved is True
    assert queue_res.direction == MetricDirection.LOWER_IS_BETTER

    # Peak queue: baseline 20.0 -> urban grid 5.0
    # Delta: -15.0, Improvement: ((20.0 - 5.0) / 20.0) * 100 = +75.0%
    peak_res = comparison["peak_queue"]
    assert peak_res.delta == -15.0
    assert peak_res.percentage_improvement == 75.0
    assert peak_res.is_improved is True
    assert peak_res.direction == MetricDirection.LOWER_IS_BETTER

    # Neutral context metrics: vehicle_count and arrival_rate
    vc_res = comparison["vehicle_count"]
    assert vc_res.direction == MetricDirection.NEUTRAL
    assert vc_res.delta == -12.0  # baseline 20.0 -> urban grid 8.0
    assert vc_res.percentage_improvement == 0.0  # Not scored as optimization KPI
    assert vc_res.is_improved is None

    ar_res = comparison["arrival_rate"]
    assert ar_res.direction == MetricDirection.NEUTRAL
    assert ar_res.delta == 0.0  # baseline 4.75 -> urban grid 4.75
    assert ar_res.percentage_improvement == 0.0
    assert ar_res.is_improved is None


def test_object_input_support():
    """Verify adapter works with Python objects having attributes, not just dicts."""
    class LaneObj:
        def __init__(self, lane_id, count, speed, queue):
            self.lane_id = lane_id
            self.vehicle_count = count
            self.mean_speed = speed
            self.queue_length = queue
            self.occupancy = 0.1
            self.arrival_rate = 0.5
            self.density = 10.0
            self.flow = 5.0

    class StateObj:
        def __init__(self):
            self.timestamp = 100.0
            self.intersection_id = "int_obj_1"
            self.lane_features = [LaneObj("l0", 5, 15.0, 2.0)]
            self.total_queue = 2.0
            self.mean_speed = 15.0
            self.arrival_rate = 0.5
            self.density = 10.0
            self.signal_phase = 1
            self.green_remaining = 10.0

    obj = StateObj()
    snapshot = extract_intersection_snapshot(obj)
    assert snapshot["intersection_id"] == "int_obj_1"
    assert snapshot["mean_speed"] == 15.0
    assert snapshot["vehicle_count"] == 5
    assert len(snapshot["lane_features"]) == 1


def test_unsupported_metrics_documented():
    """Verify unsupported metrics are explicitly cataloged with clear reasons."""
    assert "average_delay" in UNSUPPORTED_TRAFFIC_STATE_METRICS
    assert "travel_time" in UNSUPPORTED_TRAFFIC_STATE_METRICS
    assert "trip" in UNSUPPORTED_TRAFFIC_STATE_METRICS["average_delay"].lower()
