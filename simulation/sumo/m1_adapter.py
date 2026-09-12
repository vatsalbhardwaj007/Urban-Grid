"""M1 AI Decision Engine Integration Adapter for M2 Simulation.

Provides the production integration layer between:
- M2 TrafficStateProvider & TraCIBridge
- M1 Prediction & Decision Engine (ai.decision.engine.decide)
- M1 Action Contract Adapter (ai.decision.adapter.convert)
- M2 ActionDispatcher & Actuation Layer

Architecture:
    TrafficStateProvider (canonical TrafficState)
        ↓
    M1 predict (features -> XGBoost -> PredictionResult)
        ↓
    M2 context extraction (SignalContext, RoutingContext, vehicle_id)
        ↓
    M1 decide(state, prediction, config, signal, routing) -> Action
        ↓
    M1 adapter.convert(action, timestamp, vehicle_id) -> SignalAction | RouteAction
        ↓
    M2 ActionDispatcher -> TraCI -> SUMO
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Mapping, Sequence

from shared.schemas.route_action import RouteAction
from shared.schemas.signal_action import SignalAction
from shared.schemas.traffic_state import TrafficState
from simulation.sumo.traci_bridge import TraCIBridge

logger = logging.getLogger(__name__)

try:
    from ai.decision.adapter import convert as m1_convert_action
    from ai.decision.engine import (
        Action,
        ActionKind,
        DecisionConfig,
        RoutingContext,
        SignalContext,
        decide as m1_decide,
    )
    from ai.prediction.predict import PredictionResult, predict
    from ai.prediction.test_train import _varied_samples
    from ai.prediction.train import TrainingResult, train_baseline
    from ai.routing.graph import Edge, RoadNetwork, build_graph
    from ai.routing.planner import RoutePlanner

    HAS_M1 = True
except ImportError:
    HAS_M1 = False
    m1_convert_action = None
    Action = None
    ActionKind = None
    DecisionConfig = None
    RoutingContext = None
    SignalContext = None
    m1_decide = None
    PredictionResult = None
    predict = None
    _varied_samples = None
    TrainingResult = None
    train_baseline = None
    Edge = None
    RoadNetwork = None
    build_graph = None
    RoutePlanner = None


def build_urban_grid_road_network() -> RoadNetwork:
    """Build the canonical RoadNetwork topology for the Urban Grid simulation.

    Nodes represent SUMO edge identifiers to allow Dijkstra least-cost paths
    to directly yield valid, executable SUMO edge route sequences.
    """
    edges = [
        # Primary corridor eastbound: W1 -> I1 -> I2 -> E2
        Edge("w1_to_i1_i2", "E_W1_I1", "E_I1_I2", free_flow_time=15.0, capacity=100.0),
        Edge("i1_i2_to_e2", "E_I1_I2", "E_I2_E2", free_flow_time=15.0, capacity=100.0),
        # Alternate corridor eastbound: W1 -> I1 -> I3 -> I4 -> E4
        Edge("w1_to_i1_i3", "E_W1_I1", "E_I1_I3", free_flow_time=5.0, capacity=100.0),
        Edge("i1_i3_to_i3_i4", "E_I1_I3", "E_I3_I4", free_flow_time=5.0, capacity=100.0),
        Edge("i3_i4_to_e4", "E_I3_I4", "E_I4_E4", free_flow_time=5.0, capacity=100.0),
        # Inter-junction connecting edges
        Edge("i1_i2_to_i2_i4", "E_I1_I2", "E_I2_I4", free_flow_time=15.0, capacity=100.0),
        Edge("i2_i4_to_e4", "E_I2_I4", "E_I4_E4", free_flow_time=15.0, capacity=100.0),
    ]
    return build_graph(edges)


def build_signal_context(
    state: TrafficState,
    *,
    base_green: float = 15.0,
    min_green: float = 5.0,
    max_green: float = 60.0,
) -> SignalContext:
    """Extract and normalize signal optimization context from a canonical TrafficState.

    Inputs are strictly normalized/clamped according to M1 signal policy rules.
    """
    # Normalize queue length against an expected saturation capacity (e.g. 20 vehicles)
    normalized_queue = min(1.0, max(0.0, float(state.total_queue) / 20.0))

    # Normalize arrival rate against expected peak arrival (e.g. 10 vehicles/second)
    normalized_arrival = min(1.0, max(0.0, float(state.arrival_rate) / 10.0))

    # Downstream pressure is a finite non-negative metric (use density)
    downstream_pressure = max(0.0, float(state.density))

    current_green = float(state.green_remaining) if state.green_remaining >= 0.0 else None

    return SignalContext(
        node=state.intersection_id,
        normalized_queue=normalized_queue,
        normalized_arrival_rate=normalized_arrival,
        downstream_pressure=downstream_pressure,
        base_green=base_green,
        min_green=min_green,
        max_green=max_green,
        current_green=current_green,
    )


class RealM1DecisionEngine:
    """Production M2 decision engine wrapping the real M1 AI prediction and decision stack.

    Implements M2's DecisionEngineProtocol:
        decide(states: dict[str, TrafficState]) -> SignalAction | RouteAction | Sequence[...] | None
    """

    def __init__(
        self,
        bridge: TraCIBridge | None = None,
        *,
        training_result: TrainingResult | None = None,
        config: DecisionConfig | None = None,
        road_network: RoadNetwork | None = None,
    ) -> None:
        if not HAS_M1:
            raise RuntimeError(
                "M1 package (ai.*) is not available in the current environment. "
                "Ensure feature/ai-prediction is merged or present in PYTHONPATH."
            )
        self._bridge = bridge
        self._config = config or DecisionConfig()
        self._road_network = road_network or build_urban_grid_road_network()
        self._planner = RoutePlanner(self._road_network)

        # Initialize or train default baseline model
        if training_result is None:
            logger.info("Initializing baseline M1 XGBoost prediction model...")
            self._training_result = train_baseline(_varied_samples(24))
        else:
            self._training_result = training_result

    @property
    def training_result(self) -> TrainingResult:
        return self._training_result

    @property
    def config(self) -> DecisionConfig:
        return self._config

    def set_bridge(self, bridge: TraCIBridge) -> None:
        self._bridge = bridge

    def decide(
        self,
        states: dict[str, TrafficState],
    ) -> list[SignalAction | RouteAction] | None:
        """Evaluate traffic states across intersections using M1 prediction & decision engine.

        Returns:
            A list of validated shared SignalAction and/or RouteAction contracts,
            or None if no intervention is selected.
        """
        if not states:
            return None

        dispatched_actions: list[SignalAction | RouteAction] = []
        now_utc = datetime.now(timezone.utc)

        for intersection_id, state in states.items():
            state_dict = state.model_dump()

            # 1. Run real M1 ML inference to produce PredictionResult
            try:
                prediction: PredictionResult = predict(self._training_result, state_dict)
            except Exception as exc:
                logger.warning(
                    f"M1 prediction failed for intersection '{intersection_id}': {exc}"
                )
                continue

            # 2. Build M1 SignalContext
            signal_ctx = build_signal_context(state)

            # 3. Build M1 RoutingContext if vehicles are active in the network
            routing_ctx = None
            candidate_veh_id: str | None = None

            if self._config.routing_enabled and self._bridge is not None and self._bridge.is_connected:
                candidate_veh_id, routing_ctx = self._find_routing_candidate()

            # 4. Invoke real M1 Decision Engine
            try:
                action: Action = m1_decide(
                    state=state_dict,
                    prediction=prediction,
                    config=self._config,
                    signal=signal_ctx if self._config.signal_enabled else None,
                    routing=routing_ctx if self._config.routing_enabled else None,
                )
            except Exception as exc:
                logger.warning(
                    f"M1 decision engine failed for intersection '{intersection_id}': {exc}"
                )
                continue

            # 5. Convert M1 Action to shared contract via M1 adapter
            if action.type == ActionKind.NO_ACTION:
                continue

            # Route actions require the actual SUMO vehicle ID from the live runtime
            route_vehicle_id = candidate_veh_id if action.type == ActionKind.ROUTE else None

            try:
                shared_action = m1_convert_action(
                    action,
                    timestamp=now_utc,
                    vehicle_id=route_vehicle_id,
                )
                if shared_action is not None:
                    dispatched_actions.append(shared_action)
            except Exception as exc:
                logger.warning(
                    f"M1 adapter conversion failed for {action.type} at '{intersection_id}': {exc}"
                )
                continue

        return dispatched_actions if dispatched_actions else None

    def _find_routing_candidate(self) -> tuple[str | None, RoutingContext | None]:
        """Find an active vehicle eligible for rerouting and construct its RoutingContext."""
        if self._bridge is None or not self._bridge.is_connected:
            return None, None

        try:
            with self._bridge.lock:
                active_vehicles = self._bridge.get_vehicle_ids()
                if not active_vehicles:
                    return None, None

                conn = self._bridge.raw_connection
                # Look for an active vehicle on the primary entrance route
                for veh_id in active_vehicles:
                    route = list(conn.vehicle.getRoute(veh_id))
                    if not route:
                        continue

                    # If vehicle is currently on the primary route from E_W1_I1, offer alternate to E_I4_E4
                    if route[0] == "E_W1_I1" and route[-1] in ("E_I2_E2", "E_I4_E4"):
                        routing_ctx = RoutingContext(
                            planner=self._planner,
                            source="E_W1_I1",
                            destination="E_I4_E4",
                            current_path=tuple(route),
                            current_cost=30.0,
                        )
                        return veh_id, routing_ctx

                # Fallback: pick the first active vehicle
                sample_veh = active_vehicles[0]
                current_route = tuple(conn.vehicle.getRoute(sample_veh))
                if len(current_route) >= 2:
                    routing_ctx = RoutingContext(
                        planner=self._planner,
                        source=current_route[0],
                        destination=current_route[-1],
                        current_path=current_route,
                        current_cost=25.0,
                    )
                    return sample_veh, routing_ctx

        except Exception as exc:
            logger.debug(f"Error checking vehicles for routing candidate: {exc}")

        return None, None
