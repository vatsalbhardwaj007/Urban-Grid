"""Unit tests for standardized traffic metrics calculation engine."""

from analytics.core.metrics_calculator import (
    average_delay,
    average_queue_length,
    average_speed,
    calculate_traffic_summary,
    maximum_queue_length,
    throughput,
    vehicle_count,
)
from analytics.tests.mock_data import (
    MOCK_BASELINE_DATASET,
    MOCK_EMPTY_DATASET,
    MOCK_KNOWN_DATASET,
    MOCK_URBAN_GRID_DATASET,
)


def test_vehicle_count():
    """Test vehicle counting with various sequence inputs and edge cases."""
    # Known dataset: 3 vehicles
    assert vehicle_count(MOCK_KNOWN_DATASET["vehicles"]) == 3

    # Baseline & Urban Grid datasets: 10 vehicles each
    assert vehicle_count(MOCK_BASELINE_DATASET["vehicles"]) == 10
    assert vehicle_count(MOCK_URBAN_GRID_DATASET["vehicles"]) == 10

    # Empty inputs
    assert vehicle_count(MOCK_EMPTY_DATASET["vehicles"]) == 0
    assert vehicle_count([]) == 0
    assert vehicle_count(None) == 0


def test_average_speed():
    """Test arithmetic average speed calculation and rounding."""
    # Known dataset: [10.0, 20.0, 30.0] -> 20.0
    assert average_speed(MOCK_KNOWN_DATASET["speeds"]) == 20.0

    # Baseline: average of 10 speeds is 13.0
    assert average_speed(MOCK_BASELINE_DATASET["speeds"]) == 13.0

    # Urban Grid: average of 10 speeds is 20.0
    assert average_speed(MOCK_URBAN_GRID_DATASET["speeds"]) == 20.0

    # Single speed
    assert average_speed([15.5]) == 15.5

    # Safe zero/empty handling
    assert average_speed(MOCK_EMPTY_DATASET["speeds"]) == 0.0
    assert average_speed([]) == 0.0
    assert average_speed(None) == 0.0


def test_average_queue_length():
    """Test average queue length calculation."""
    # Known dataset: [2.0, 4.0, 6.0, 8.0] -> 5.0
    assert average_queue_length(MOCK_KNOWN_DATASET["queue_lengths"]) == 5.0

    # Baseline: [8, 12, 15, 10, 15] -> 12.0
    assert average_queue_length(MOCK_BASELINE_DATASET["queue_lengths"]) == 12.0

    # Urban Grid: [3, 4, 5, 2, 6] -> 4.0
    assert average_queue_length(MOCK_URBAN_GRID_DATASET["queue_lengths"]) == 4.0

    # Empty / None handling
    assert average_queue_length(MOCK_EMPTY_DATASET["queue_lengths"]) == 0.0
    assert average_queue_length([]) == 0.0
    assert average_queue_length(None) == 0.0


def test_maximum_queue_length():
    """Test maximum queue length extraction."""
    # Known dataset: max of [2, 4, 6, 8] is 8.0
    assert maximum_queue_length(MOCK_KNOWN_DATASET["queue_lengths"]) == 8.0

    # Baseline: max of [8, 12, 15, 10, 15] is 15.0
    assert maximum_queue_length(MOCK_BASELINE_DATASET["queue_lengths"]) == 15.0

    # Urban Grid: max of [3, 4, 5, 2, 6] is 6.0
    assert maximum_queue_length(MOCK_URBAN_GRID_DATASET["queue_lengths"]) == 6.0

    # Empty / None handling
    assert maximum_queue_length(MOCK_EMPTY_DATASET["queue_lengths"]) == 0.0
    assert maximum_queue_length([]) == 0.0
    assert maximum_queue_length(None) == 0.0


def test_throughput():
    """Test throughput rates with different windows and per-hour options."""
    # Known dataset: 60 vehicles in 60 seconds
    # Rate = 1.0 veh/s
    assert throughput(MOCK_KNOWN_DATASET["completed_vehicles"], 60.0) == 1.0
    # Rate per hour = 3600.0 veh/h
    assert throughput(MOCK_KNOWN_DATASET["completed_vehicles"], 60.0, per_hour=True) == 3600.0

    # Sequence input (list of vehicle IDs)
    completed_list = ["v1", "v2", "v3", "v4"]
    assert throughput(completed_list, 10.0) == 0.4

    # Baseline dataset: 120 veh in 3600s -> 120 veh/h
    assert throughput(
        MOCK_BASELINE_DATASET["completed_vehicles"],
        MOCK_BASELINE_DATASET["time_window_seconds"],
        per_hour=True,
    ) == 120.0

    # Urban Grid dataset: 150 veh in 3600s -> 150 veh/h
    assert throughput(
        MOCK_URBAN_GRID_DATASET["completed_vehicles"],
        MOCK_URBAN_GRID_DATASET["time_window_seconds"],
        per_hour=True,
    ) == 150.0

    # Safe zero / division by zero edge cases
    assert throughput(0, 3600.0) == 0.0
    assert throughput(10, 0.0) == 0.0
    assert throughput(10, -50.0) == 0.0
    assert throughput(None, 3600.0) == 0.0
    assert throughput([], 3600.0) == 0.0


def test_average_delay():
    """Test average delay calculation directly and from travel time comparisons."""
    # Direct delay list: [10.0, 20.0, 30.0] -> 20.0
    assert average_delay(delays=MOCK_KNOWN_DATASET["delays"]) == 20.0

    # From actual vs free-flow travel times:
    # actual=[50, 60, 70], free_flow=[40, 40, 40] -> delays=[10, 20, 30] -> avg 20.0
    assert average_delay(
        actual_travel_times=MOCK_KNOWN_DATASET["actual_travel_times"],
        free_flow_travel_times=MOCK_KNOWN_DATASET["free_flow_travel_times"],
    ) == 20.0

    # Baseline delays: sum=250, len=5 -> avg 50.0
    assert average_delay(delays=MOCK_BASELINE_DATASET["delays"]) == 50.0

    # Urban Grid delays: sum=125, len=5 -> avg 25.0
    assert average_delay(delays=MOCK_URBAN_GRID_DATASET["delays"]) == 25.0

    # Negative delay sanity check: vehicle faster than free-flow should clamp delay to 0.0
    assert average_delay(actual_travel_times=[35.0], free_flow_travel_times=[40.0]) == 0.0

    # Empty inputs
    assert average_delay(delays=MOCK_EMPTY_DATASET["delays"]) == 0.0
    assert average_delay(delays=[]) == 0.0
    assert average_delay(delays=None) == 0.0
    assert average_delay() == 0.0


def test_calculate_traffic_summary():
    """Test full summary aggregator on complete mock datasets."""
    summary = calculate_traffic_summary(MOCK_KNOWN_DATASET)
    assert summary["vehicle_count"] == 3.0
    assert summary["average_speed"] == 20.0
    assert summary["average_queue_length"] == 5.0
    assert summary["maximum_queue_length"] == 8.0
    assert summary["throughput"] == 1.0
    assert summary["average_delay"] == 20.0

    empty_summary = calculate_traffic_summary(MOCK_EMPTY_DATASET)
    for key, val in empty_summary.items():
        assert val == 0.0
