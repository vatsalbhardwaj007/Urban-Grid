"""Unit tests for the M4 Analytics Service Layer."""

import json

from analytics.core.baseline_comparator import MetricDirection
from analytics.services.analytics_service import (
    AnalyticsService,
    analyze_run,
    analyze_snapshot,
    compare_analytics_runs,
)
from analytics.tests.mock_data import (
    MOCK_MULTI_INTERSECTION_SNAPSHOT,
    MOCK_SERVICE_BASELINE_RUN,
    MOCK_SERVICE_URBAN_GRID_RUN,
    MOCK_TRAFFIC_STATE_EMPTY,
    MOCK_TRAFFIC_STATE_SINGLE,
)


def test_process_snapshot_multi_intersection():
    """Verify processing of M2 dict[str, TrafficState] format with multiple junctions."""
    result = AnalyticsService.process_snapshot(MOCK_MULTI_INTERSECTION_SNAPSHOT)

    assert result["intersection_count"] == 2
    assert "int_main_1" in result["intersections"]
    assert "int_side_2" in result["intersections"]

    # Main intersection: 10 vehicles, side intersection: 2 vehicles -> 12 total
    net = result["network_summary"]
    assert net["vehicle_count"] == 12
    # Mean speed: (13.0 + 16.0) / 2 = 14.5
    assert net["mean_speed"] == 14.5
    # Total queue: 8.0 + 1.0 = 9.0
    assert net["total_queue"] == 9.0
    # Flow: 40.0 + 10.0 = 50.0
    assert net["flow"] == 50.0

    # Unsupported metrics are cataloged
    assert "average_delay" in result["unsupported_metrics"]
    assert "travel_time" in result["unsupported_metrics"]


def test_process_snapshot_single_state():
    """Verify processing when passed a single TrafficState directly."""
    result = analyze_snapshot(MOCK_TRAFFIC_STATE_SINGLE)

    assert result["intersection_count"] == 1
    assert "int_main_1" in result["intersections"]
    net = result["network_summary"]
    assert net["vehicle_count"] == 10
    assert net["mean_speed"] == 13.0
    assert net["total_queue"] == 8.0


def test_process_snapshot_empty():
    """Verify safe handling of empty or None snapshot inputs."""
    res_empty = analyze_snapshot({})
    assert res_empty["intersection_count"] == 0
    assert res_empty["network_summary"]["vehicle_count"] == 0
    assert res_empty["network_summary"]["mean_speed"] == 0.0

    res_none = analyze_snapshot(None)
    assert res_none["intersection_count"] == 0
    assert res_none["network_summary"]["total_queue"] == 0.0


def test_process_run_repeated_timesteps():
    """Verify aggregation across repeated simulation timesteps representing a run."""
    run_result = analyze_run(MOCK_SERVICE_BASELINE_RUN)

    assert run_result["timestep_count"] == 2
    assert len(run_result["time_series"]) == 2

    # Check time series entry structure
    first_point = run_result["time_series"][0]
    assert "timestamp" in first_point
    assert "mean_speed" in first_point
    assert "total_queue" in first_point
    assert "flow" in first_point

    # Check network run summary
    net = run_result["network_summary"]
    # Step 0: 8.0, Step 10: 7.0 -> mean_speed = 7.5
    assert net["mean_speed"] == 7.5
    # Step 0: 16.0, Step 10: 20.0 -> total_queue = 18.0
    assert net["total_queue"] == 18.0
    # Peak queue across run is 20.0
    assert net["peak_queue"] == 20.0

    # Per-intersection summary
    assert "int_main_1" in run_result["intersections"]
    int_info = run_result["intersections"]["int_main_1"]
    assert int_info["timesteps_observed"] == 2
    assert int_info["metrics"]["mean_speed"] == 7.5


def test_process_run_empty():
    """Verify safe handling of an empty simulation run."""
    empty_run = analyze_run([])
    assert empty_run["timestep_count"] == 0
    assert empty_run["time_series"] == []
    assert empty_run["network_summary"]["mean_speed"] == 0.0
    assert empty_run["network_summary"]["total_queue"] == 0.0


