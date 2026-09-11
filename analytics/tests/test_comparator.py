"""Unit tests for baseline vs Urban Grid A/B comparator engine."""

from analytics.core.baseline_comparator import (
    MetricDirection,
    calculate_percentage_improvement,
    compare_metric,
    compare_runs,
    resolve_metric_direction,
)
from analytics.tests.mock_data import (
    MOCK_BASELINE_METRICS_SUMMARY,
    MOCK_URBAN_GRID_METRICS_SUMMARY,
)


def test_resolve_metric_direction():
    """Test automatic resolution and explicit overrides of metric directions."""
    # Automatic registry lookup: lower is better
    assert resolve_metric_direction("average_delay") == MetricDirection.LOWER_IS_BETTER
    assert resolve_metric_direction("average_queue_length") == MetricDirection.LOWER_IS_BETTER
    assert resolve_metric_direction("maximum_queue_length") == MetricDirection.LOWER_IS_BETTER
    assert resolve_metric_direction("waiting_time") == MetricDirection.LOWER_IS_BETTER

    # Automatic registry lookup: higher is better
    assert resolve_metric_direction("average_speed") == MetricDirection.HIGHER_IS_BETTER
    assert resolve_metric_direction("throughput") == MetricDirection.HIGHER_IS_BETTER

    # Neutral registry lookup: informational context metrics
    assert resolve_metric_direction("vehicle_count") == MetricDirection.NEUTRAL
    assert resolve_metric_direction("arrival_rate") == MetricDirection.NEUTRAL

    # Explicit overrides
    assert resolve_metric_direction("custom_metric", "lower_is_better") == MetricDirection.LOWER_IS_BETTER
    assert resolve_metric_direction("custom_metric", "higher_is_better") == MetricDirection.HIGHER_IS_BETTER
    assert resolve_metric_direction("custom_metric", "neutral") == MetricDirection.NEUTRAL


def test_neutral_metric_direction_and_behavior():
    """Verify NEUTRAL metrics behavior: delta preserved, no misleading pct, is_improved is None."""
    # Vehicle count: baseline 10 -> urban grid 15
    res_vc = compare_metric("vehicle_count", 10.0, 15.0)
    assert res_vc.direction == MetricDirection.NEUTRAL
    assert res_vc.baseline_value == 10.0
    assert res_vc.urban_grid_value == 15.0
    assert res_vc.delta == 5.0
    assert res_vc.percentage_improvement == 0.0  # Not misleadingly scored as +50% improvement
    assert res_vc.is_improved is None  # Not marked as KPI winner/loser

    # Arrival rate: baseline 4.5 -> urban grid 3.0
    res_ar = compare_metric("arrival_rate", 4.5, 3.0)
    assert res_ar.direction == MetricDirection.NEUTRAL
    assert res_ar.baseline_value == 4.5
    assert res_ar.urban_grid_value == 3.0
    assert res_ar.delta == -1.5
    assert res_ar.percentage_improvement == 0.0
    assert res_ar.is_improved is None

    # Serialization check
    d = res_vc.to_dict()
    assert d["direction"] == "neutral"
    assert d["is_improved"] is None
    assert d["percentage_improvement"] == 0.0


def test_correct_delta():
    """Test that delta is calculated as (urban_grid_value - baseline_value)."""
    # Speed: 13.0 -> 20.0 -> delta = +7.0
    res_speed = compare_metric("average_speed", 13.0, 20.0)
    assert res_speed.delta == 7.0

    # Delay: 50.0 -> 25.0 -> delta = -25.0
    res_delay = compare_metric("average_delay", 50.0, 25.0)
    assert res_delay.delta == -25.0

    # Queue length: 12.0 -> 4.0 -> delta = -8.0
    res_queue = compare_metric("average_queue_length", 12.0, 4.0)
    assert res_queue.delta == -8.0


def test_percentage_improvement_higher_is_better():
    """Test percentage improvement for higher-is-better metrics (e.g., speed, throughput)."""
    # Speed: baseline 20.0 -> urban grid 25.0: +25% improvement
    res_speed = compare_metric("average_speed", 20.0, 25.0)
    assert res_speed.percentage_improvement == 25.0
    assert res_speed.is_improved is True

    # Throughput: baseline 100 -> urban grid 150: +50% improvement
    res_thru = compare_metric("throughput", 100.0, 150.0)
    assert res_thru.percentage_improvement == 50.0
    assert res_thru.is_improved is True

    # Regression: speed decreased from 20.0 to 15.0: -25% degradation
    res_slower = compare_metric("average_speed", 20.0, 15.0)
    assert res_slower.percentage_improvement == -25.0
    assert res_slower.is_improved is False


