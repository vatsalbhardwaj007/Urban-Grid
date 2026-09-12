import math

import pytest

from ai.routing.cost import future_edge_cost


def test_free_flow_only_cost():
    assert future_edge_cost(5.0) == 5.0
    assert future_edge_cost(0.0) == 0.0


def test_queue_delay_contribution():
    assert future_edge_cost(5.0, queue_delay=2.0) == 7.0


def test_signal_delay_contribution():
    assert future_edge_cost(5.0, signal_delay=3.0) == 8.0


def test_congestion_penalty_contribution():
    assert future_edge_cost(5.0, congestion_penalty=4.0) == 9.0


def test_all_components_accumulate():
    cost = future_edge_cost(
        free_flow_time=5.0,
        queue_delay=2.0,
        signal_delay=3.0,
        congestion_penalty=4.0,
    )
    assert cost == 14.0


def test_configurable_weights():
    assert future_edge_cost(5.0, queue_delay=10.0, queue_delay_weight=0.0) == 5.0
    assert future_edge_cost(5.0, signal_delay=2.0, signal_delay_weight=2.0) == 9.0
    assert future_edge_cost(
        5.0, congestion_penalty=3.0, congestion_penalty_weight=0.5
    ) == 6.5
    assert future_edge_cost(5.0, free_flow_weight=2.0) == 10.0


def test_free_flow_time_is_base_cost():
    base = future_edge_cost(5.0)
    assert base == 5.0
    weighted = future_edge_cost(5.0, queue_delay=10.0, congestion_penalty=10.0)
    assert weighted >= base


@pytest.mark.parametrize("name", ["free_flow_time", "queue_delay", "signal_delay", "congestion_penalty"])
@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), float("-inf"), "abc", True, None])
def test_invalid_component_values_rejected(name, bad):
    kwargs = {name: bad}
    if name == "free_flow_time":
        with pytest.raises(ValueError):
            future_edge_cost(bad)
    else:
        with pytest.raises(ValueError):
            future_edge_cost(5.0, **kwargs)


@pytest.mark.parametrize(
    "name", ["free_flow_weight", "queue_delay_weight", "signal_delay_weight", "congestion_penalty_weight"]
)
@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), float("-inf"), "abc", True])
def test_invalid_weights_rejected(name, bad):
    kwargs = {name: bad}
    with pytest.raises(ValueError):
        future_edge_cost(5.0, queue_delay=1.0, **kwargs)


def test_result_is_finite_and_non_negative_for_valid_inputs():
    result = future_edge_cost(
        free_flow_time=1.5,
        queue_delay=0.25,
        signal_delay=0.0,
        congestion_penalty=0.75,
        queue_delay_weight=2.0,
    )
    assert isinstance(result, float)
    assert 0.0 <= result
    assert math.isfinite(result)