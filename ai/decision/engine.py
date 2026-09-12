"""AI Decision Engine for M1.

The engine consumes the current canonical TrafficState, a congestion prediction
result, optional route/topology context, and optional signal context, applies
explicit configurable thresholds, and deterministically selects zero or one
intervention:

* ``SIGNAL`` — a signal-green recommendation delegated to ``ai.signals``.
* ``ROUTE`` — a diversion recommendation delegated to ``ai.routing``.
* ``NO_ACTION`` — no intervention meets the configured criteria.

Decision logic only: no SUMO/TraCI/FastAPI/database/frontend interaction. All
defaults are provisional, documented values — not final Urban Grid thresholds.

Determinism: given identical inputs and configuration, ``decide`` always
returns exactly the same action. Candidate ranking is explicit: higher score
first, then a fixed kind priority (SIGNAL before ROUTE), then the action target
lexicographically. ``max_candidate_interventions`` limits how many candidates
are considered, applied in deterministic generation order (signal, then route).
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Callable, Mapping

from ai.prediction.predict import (
    HIGH_SEVERITY,
    LOW_SEVERITY,
    MEDIUM_SEVERITY,
    PredictionResult,
)
from ai.routing.planner import RoutePlanner
from ai.signals.optimizer import (
    DEFAULT_GAIN,
    DEFAULT_MAX_GREEN,
    DEFAULT_MIN_GREEN,
    recommended_green,
)
from ai.signals.policy import (
    DEFAULT_ARRIVAL_RATE_WEIGHT,
    DEFAULT_DOWNSTREAM_PRESSURE_WEIGHT,
    DEFAULT_QUEUE_WEIGHT,
    signal_pressure_score,
)

DEFAULT_ACTION_SOURCE = "m1-decision-engine-v1"

DEFAULT_PREDICTION_PROBABILITY_THRESHOLD = 0.5
DEFAULT_MINIMUM_SEVERITY = MEDIUM_SEVERITY
DEFAULT_SIGNAL_ENABLED = True
DEFAULT_ROUTING_ENABLED = True
DEFAULT_DIVERSION_CAP = None
DEFAULT_MAX_CANDIDATE_INTERVENTIONS = 8

SUPPORTED_SEVERITIES = frozenset({LOW_SEVERITY, MEDIUM_SEVERITY, HIGH_SEVERITY})

_SEVERITY_RANK = {LOW_SEVERITY: 0, MEDIUM_SEVERITY: 1, HIGH_SEVERITY: 2}
_KIND_PRIORITY = {"SIGNAL": 0, "ROUTE": 1}


def _validate_config(config) -> None:
    threshold = config.prediction_probability_threshold
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("prediction_probability_threshold must be numeric")
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("prediction_probability_threshold must be in [0, 1]")

    if config.minimum_severity is not None and config.minimum_severity not in SUPPORTED_SEVERITIES:
        raise ValueError(
            f"minimum_severity must be one of {sorted(SUPPORTED_SEVERITIES)} or None"
        )

    if not isinstance(config.signal_enabled, bool):
        raise ValueError("signal_enabled must be a boolean")
    if not isinstance(config.routing_enabled, bool):
        raise ValueError("routing_enabled must be a boolean")

    diversion_cap = config.diversion_cap
    if diversion_cap is not None:
        if isinstance(diversion_cap, bool) or not isinstance(diversion_cap, (int, float)):
            raise ValueError("diversion_cap must be a finite non-negative number or None")
        if not math.isfinite(diversion_cap) or diversion_cap < 0:
            raise ValueError("diversion_cap must be a finite non-negative number or None")

    max_candidates = config.max_candidate_interventions
    if not isinstance(max_candidates, int) or isinstance(max_candidates, bool):
        raise ValueError("max_candidate_interventions must be a positive integer")
    if max_candidates < 1:
        raise ValueError("max_candidate_interventions must be a positive integer")


class ActionKind(str, enum.Enum):
    NO_ACTION = "no_action"
    SIGNAL = "signal"
    ROUTE = "route"


@dataclass(frozen=True)
class Action:
    """Local M1 action representation (not the final cross-team contract)."""

    type: ActionKind
    target: str
    parameters: Mapping
    source: str
    timestamp: float


@dataclass(frozen=True)
class DecisionConfig:
    prediction_probability_threshold: float = DEFAULT_PREDICTION_PROBABILITY_THRESHOLD
    minimum_severity: str | None = DEFAULT_MINIMUM_SEVERITY
    signal_enabled: bool = DEFAULT_SIGNAL_ENABLED
    routing_enabled: bool = DEFAULT_ROUTING_ENABLED
    diversion_cap: float | None = DEFAULT_DIVERSION_CAP
    max_candidate_interventions: int = DEFAULT_MAX_CANDIDATE_INTERVENTIONS

    def __post_init__(self) -> None:
        _validate_config(self)


@dataclass(frozen=True)
class SignalContext:
    """Caller-supplied signal-policy inputs for the engine."""

    node: str
    normalized_queue: float
    normalized_arrival_rate: float
    downstream_pressure: float
    base_green: float
    queue_weight: float = DEFAULT_QUEUE_WEIGHT
    arrival_rate_weight: float = DEFAULT_ARRIVAL_RATE_WEIGHT
    downstream_pressure_weight: float = DEFAULT_DOWNSTREAM_PRESSURE_WEIGHT
    gain: float = DEFAULT_GAIN
    min_green: float = DEFAULT_MIN_GREEN
    max_green: float = DEFAULT_MAX_GREEN
    current_green: float | None = None


@dataclass(frozen=True)
class RoutingContext:
    """Caller-supplied routing context; ``planner`` and cost info are provided."""

    planner: RoutePlanner
    source: str
    destination: str
    cost_fn: Callable[[str, str, dict], float] | None = None
    current_path: tuple[str, ...] = ()
    current_cost: float | None = None
    diversion_cap: float | None = None


@dataclass(frozen=True)
class _Candidate:
    score: float
    action: Action

    @property
    def kind(self) -> str:
        return self.action.type.name


def decide(
    state: Mapping[str, object],
    prediction: PredictionResult,
    *,
    config: DecisionConfig = DecisionConfig(),
    signal: SignalContext | None = None,
    routing: RoutingContext | None = None,
) -> Action:
    """Return the deterministic best intervention, or ``NO_ACTION``.

    Intervention is only considered when ``prediction.probability >= threshold``
    and the prediction severity meets the configured minimum. Valid candidates
    are then generated (signal, then route), capped by
    ``max_candidate_interventions``, ranked deterministically, and the single
    best action is returned. Nothing here mutates its inputs.
    """
    _validate_state(state)
    _validate_prediction(prediction)

    gate_rank: int | None = None
    if config.minimum_severity is not None:
        gate_rank = _SEVERITY_RANK[config.minimum_severity]
    if prediction.probability < config.prediction_probability_threshold:
        return _no_action(state)
    if gate_rank is not None and _SEVERITY_RANK[prediction.severity] < gate_rank:
        return _no_action(state)

    candidates: list[_Candidate] = []
    if config.signal_enabled and signal is not None:
        candidates.append(_signal_candidate(signal, state))
    if config.routing_enabled and routing is not None:
        route_candidate = _route_candidate(routing, config, state)
        if route_candidate is not None:
            candidates.append(route_candidate)

    limited = candidates[: config.max_candidate_interventions]
    ranked = sorted(limited, key=_rank_key)
    if not ranked:
        return _no_action(state)
    return ranked[0].action


def _signal_candidate(signal: SignalContext, state: Mapping) -> _Candidate:
    if not isinstance(signal.node, str) or not signal.node.strip():
        raise ValueError("signal.node must be a non-empty string")
    score = signal_pressure_score(
        normalized_queue=signal.normalized_queue,
        normalized_arrival_rate=signal.normalized_arrival_rate,
        downstream_pressure=signal.downstream_pressure,
        queue_weight=signal.queue_weight,
        arrival_rate_weight=signal.arrival_rate_weight,
        downstream_pressure_weight=signal.downstream_pressure_weight,
    )
    green = recommended_green(
        score,
        base_green=signal.base_green,
        gain=signal.gain,
        min_green=signal.min_green,
        max_green=signal.max_green,
        current_green=signal.current_green,
    )
    parameters = {
        "score": score,
        "recommended_green_seconds": green,
        "min_green": signal.min_green,
        "max_green": signal.max_green,
    }
    return _Candidate(
        score=float(score),
        action=Action(
            type=ActionKind.SIGNAL,
            target=signal.node,
            parameters=parameters,
            source=DEFAULT_ACTION_SOURCE,
            timestamp=_timestamp(state),
        ),
    )


def _route_candidate(
    routing: RoutingContext,
    config: DecisionConfig,
    state: Mapping,
) -> _Candidate | None:
    if not isinstance(routing.planner, RoutePlanner):
        raise TypeError("routing.planner must be a RoutePlanner")
    cap = routing.diversion_cap if routing.diversion_cap is not None else config.diversion_cap
    planned = routing.planner.plan(
        routing.source,
        routing.destination,
        cost_fn=routing.cost_fn,
        diversion_cap=cap,
    )
    if not planned.reachable:
        return None
    if routing.current_path and tuple(routing.current_path) == planned.path:
        return None

    current_path = tuple(routing.current_path)
    if current_path and routing.current_cost is not None:
        savings = routing.current_cost - planned.total_cost
        if savings < 0:
            return None
        score = savings
    elif current_path:
        score = 0.0
    else:
        score = 0.0

    parameters = {
        "path": list(planned.path),
        "total_cost": planned.total_cost,
        "current_path": list(current_path),
    }
    return _Candidate(
        score=float(score),
        action=Action(
            type=ActionKind.ROUTE,
            target=routing.destination,
            parameters=parameters,
            source=DEFAULT_ACTION_SOURCE,
            timestamp=_timestamp(state),
        ),
    )


def _no_action(state: Mapping) -> Action:
    return Action(
        type=ActionKind.NO_ACTION,
        target="",
        parameters={},
        source=DEFAULT_ACTION_SOURCE,
        timestamp=_timestamp(state),
    )


def _rank_key(candidate: _Candidate) -> tuple:
    return (
        -candidate.score,
        _KIND_PRIORITY[candidate.kind],
        candidate.action.target,
    )


def _validate_state(state: Mapping) -> None:
    if not isinstance(state, Mapping):
        raise ValueError("state must be a canonical TrafficState mapping")
    _timestamp(state)


def _timestamp(state: Mapping) -> float:
    value = state.get("timestamp")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("state must include a numeric 'timestamp'")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("state 'timestamp' must be finite")
    return result


def _validate_prediction(prediction) -> None:
    if not isinstance(prediction, PredictionResult):
        raise TypeError("prediction must be a PredictionResult")
    probability = prediction.probability
    if isinstance(probability, bool) or not isinstance(probability, (int, float)):
        raise ValueError("prediction probability must be numeric")
    if not math.isfinite(probability):
        raise ValueError("prediction probability must be finite")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("prediction probability must be in [0, 1]")
    if prediction.severity not in SUPPORTED_SEVERITIES:
        raise ValueError(
            f"prediction severity must be one of {sorted(SUPPORTED_SEVERITIES)}, "
            f"got {prediction.severity!r}"
        )