"""Route planning over the M1 road network using edge costs.

Dijkstra shortest-path planning over the directed :class:`RoadNetwork` with a
caller-supplied (deterministic) edge cost function. Baselines (e.g. free-flow
cost) can be used together with a diversion cap so the planner avoids
excessive rerouting. Planning never mutates the graph.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import networkx as nx

from ai.routing.graph import RoadNetwork

DEFAULT_UNREACHABLE_COST = math.inf


@dataclass(frozen=True)
class RouteResult:
    path: tuple[str, ...]
    total_cost: float
    reachable: bool = True


class RoutePlanner:
    """Plans least-cost routes on the given road network.

    ``cost_fn(u, v, edge_data) -> float`` is a deterministic function of an
    edge; when omitted, free-flow time is used as the cost. The planner never
    mutates the graph.
    """

    def __init__(self, graph: RoadNetwork) -> None:
        if not isinstance(graph, RoadNetwork):
            raise TypeError("graph must be a RoadNetwork")
        self._graph = graph

    def plan(
        self,
        source: str,
        destination: str,
        *,
        cost_fn: Callable[[str, str, dict], float] | None = None,
        diversion_cap: float | None = None,
    ) -> RouteResult:
        """Return the least-cost route from ``source`` to ``destination``.

        ``diversion_cap``, when given a finite non-negative number, is the
        maximum extra cost (over the free-flow baseline route) the planner
        will accept before falling back to the baseline route, preventing
        excessive rerouting. If ``source`` or ``destination`` is not a node,
        a ``ValueError`` is raised; an unreachable destination yields a
        ``RouteResult`` with ``reachable=False``.
        """
        if not isinstance(source, str) or not isinstance(destination, str):
            raise ValueError("source and destination must be node ids (strings)")
        if not self._graph.has_node(source) or not self._graph.has_node(destination):
            raise ValueError(f"source {source!r} and/or destination {destination!r} is not a node")
        if diversion_cap is not None:
            _require_non_negative_finite(diversion_cap, "diversion_cap")

        if source == destination:
            return RouteResult(path=(source,), total_cost=0.0, reachable=True)

        baseline = self._shortest_cost(source, destination, self._free_flow_cost)
        if not baseline.reachable:
            return RouteResult(path=(), total_cost=DEFAULT_UNREACHABLE_COST, reachable=False)

        selected = baseline
        if cost_fn is not None:
            future = self._shortest_cost(source, destination, _validated(cost_fn))
            if future.reachable:
                cap = diversion_cap if diversion_cap is not None else math.inf
                if future.total_cost <= baseline.total_cost + cap:
                    selected = future
        return selected

    def shortest_future_route(
        self,
        source: str,
        destination: str,
        *,
        cost_fn: Callable[[str, str, dict], float],
    ) -> RouteResult:
        """Convenience wrapper for future-cost planning without a baseline cap."""
        return self.plan(source, destination, cost_fn=cost_fn)

    def _shortest_cost(
        self,
        source: str,
        destination: str,
        weight: Callable[[str, str, dict], float],
    ) -> RouteResult:
        try:
            path = nx.shortest_path(
                self._graph.network(),
                source,
                destination,
                weight=weight,
                method="dijkstra",
            )
        except nx.NetworkXNoPath:
            return RouteResult(path=(), total_cost=DEFAULT_UNREACHABLE_COST, reachable=False)
        cost = _path_cost(self._graph, tuple(path), weight)
        return RouteResult(path=tuple(path), total_cost=cost, reachable=True)

    @staticmethod
    def _free_flow_cost(_u: str, _v: str, edge_data: dict) -> float:
        return float(edge_data["free_flow_time"])


def _validated(
    cost_fn: Callable[[str, str, dict], float],
) -> Callable[[str, str, dict], float]:
    def _weighted(u: str, v: str, edge_data: dict) -> float:
        value = cost_fn(u, v, edge_data)
        _require_non_negative_finite(value, "edge cost")
        return value

    return _weighted


def _path_cost(
    graph: RoadNetwork,
    path: tuple[str, ...],
    weight: Callable[[str, str, dict], float],
) -> float:
    edges = graph.network().edges
    total = 0.0
    for u, v in zip(path, path[1:]):
        total += weight(u, v, edges[(u, v)])
    return float(total)


def _require_non_negative_finite(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")