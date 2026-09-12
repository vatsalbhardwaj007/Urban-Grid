"""Tests for the M1 -> M2 contract adapter (ai.decision.adapter)."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pydantic
import pytest

from ai.decision.adapter import convert, _SOURCE_MAP
from ai.decision.engine import DEFAULT_ACTION_SOURCE, Action, ActionKind
from shared.schemas.route_action import RouteAction
from shared.schemas.signal_action import ActionSource, SignalAction

TS = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)


def _signal_action(target: str = "INT-001", green: float = 15.0) -> Action:
    return Action(
        type=ActionKind.SIGNAL,
        target=target,
        parameters={"recommended_green_seconds": green},
        source=DEFAULT_ACTION_SOURCE,
        timestamp=12345.0,
    )


def _route_action(target: str = "DEST-B", path=("A", "Y", "B")) -> Action:
    return Action(
        type=ActionKind.ROUTE,
        target=target,
        parameters={"path": list(path), "total_cost": 10.0},
        source=DEFAULT_ACTION_SOURCE,
        timestamp=12345.0,
    )


def _no_action() -> Action:
    return Action(
        type=ActionKind.NO_ACTION,
        target="",
        parameters={},
        source=DEFAULT_ACTION_SOURCE,
        timestamp=12345.0,
    )


# --- SIGNAL conversion ---


def test_signal_action_converts_to_valid_signal_action():
    result = convert(_signal_action(), timestamp=TS)
    assert isinstance(result, SignalAction)


def test_signal_green_duration_copied():
    result = convert(_signal_action(green=22.5), timestamp=TS)
    assert result.green_duration == 22.5


def test_signal_target_copied():
    result = convert(_signal_action(target="INT-042"), timestamp=TS)
    assert result.target == "INT-042"


def test_signal_source_maps_to_ai():
    result = convert(_signal_action(), timestamp=TS)
    assert result.source == ActionSource.AI


def test_signal_requires_explicit_datetime():
    with pytest.raises(ValueError, match="timestamp"):
        convert(_signal_action())


def test_signal_source_map_contains_m1_decision_engine():
    assert _SOURCE_MAP[DEFAULT_ACTION_SOURCE] == ActionSource.AI


# --- ROUTE conversion ---


def test_route_action_converts_to_valid_route_action_with_vehicle_id():
    result = convert(_route_action(), timestamp=TS, vehicle_id="veh_7")
    assert isinstance(result, RouteAction)


def test_route_path_becomes_route():
    result = convert(_route_action(path=("A", "Y", "B")), timestamp=TS, vehicle_id="veh_7")
    assert result.route == ["A", "Y", "B"]


def test_route_uses_supplied_vehicle_id_not_action_target():
    result = convert(_route_action(target="DEST-B"), timestamp=TS, vehicle_id="veh_7")
    assert result.target == "veh_7"
    assert result.target != "DEST-B"


def test_route_without_vehicle_id_fails_clearly():
    with pytest.raises(ValueError, match="vehicle_id"):
        convert(_route_action(), timestamp=TS)


def test_route_source_maps_to_ai():
    result = convert(_route_action(), timestamp=TS, vehicle_id="veh_7")
    assert result.source == ActionSource.AI


# --- NO_ACTION ---


def test_no_action_converts_to_none():
    assert convert(_no_action(), timestamp=TS) is None


def test_no_action_returns_none_without_timestamp():
    assert convert(_no_action()) is None


# --- Validation / shared Pydantic exercised ---


def test_missing_signal_green_duration_rejected():
    action = _signal_action()
    action = Action(
        type=ActionKind.SIGNAL,
        target=action.target,
        parameters={"score": 0.5},
        source=action.source,
        timestamp=action.timestamp,
    )
    with pytest.raises(ValueError, match="recommended_green_seconds"):
        convert(action, timestamp=TS)


def test_invalid_signal_green_duration_rejected_by_pydantic():
    with pytest.raises(pydantic.ValidationError):
        convert(_signal_action(green=float("nan")), timestamp=TS)
    with pytest.raises(pydantic.ValidationError):
        convert(_signal_action(green=-1.0), timestamp=TS)


def test_missing_route_path_rejected():
    action = _route_action()
    action = Action(
        type=ActionKind.ROUTE,
        target=action.target,
        parameters={"total_cost": 10.0},
        source=action.source,
        timestamp=action.timestamp,
    )
    with pytest.raises(ValueError, match="path"):
        convert(action, timestamp=TS, vehicle_id="veh_7")


def test_invalid_route_path_rejected_by_pydantic():
    with pytest.raises(pydantic.ValidationError):
        convert(_route_action(path=()), timestamp=TS, vehicle_id="veh_7")
    with pytest.raises(pydantic.ValidationError):
        convert(_route_action(path=("e1", "")), timestamp=TS, vehicle_id="veh_7")


def test_empty_signal_target_rejected_by_pydantic():
    with pytest.raises(pydantic.ValidationError):
        convert(_signal_action(target="  "), timestamp=TS)


def test_empty_vehicle_id_rejected_by_pydantic():
    with pytest.raises(pydantic.ValidationError):
        convert(_route_action(), timestamp=TS, vehicle_id="")


def test_numeric_timestamp_rejected_instead_of_fabricated():
    with pytest.raises(ValueError, match="datetime"):
        convert(_signal_action(), timestamp=12345.0)


# --- Timestamp handling ---


def test_timestamp_passed_through_as_datetime():
    result = convert(_signal_action(), timestamp=TS)
    assert result.timestamp == TS
    assert isinstance(result.timestamp, datetime)


def test_route_timestamp_passed_through_as_datetime():
    result = convert(_route_action(), timestamp=TS, vehicle_id="veh_7")
    assert result.timestamp == TS
    assert isinstance(result.timestamp, datetime)


# --- Source mapping ---


def test_unknown_source_rejected():
    action = _signal_action()
    action = Action(
        type=ActionKind.SIGNAL,
        target=action.target,
        parameters=action.parameters,
        source="m1-unknown-source",
        timestamp=action.timestamp,
    )
    with pytest.raises(ValueError, match="source"):
        convert(action, timestamp=TS)


# --- Type handling ---


def test_non_action_input_rejected():
    with pytest.raises(TypeError):
        convert({"type": "SIGNAL"})  # type: ignore[arg-type]


def test_unsupported_action_type_rejected():
    action = _signal_action()
    weird = Action(
        type="definitely-not-an-action-kind",  # type: ignore[arg-type]
        target=action.target,
        parameters=action.parameters,
        source=action.source,
        timestamp=action.timestamp,
    )
    with pytest.raises(ValueError, match="unsupported action type"):
        convert(weird, timestamp=TS)


# --- Immutability of the input ---


def test_adapter_does_not_mutate_original_action():
    signal = _signal_action()
    signal_snapshot = copy.deepcopy(signal)
    route = _route_action()
    route_snapshot = copy.deepcopy(route)
    no_action = _no_action()
    no_action_snapshot = copy.deepcopy(no_action)

    convert(signal, timestamp=TS)
    convert(route, timestamp=TS, vehicle_id="veh_7")
    convert(no_action, timestamp=TS)

    assert signal == signal_snapshot
    assert dict(signal.parameters) == dict(signal_snapshot.parameters)
    assert route == route_snapshot
    assert dict(route.parameters) == dict(route_snapshot.parameters)
    assert no_action == no_action_snapshot


def test_repeated_conversion_is_deterministic_and_non_mutating():
    signal = _signal_action()
    first = convert(signal, timestamp=TS)
    second = convert(signal, timestamp=TS)
    assert first == second
    assert first is not second
