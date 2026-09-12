import copy
import math

import pytest

from ai.decision.engine import (
    DEFAULT_ACTION_SOURCE,
    Action,
    ActionKind,
    DecisionConfig,
    RoutingContext,
    SignalContext,
    decide,
)
from ai.prediction.predict import HIGH_SEVERITY, LOW_SEVERITY, MEDIUM_SEVERITY, PredictionResult
from ai.routing.graph import Edge, build_graph
from ai.routing.planner import RoutePlanner
from ai.signals.optimizer import recommended_green
from ai.signals.policy import signal_pressure_score


def _state(timestamp=1700000000.0, **overrides):
    state = {
        "timestamp": timestamp,
        "intersection_id": "INT-001",
        "lane_features": [],
        "total_queue": 4,
        "mean_speed": 25.0,
        "arrival_rate": 3.0,
        "density": 0.2,
        "signal_phase": "GREEN",
        "green_remaining": 15,
    }
    state.update(overrides)
    return state


def _prediction(probability=0.9, severity=HIGH_SEVERITY):
    return PredictionResult(
        probability=probability,
        severity=severity,
        horizon_seconds=300.0,
        feature_version="v1",
        model_version="xgboost-baseline-v1",
    )


def _signal_context(**overrides):
    defaults = dict(
        node="INT-001",
        normalized_queue=0.3,
        normalized_arrival_rate=0.2,
        downstream_pressure=0.1,
        base_green=10.0,
    )
    defaults.update(overrides)
    return SignalContext(**defaults)


def _network():
    return build_graph(
        [
            Edge("ax", "A", "X", 1.0, 100),
            Edge("xb", "X", "B", 1.0, 100),
            Edge("ay", "A", "Y", 5.0, 100),
            Edge("yb", "Y", "B", 5.0, 100),
        ]
    )


def _congested_cost(u, v, data):
    return data["free_flow_time"] + (100.0 if (u, v) == ("A", "X") else 0.0)


def _routing_context(**overrides):
    planner = RoutePlanner(_network())
    defaults = dict(
        planner=planner,
        source="A",
        destination="B",
        cost_fn=_congested_cost,
        current_path=("A", "X", "B"),
        current_cost=50.0,
    )
    defaults.update(overrides)
    return RoutingContext(**defaults)


def test_no_intervention_below_probability_threshold():
    action = decide(
        _state(),
        _prediction(probability=0.4),
        signal=_signal_context(),
        routing=_routing_context(),
    )
    assert action.type == ActionKind.NO_ACTION


def test_no_intervention_below_minimum_severity():
    action = decide(
        _state(),
        _prediction(probability=1.0, severity=LOW_SEVERITY),
        signal=_signal_context(),
        routing=_routing_context(),
    )
    assert action.type == ActionKind.NO_ACTION


def test_intervention_above_threshold():
    action = decide(_state(), _prediction(), signal=_signal_context())
    assert action.type == ActionKind.SIGNAL


def test_signal_candidate_generation():
    action = decide(_state(), _prediction(), signal=_signal_context())
    assert action.type == ActionKind.SIGNAL
    assert action.target == "INT-001"
    assert "recommended_green_seconds" in action.parameters
    assert "score" in action.parameters


def test_route_candidate_generation():
    action = decide(_state(), _prediction(), routing=_routing_context())
    assert action.type == ActionKind.ROUTE
    assert action.target == "B"
    assert action.parameters["path"] == ["A", "Y", "B"]
    assert action.parameters["current_path"] == ["A", "X", "B"]


def test_deterministic_candidate_ranking():
    action = decide(_state(), _prediction(), signal=_signal_context(), routing=_routing_context())
    assert action.type == ActionKind.ROUTE  # higher score: 40.0 savings vs 0.6 signal
    assert action.parameters["path"] == ["A", "Y", "B"]


def test_deterministic_repeated_execution():
    kwargs = dict(
        state=_state(),
        prediction=_prediction(),
        signal=_signal_context(),
        routing=_routing_context(),
    )
    first = decide(**kwargs)
    second = decide(**kwargs)
    assert first == second


def test_best_candidate_wins_despite_generation_order():
    action = decide(_state(), _prediction(), signal=_signal_context(), routing=_routing_context())
    assert action.type == ActionKind.ROUTE


def test_max_candidate_interventions_caps_consideration():
    config = DecisionConfig(max_candidate_interventions=1)
    action = decide(
        _state(),
        _prediction(),
        config=config,
        signal=_signal_context(),
        routing=_routing_context(),
    )
    assert action.type == ActionKind.SIGNAL


@pytest.mark.parametrize(
    "probability", [float("nan"), float("inf"), float("-inf"), -0.1, 1.5, "abc", True]
)
def test_malformed_prediction_probability_rejected(probability):
    with pytest.raises(ValueError):
        decide(_state(), _prediction(probability=probability))


def test_malformed_prediction_severity_rejected():
    with pytest.raises(ValueError):
        decide(_state(), _prediction(severity="CRITICAL"))


def test_non_prediction_rejected():
    with pytest.raises(TypeError):
        decide(_state(), {"probability": 0.9})


def test_signal_optimizer_integration():
    context = _signal_context(
        normalized_queue=0.6,
        normalized_arrival_rate=0.4,
        downstream_pressure=0.3,
        base_green=12.0,
    )
    action = decide(_state(), _prediction(), signal=context)
    score = signal_pressure_score(
        normalized_queue=context.normalized_queue,
        normalized_arrival_rate=context.normalized_arrival_rate,
        downstream_pressure=context.downstream_pressure,
    )
    expected_green = recommended_green(
        score, base_green=context.base_green, gain=context.gain, min_green=context.min_green, max_green=context.max_green
    )
    assert action.parameters["score"] == pytest.approx(score)
    assert action.parameters["recommended_green_seconds"] == pytest.approx(expected_green)


