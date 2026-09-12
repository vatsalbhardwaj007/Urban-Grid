"""M1 -> M2 contract adapter for Decision Engine actions.

Converts the local M1 :class:`ai.decision.engine.Action` into M2's canonical
shared action contracts (``shared.schemas.SignalAction`` / ``RouteAction``).
This is a thin adapter only: all field semantics and validation live in the
shared Pydantic models, which are used directly and never duplicated here.

Conversion rules:

* ``SIGNAL`` -> ``SignalAction``; ``parameters["recommended_green_seconds"]``
  becomes ``green_duration`` and the local ``target`` is passed through.
* ``ROUTE`` -> ``RouteAction``; ``parameters["path"]`` becomes ``route`` and
  the canonical ``target`` (a SUMO vehicle id) must be supplied explicitly by
  the integration caller, since the local engine target is the routing
  destination, not a vehicle.
* ``NO_ACTION`` is an internal result and maps to ``None``.

The shared contracts require an ISO wall-clock ``datetime`` while the Decision
Engine/``TrafficState`` currently carry numeric SUMO-style timestamps. The
adapter therefore never fabricates a wall-clock time: the integration caller
must supply the ``datetime`` explicitly. No vehicle id, timestamp, or SUMO
data is invented here.
"""

from __future__ import annotations

from datetime import datetime

from ai.decision.engine import DEFAULT_ACTION_SOURCE, Action, ActionKind
from shared.schemas.route_action import RouteAction
from shared.schemas.signal_action import ActionSource, SignalAction

_SOURCE_MAP: dict[str, ActionSource] = {
    DEFAULT_ACTION_SOURCE: ActionSource.AI,
}


def convert(
    action: Action,
    *,
    timestamp: datetime | None = None,
    vehicle_id: str | None = None,
) -> SignalAction | RouteAction | None:
    """Convert a local Decision Engine ``action`` to a shared contract.

    ``timestamp`` (a ``datetime``) is required for SIGNAL and ROUTE actions;
    it must be supplied by the integration caller. ``vehicle_id`` is required
    for ROUTE actions. ``NO_ACTION`` returns ``None`` and requires neither.
    Unknown local sources and action types are rejected rather than guessed.
    """
    if not isinstance(action, Action):
        raise TypeError("action must be an ai.decision.engine.Action")

    if action.type is ActionKind.NO_ACTION:
        return None
    if action.type is ActionKind.SIGNAL:
        return _to_signal_action(action, _require_timestamp(timestamp))
    if action.type is ActionKind.ROUTE:
        return _to_route_action(action, _require_timestamp(timestamp), vehicle_id)
    raise ValueError(f"unsupported action type: {action.type!r}")


def _to_signal_action(action: Action, timestamp: datetime) -> SignalAction:
    green_duration = _require_parameter(action, "recommended_green_seconds")
    source = _map_source(action.source)
    return SignalAction(
        target=action.target,
        green_duration=green_duration,
        source=source,
        timestamp=timestamp,
    )


def _to_route_action(action: Action, timestamp: datetime, vehicle_id: str | None) -> RouteAction:
    if vehicle_id is None:
        raise ValueError(
            "vehicle_id is required to convert a ROUTE action to RouteAction; "
            "the local action target is the routing destination, not a SUMO vehicle"
        )
    path = _require_parameter(action, "path")
    source = _map_source(action.source)
    return RouteAction(
        target=vehicle_id,
        route=path,
        source=source,
        timestamp=timestamp,
    )


def _require_parameter(action: Action, name: str):
    parameters = action.parameters
    if not isinstance(parameters, dict) or name not in parameters:
        raise ValueError(f"action is missing required parameter {name!r}")
    return parameters[name]


def _require_timestamp(timestamp: datetime | None) -> datetime:
    if not isinstance(timestamp, datetime):
        raise ValueError(
            "timestamp (a datetime) is required for shared action conversion; "
            "the numeric simulation timestamp cannot be converted without "
            "explicit wall-clock runtime context"
        )
    return timestamp


def _map_source(source: str) -> ActionSource:
    try:
        return _SOURCE_MAP[source]
    except KeyError:
        raise ValueError(
            f"unknown M1 action source {source!r}; no canonical ActionSource mapping exists"
        ) from None