def test_percentage_improvement_lower_is_better():
    """Test percentage improvement for lower-is-better metrics (e.g., delay, queue length)."""
    # Delay: baseline 50.0s -> urban grid 30.0s:
    # 20s reduced from 50s baseline = +40.0% improvement
    res_delay = compare_metric("average_delay", 50.0, 30.0)
    assert res_delay.percentage_improvement == 40.0
    assert res_delay.is_improved is True

    # Queue: baseline 10 -> urban grid 4:
    # 6 vehicles reduced from 10 baseline = +60.0% improvement
    res_queue = compare_metric("average_queue_length", 10.0, 4.0)
    assert res_queue.percentage_improvement == 60.0
    assert res_queue.is_improved is True

    # Regression: delay increased from 50.0s to 60.0s:
    # 10s worse = -20.0% degradation
    res_worse = compare_metric("average_delay", 50.0, 60.0)
    assert res_worse.percentage_improvement == -20.0
    assert res_worse.is_improved is False


def test_zero_baseline_handling():
    """Test safe handling when baseline is 0.0 to avoid division by zero."""
    # Both zero: 0.0% change, delta 0.0
    res_zero_both = compare_metric("average_delay", 0.0, 0.0)
    assert res_zero_both.delta == 0.0
    assert res_zero_both.percentage_improvement == 0.0
    assert res_zero_both.is_improved is False

    # Baseline 0.0, Urban Grid > 0 for higher-is-better
    res_speed_zero_base = compare_metric("average_speed", 0.0, 20.0)
    assert res_speed_zero_base.delta == 20.0
    assert res_speed_zero_base.percentage_improvement == 0.0
    assert res_speed_zero_base.is_improved is True

    # Baseline 0.0, Urban Grid > 0 for lower-is-better
    res_delay_zero_base = compare_metric("average_delay", 0.0, 15.0)
    assert res_delay_zero_base.delta == 15.0
    assert res_delay_zero_base.percentage_improvement == 0.0
    assert res_delay_zero_base.is_improved is False


def test_identical_baseline_and_urban_grid():
    """Test behavior when baseline and Urban Grid metrics are identical."""
    res_same = compare_metric("average_speed", 42.5, 42.5)
    assert res_same.delta == 0.0
    assert res_same.percentage_improvement == 0.0
    assert res_same.is_improved is False

    res_same_delay = compare_metric("average_delay", 30.0, 30.0)
    assert res_same_delay.delta == 0.0
    assert res_same_delay.percentage_improvement == 0.0
    assert res_same_delay.is_improved is False


def test_compare_runs_mock_datasets():
    """Test full multi-metric run comparison using mock baseline and urban grid data."""
    comparison = compare_runs(
        MOCK_BASELINE_METRICS_SUMMARY,
        MOCK_URBAN_GRID_METRICS_SUMMARY,
    )

    # All expected metrics present
    assert "average_speed" in comparison
    assert "average_delay" in comparison
    assert "average_queue_length" in comparison
    assert "maximum_queue_length" in comparison
    assert "throughput" in comparison

    # Speed: 13.0 -> 20.0: +53.85% improvement
    speed_comp = comparison["average_speed"]
    assert speed_comp.delta == 7.0
    assert speed_comp.percentage_improvement == 53.85
    assert speed_comp.is_improved is True

    # Delay: 50.0 -> 25.0: +50.0% improvement (delay cut in half)
    delay_comp = comparison["average_delay"]
    assert delay_comp.delta == -25.0
    assert delay_comp.percentage_improvement == 50.0
    assert delay_comp.is_improved is True

    # Queue length: 12.0 -> 4.0: +66.67% improvement
    queue_comp = comparison["average_queue_length"]
    assert queue_comp.delta == -8.0
    assert queue_comp.percentage_improvement == 66.67
    assert queue_comp.is_improved is True

    # to_dict verification
    d = delay_comp.to_dict()
    assert d["metric_name"] == "average_delay"
    assert d["direction"] == "lower_is_better"
    assert isinstance(d["delta"], float)
