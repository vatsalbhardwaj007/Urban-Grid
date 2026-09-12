"""Directed weighted road-network graph for M1 routing.

The road network is modelled as a directed graph: intersections are nodes and
road segments are directed edges (one per travel direction). The layer is
independent of SUMO/TraCI and stores only the structural and capacity data a
planner needs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Iterator

import networkx as nx

MIN_FREE_FLOW_TIME = 0.0
MIN_CAPACITY = 0.0


@dataclass(frozen=True)
class Edge:
    edge_id: str
    from_node: str
    to_node: str
    free_flow_time: float
    capacity: float


class RoadNetwork:
    """A directed road network with edges keyed by ``edge_id``.

    Nodes are auto-created when edges reference them. Edges must be unique by
    ``edge_id`` and by ``(from_node, to_node)``; every edge must reference two
    distinct, well-formed node ids and carry finite, non-negative
    ``free_flow_time`` and ``capacity``. The network is a plain weighted
    digraph (no SUMO-specific semantics).
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    def add_node(self, node_id: str) -> None:
        """Add a node (intersection); a no-op if it already exists."""
        _require_node_id(node_id)
        self._graph.add_node(node_id)

    def add_edge(self, edge: Edge) -> None:
        """Add a directed edge (road segment) with full validation."""
        _validate_edge(edge)
        if self.has_edge(edge.edge_id):
            raise ValueError(f"edge_id {edge.edge_id!r} already exists")
        if self._graph.has_edge(edge.from_node, edge.to_node):
            raise ValueError(
                f"edge already exists between {edge.from_node!r} and {edge.to_node!r}"
            )
        self._graph.add_edge(
            edge.from_node,
            edge.to_node,
            edge_id=edge.edge_id,
            free_flow_time=edge.free_flow_time,
            capacity=edge.capacity,
        )

    def edge(self, edge_id: str) -> Edge:
        """Return the edge with ``edge_id``; raises KeyError if absent."""
        u, v = self._edge_lookup(edge_id)
        data = self._graph.edges[(u, v)]
        return Edge(
            edge_id=edge_id,
            from_node=u,
            to_node=v,
            free_flow_time=data["free_flow_time"],
            capacity=data["capacity"],
        )

    def get_edge(self, edge_id: str, default=None) -> Edge | None:
        """Return the edge with ``edge_id`` or ``default`` if absent."""
        try:
            return self.edge(edge_id)
        except KeyError:
            return default

    def edges(self) -> Iterator[Edge]:
        """Iterate over all edges in insertion order."""
        for u, v, data in self._graph.edges(data=True):
            yield Edge(
                edge_id=data["edge_id"],
                from_node=u,
                to_node=v,
                free_flow_time=data["free_flow_time"],
                capacity=data["capacity"],
            )

    def nodes(self) -> list[str]:
        return list(self._graph.nodes)

    def has_node(self, node_id: str) -> bool:
        return self._graph.has_node(node_id)

    def has_edge(self, edge_id: str) -> bool:
        return edge_id in self._edge_ids()

    def network(self) -> nx.DiGraph:
        """Return the underlying NetworkX digraph (read-only by convention)."""
        return self._graph

    def validate(self) -> None:
        """Re-validate structural integrity and raise on malformed topology."""
        seen_ids: dict[tuple[str, str], str] = {}
        for edge in self.edges():
            _validate_edge(edge)
            if not self._graph.has_edge(edge.from_node, edge.to_node):
                raise ValueError(f"edge {edge.edge_id!r} endpoint pair is missing from graph")
            pair = (edge.from_node, edge.to_node)
            if pair in seen_ids:
                raise ValueError(
                    f"duplicate edge {edge.edge_id!r} for endpoints {pair!r}"
                )
            seen_ids[pair] = edge.edge_id
            data = self._graph.edges[pair]
            if data.get("edge_id") != edge.edge_id:
                raise ValueError(f"edge {edge.edge_id!r} is inconsistent with graph data")

    def _edge_lookup(self, edge_id: str) -> tuple[str, str]:
        for u, v, data in self._graph.edges(data=True):
            if data["edge_id"] == edge_id:
                return u, v
        raise KeyError(edge_id)

    def _edge_ids(self) -> set[str]:
        return {data["edge_id"] for _, _, data in self._graph.edges(data=True)}


def build_graph(edges: Iterable[Edge]) -> RoadNetwork:
    """Build and validate a :class:`RoadNetwork` from an iterable of edges."""
    network = RoadNetwork()
    for edge in edges:
        network.add_edge(edge)
    network.validate()
    return network


def _require_node_id(node_id) -> None:
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValueError("node id must be a non-empty string")


def _validate_edge(edge) -> None:
    if not isinstance(edge, Edge):
        raise TypeError("edge must be an Edge")
    if not isinstance(edge.edge_id, str) or not edge.edge_id.strip():
        raise ValueError("edge.edge_id must be a non-empty string")
    _require_node_id(edge.from_node)
    _require_node_id(edge.to_node)
    if edge.from_node == edge.to_node:
        raise ValueError(f"edge {edge.edge_id!r} must connect two distinct nodes")
    _require_non_negative_finite(edge.free_flow_time, "free_flow_time", edge.edge_id)
    _require_non_negative_finite(edge.capacity, "capacity", edge.edge_id)


def _require_non_negative_finite(value, field: str, edge_id: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"edge {edge_id!r} field '{field}' must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"edge {edge_id!r} field '{field}' must be finite")
    if value < 0:
        raise ValueError(f"edge {edge_id!r} field '{field}' must be >= 0")