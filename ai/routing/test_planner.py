import copy
import math

import pytest

from ai.routing.cost import future_edge_cost
from ai.routing.graph import Edge, RoadNetwork, build_graph
from ai.routing.planner import RoutePlanner, RouteResult


def _edge(edge_id, from_node, to_node, free_flow_time=5.0, capacity=100):
    return Edge(edge_id, from_node, to_node, free_flow_time, capacity)


def _free_flow_network():
    return build_graph(
        [
            _edge("ab", "A", "B", 10.0),
            _edge("ac", "A", "C", 2.0),
            _edge("cb", "C", "B", 3.0),
        ]
    )


def _future_cost_network():
    return build_graph(
        [
            _edge("ax", "A", "X", 1.0),
            _edge("xb", "X", "B", 1.0),
            _edge("ay", "A", "Y", 5.0),
            _edge("yb", "Y", "B", 5.0),
            _edge("bd", "B", "D", 1.0),
        ]
    )


def test_shortest_route_selection():
    planner = RoutePlanner(_free_flow_network())
    result = planner.plan("A", "B")
    assert result.path == ("A", "C", "B")
    assert result.total_cost == 5.0
    assert result.reachable is True


def test_free_flow_only_cost_when_no_cost_fn():
    planner = RoutePlanner(_free_flow_network())
    result = planner.plan("A", "B")
    assert result.total_cost == pytest.approx(5.0)
    assert result.path == ("A", "C", "B")


def test_route_changes_when_future_congestion_changes_costs():
    network = _future_cost_network()
    planner = RoutePlanner(network)

    def courtney_congested_cost(u, v, data):
        if (u, v) == ("A", "X"):
            return future_edge_cost(data["free_flow_time"], congestion_penalty=200.0)
        return data["free_flow_time"]

    free = planner.plan("A", "B")
    assert free.path == ("A", "X", "B")

    future = planner.plan("A", "B", cost_fn=courtney_congested_cost)
    assert future.path == ("A", "Y", "B")
    assert future.total_cost == pytest.approx(10.0)


def test_unreachable_destination_handled_cleanly():
    network = _future_cost_network()
    network.add_node("ORPHAN")
    planner = RoutePlanner(network)
    result = planner.plan("A", "ORPHAN")
    assert result.reachable is False
    assert result.path == ()
    assert result.total_cost == math.inf


def test_invalid_source_or_destination_rejected():
    planner = RoutePlanner(_free_flow_network())
    with pytest.raises(ValueError):
        planner.plan("MISSING", "B")
    with pytest.raises(ValueError):
        planner.plan("A", "MISSING")
    with pytest.raises(ValueError):
        planner.plan(123, "B")
    with pytest.raises(ValueError):
        planner.plan(None, "B")


def test_source_equals_destination():
    planner = RoutePlanner(_free_flow_network())
    result = planner.plan("B", "B")
    assert result.path == ("B",)
    assert result.total_cost == 0.0
    assert result.reachable is True


def test_deterministic_repeated_planning():
    planner = RoutePlanner(_future_cost_network())

    def noisy_cost(u, v, data):
        return data["free_flow_time"] + (100.0 if (u, v) == ("A", "X") else 0.0)

    first = planner.plan("A", "B", cost_fn=noisy_cost)
    second = planner.plan("A", "B", cost_fn=noisy_cost)
    assert first == second


def test_planning_does_not_modify_graph():
    planner = RoutePlanner(_future_cost_network())
    before = [(e.edge_id, e.free_flow_time, e.capacity) for e in planner._graph.edges()]
    snapshot = copy.deepcopy(before)

    def cost(u, v, data):
        return future_edge_cost(data["free_flow_time"], congestion_penalty=50.0)

    planner.plan("A", "D", cost_fn=cost)
    planner.plan("X", "D", cost_fn=cost)
    after = [(e.edge_id, e.free_flow_time, e.capacity) for e in planner._graph.edges()]
    assert after == snapshot


def test_diversion_cap_prevents_excessive_rerouting():
    network = _future_cost_network()
    planner = RoutePlanner(network)

    def congested_cost(u, v, data):
        if (u, v) == ("A", "X"):
            return data["free_flow_time"] + 100.0
        return data["free_flow_time"]

    baseline = planner.plan("A", "B")
    assert baseline.total_cost == 2.0

    with_cap_zero = planner.plan("A", "B", cost_fn=congested_cost, diversion_cap=0.0)
    assert with_cap_zero.path == baseline.path
    assert with_cap_zero.total_cost == 2.0

    with_mid_cap = planner.plan("A", "B", cost_fn=congested_cost, diversion_cap=5.0)
    assert with_mid_cap.path == baseline.path

    with_big_cap = planner.plan("A", "B", cost_fn=congested_cost, diversion_cap=200.0)
    assert with_big_cap.path == ("A", "Y", "B")
    assert with_big_cap.total_cost == 10.0


def test_future_route_is_never_cheaper_than_free_flow_baseline():
    network = _future_cost_network()
    planner = RoutePlanner(network)

    def varying_cost(u, v, data):
        if (u, v) == ("A", "X"):
            return data["free_flow_time"] + 100.0
        return data["free_flow_time"]

    baseline = planner.plan("A", "B")
    future = planner.plan("A", "B", cost_fn=varying_cost, diversion_cap=None)
    assert future.total_cost >= baseline.total_cost
    assert baseline.reachable is True


def test_invalid_diversion_cap_rejected():
    planner = RoutePlanner(_free_flow_network())
    with pytest.raises(ValueError):
        planner.plan("A", "B", diversion_cap=-1.0)
    with pytest.raises(ValueError):
        planner.plan("A", "B", diversion_cap=float("nan"))
    with pytest.raises(ValueError):
        planner.plan("A", "B", diversion_cap=float("inf"))


def test_invalid_edge_cost_from_cost_fn_rejected():
    planner = RoutePlanner(_free_flow_network())

    def negative_cost(u, v, data):
        return -1.0

    with pytest.raises(ValueError):
        planner.plan("A", "B", cost_fn=negative_cost)

    def nan_cost(u, v, data):
        return float("nan")

    with pytest.raises(ValueError):
        planner.plan("A", "B", cost_fn=nan_cost)


def test_result_return_type():
    planner = RoutePlanner(_free_flow_network())
    result = planner.plan("A", "B")
    assert isinstance(result, RouteResult)
    assert isinstance(result.path, tuple)
    assert isinstance(result.total_cost, float)