def test_routing_planner_integration():
    planner = RoutePlanner(_network())
    context = _routing_context(planner=planner)
    action = decide(_state(), _prediction(), routing=context)
    planned = planner.plan("A", "B", cost_fn=_congested_cost)
    assert action.parameters["path"] == list(planned.path)
    assert action.parameters["total_cost"] == planned.total_cost


def test_no_action_when_no_candidates():
    action = decide(_state(), _prediction())
    assert action.type == ActionKind.NO_ACTION


def test_no_action_when_current_route_already_optimal():
    free_flow_cost = lambda _u, _v, data: data["free_flow_time"]
    context = _routing_context(cost_fn=free_flow_cost, current_path=("A", "X", "B"), current_cost=2.0)
    action = decide(_state(), _prediction(), routing=context)
    assert action.type == ActionKind.NO_ACTION


def test_action_representation_validation():
    action = decide(_state(), _prediction(), signal=_signal_context())
    assert isinstance(action, Action)
    assert isinstance(action.type, ActionKind)
    assert isinstance(action.target, str)
    assert isinstance(action.parameters, dict)
    assert isinstance(action.source, str)
    assert isinstance(action.timestamp, float)
    with pytest.raises(AttributeError):
        action.timestamp = 5.0  # immutable


def test_timestamp_propagation():
    for timestamp in (1700000000, 1700000000.5):
        signal_action = decide(_state(timestamp=timestamp), _prediction(), signal=_signal_context())
        assert signal_action.timestamp == float(timestamp)
        route_action = decide(_state(timestamp=timestamp), _prediction(), routing=_routing_context())
        assert route_action.timestamp == float(timestamp)
        no_action = decide(_state(timestamp=timestamp), _prediction(probability=0.1))
        assert no_action.timestamp == float(timestamp)


def test_missing_or_invalid_timestamp_rejected():
    with pytest.raises(ValueError):
        decide(_state(timestamp=None), _prediction())
    state = _state()
    del state["timestamp"]
    with pytest.raises(ValueError):
        decide(state, _prediction())


def test_source_field():
    for action in (
        decide(_state(), _prediction(probability=0.1)),
        decide(_state(), _prediction(), signal=_signal_context()),
        decide(_state(), _prediction(), routing=_routing_context()),
    ):
        assert action.source == DEFAULT_ACTION_SOURCE


def test_tie_breaking_prefers_signal():
    signal = _signal_context(
        normalized_queue=1.0,
        normalized_arrival_rate=0.0,
        downstream_pressure=4.0,
        base_green=5.0,
    )
    routing = _routing_context(current_cost=15.0)  # savings = 15 - 10 = 5.0, ties signal score
    action = decide(_state(), _prediction(), signal=signal, routing=routing)
    assert action.type == ActionKind.SIGNAL


@pytest.mark.parametrize(
    "kwargs",
    [
        {"prediction_probability_threshold": -0.1},
        {"prediction_probability_threshold": 1.5},
        {"prediction_probability_threshold": float("nan")},
        {"prediction_probability_threshold": "abc"},
        {"minimum_severity": "CRITICAL"},
        {"signal_enabled": "yes"},
        {"routing_enabled": 1},
        {"diversion_cap": -1.0},
        {"diversion_cap": float("nan")},
        {"max_candidate_interventions": 0},
        {"max_candidate_interventions": -3},
        {"max_candidate_interventions": 2.5},
        {"max_candidate_interventions": True},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        DecisionConfig(**kwargs)


def test_invalid_signal_context_rejected():
    with pytest.raises(ValueError):
        decide(_state(), _prediction(), signal=_signal_context(normalized_queue=-0.1))
    with pytest.raises(ValueError):
        decide(_state(), _prediction(), signal=_signal_context(normalized_queue=float("nan")))


def test_invalid_routing_context_rejected():
    with pytest.raises(TypeError):
        decide(_state(), _prediction(), routing=_routing_context(planner=object()))


def test_engine_does_not_mutate_inputs():
    state = _state()
    state_snapshot = copy.deepcopy(state)
    prediction = _prediction()
    prediction_snapshot = copy.deepcopy(prediction)
    config = DecisionConfig()
    config_snapshot = copy.deepcopy(config)
    signal = _signal_context()
    signal_snapshot = copy.deepcopy(signal)
    planner = RoutePlanner(_network())
    routing = _routing_context(planner=planner)
    routing_scalars = {
        "source": routing.source,
        "destination": routing.destination,
        "cost_fn": routing.cost_fn,
        "current_path": routing.current_path,
        "current_cost": routing.current_cost,
        "diversion_cap": routing.diversion_cap,
    }
    edges_before = [(e.edge_id, e.free_flow_time, e.capacity) for e in planner._graph.edges()]

    decide(
        state,
        prediction,
        config=config,
        signal=signal,
        routing=routing,
    )

    assert state == state_snapshot
    assert prediction == prediction_snapshot
    assert config == config_snapshot
    assert signal == signal_snapshot
    assert routing.source == routing_scalars["source"]
    assert routing.destination == routing_scalars["destination"]
    assert routing.cost_fn == routing_scalars["cost_fn"]
    assert routing.current_path == routing_scalars["current_path"]
    assert routing.current_cost == routing_scalars["current_cost"]
    assert routing.diversion_cap == routing_scalars["diversion_cap"]
    assert [(e.edge_id, e.free_flow_time, e.capacity) for e in planner._graph.edges()] == edges_before