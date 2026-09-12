import math

import pytest

from ai.routing.graph import Edge, RoadNetwork, build_graph


def _edge(edge_id="e1", from_node="A", to_node="B", free_flow_time=5.0, capacity=100):
    return Edge(
        edge_id=edge_id,
        from_node=from_node,
        to_node=to_node,
        free_flow_time=free_flow_time,
        capacity=capacity,
    )


def test_graph_creation_and_build():
    network = build_graph([_edge(), _edge("e2", "B", "C")])
    assert isinstance(network, RoadNetwork)
    assert sorted(network.nodes()) == ["A", "B", "C"]
    assert len(list(network.edges())) == 2


def test_directed_edges():
    network = RoadNetwork()
    network.add_edge(_edge("e1", "A", "B"))
    assert network.has_edge("e1")
    assert network.network().has_edge("A", "B")
    assert not network.network().has_edge("B", "A")
    assert sorted(network.nodes()) == ["A", "B"]


def test_add_node_and_edges_autocreate_nodes():
    network = RoadNetwork()
    network.add_node("A")
    network.add_edge(_edge("e1", "A", "B"))
    assert network.has_node("A")
    assert network.has_node("B")


def test_retrieve_edge():
    network = build_graph([_edge(free_flow_time=6.0, capacity=200)])
    edge = network.edge("e1")
    assert edge == Edge("e1", "A", "B", 6.0, 200)
    assert network.get_edge("missing") is None
    with pytest.raises(KeyError):
        network.edge("missing")


def test_edge_id_uniqueness_enforced():
    with pytest.raises(ValueError, match="already exists"):
        build_graph([_edge("e1", "A", "B"), _edge("e1", "B", "C")])


def test_duplicate_endpoint_pair_rejected():
    with pytest.raises(ValueError, match="already exists"):
        build_graph([_edge("e1", "A", "B"), _edge("e2", "A", "B")])


def test_self_loop_rejected():
    with pytest.raises(ValueError, match="distinct"):
        build_graph([_edge("e1", "A", "A")])


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), float("-inf"), "abc", True])
def test_invalid_free_flow_time_rejected(bad):
    with pytest.raises(ValueError):
        build_graph([_edge(free_flow_time=bad)])


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), float("-inf"), "abc", True])
def test_invalid_capacity_rejected(bad):
    with pytest.raises(ValueError):
        build_graph([_edge(capacity=bad)])


def test_invalid_edge_metadata_rejected():
    with pytest.raises(ValueError):
        build_graph([_edge(edge_id="")])
    with pytest.raises(ValueError):
        build_graph([_edge(edge_id="  ")])
    with pytest.raises(TypeError):
        build_graph([object()])


def test_graph_edge_retrieval_via_edges_iteration():
    network = build_graph([_edge("e1", "A", "B", 3.0, 50), _edge("e2", "B", "C", 4.0, 60)])
    returned = {edge.edge_id: edge for edge in network.edges()}
    assert returned["e1"].free_flow_time == 3.0
    assert returned["e1"].capacity == 50
    assert returned["e2"].to_node == "C"


def test_validate_passes_and_never_mutates():
    edges = [_edge("e1", "A", "B", 3.0, 50), _edge("e2", "B", "A", 3.5, 40)]
    network = build_graph(edges)
    network.validate()
    assert network.edge("e1").free_flow_time == 3.0

    double = build_graph(edges)
    snapshot = [(e.edge_id, e.free_flow_time, e.capacity) for e in double.edges()]
    double.validate()
    assert [(e.edge_id, e.free_flow_time, e.capacity) for e in double.edges()] == snapshot


def test_get_edge_and_has_edge_edge_cases():
    network = build_graph([_edge()])
    assert network.edge("e1").from_node == "A"
    assert not network.has_edge("missing")