def test_service_compare_runs():
    """Verify Baseline vs Urban Grid comparison orchestrated through the service layer."""
    comparison = compare_analytics_runs(
        baseline_run=MOCK_SERVICE_BASELINE_RUN,
        urban_grid_run=MOCK_SERVICE_URBAN_GRID_RUN,
    )

    summary = comparison["comparison_summary"]
    assert "mean_speed" in summary
    assert "total_queue" in summary
    assert "peak_queue" in summary
    assert "flow" in summary

    # Mean speed: 7.5 -> 18.5: +146.67% improvement
    speed_comp = summary["mean_speed"]
    assert speed_comp["delta"] == 11.0
    assert speed_comp["percentage_improvement"] == 146.67
    assert speed_comp["is_improved"] is True
    assert speed_comp["direction"] == MetricDirection.HIGHER_IS_BETTER.value

    # Total queue: 18.0 -> 4.0: +77.78% improvement (reduction)
    queue_comp = summary["total_queue"]
    assert queue_comp["delta"] == -14.0
    assert queue_comp["percentage_improvement"] == 77.78
    assert queue_comp["is_improved"] is True
    assert queue_comp["direction"] == MetricDirection.LOWER_IS_BETTER.value

    # Per-intersection comparison exists
    assert "int_main_1" in comparison["intersection_comparisons"]
    int_comp = comparison["intersection_comparisons"]["int_main_1"]
    assert int_comp["mean_speed"]["is_improved"] is True


def test_neutral_metrics_in_service_comparison():
    """Verify vehicle_count and arrival_rate are treated as NEUTRAL context metrics."""
    comparison = AnalyticsService.compare_runs(
        baseline_run=MOCK_SERVICE_BASELINE_RUN,
        urban_grid_run=MOCK_SERVICE_URBAN_GRID_RUN,
    )

    summary = comparison["comparison_summary"]

    # vehicle_count: baseline 20.0 -> urban grid 8.0 (delta = -12.0)
    vc = summary["vehicle_count"]
    assert vc["direction"] == "neutral"
    assert vc["delta"] == -12.0
    assert vc["percentage_improvement"] == 0.0
    assert vc["is_improved"] is None

    # arrival_rate: baseline 4.75 -> urban grid 4.75 (same scenario demand)
    ar = summary["arrival_rate"]
    assert ar["direction"] == "neutral"
    assert ar["delta"] == 0.0
    assert ar["percentage_improvement"] == 0.0
    assert ar["is_improved"] is None


def test_unsupported_metrics_in_service():
    """Verify unsupported metrics are cataloged and not falsely computed."""
    snap_result = AnalyticsService.process_snapshot(MOCK_MULTI_INTERSECTION_SNAPSHOT)
    run_result = AnalyticsService.process_run(MOCK_SERVICE_BASELINE_RUN)
    comp_result = AnalyticsService.compare_runs(
        MOCK_SERVICE_BASELINE_RUN, MOCK_SERVICE_URBAN_GRID_RUN
    )

    for res in [snap_result, run_result, comp_result]:
        unsupp = res["unsupported_metrics"]
        assert "average_delay" in unsupp
        assert "travel_time" in unsupp
        assert "average_travel_time" in unsupp
        assert "delay" not in res.get("network_summary", {})
        assert "travel_time" not in res.get("network_summary", {})


def test_api_ready_json_serialization():
    """Verify that all service outputs are directly JSON-serializable for FastAPI consumption."""
    comp_result = AnalyticsService.compare_runs(
        baseline_run=MOCK_SERVICE_BASELINE_RUN,
        urban_grid_run=MOCK_SERVICE_URBAN_GRID_RUN,
    )

    # Must serialize without TypeError
    json_str = json.dumps(comp_result)
    parsed = json.loads(json_str)

    assert "comparison_summary" in parsed
    assert parsed["comparison_summary"]["mean_speed"]["is_improved"] is True
    assert parsed["comparison_summary"]["vehicle_count"]["is_improved"] is None
    assert parsed["unsupported_metrics"]["average_delay"] != ""


def test_missing_lanes_or_fields_resilience():
    """Verify service does not crash when receiving partially empty/malformed TrafficState."""
    malformed_snapshot = {
        "int_weird_1": {
            "timestamp": 50.0,
            "intersection_id": "int_weird_1",
            "lane_features": [],  # Empty lanes
            "total_queue": None,  # None fields
            "mean_speed": None,
        }
    }

    result = AnalyticsService.process_snapshot(malformed_snapshot)
    assert result["intersection_count"] == 1
    assert result["network_summary"]["mean_speed"] == 0.0
    assert result["network_summary"]["total_queue"] == 0.0
