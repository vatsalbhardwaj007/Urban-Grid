"""Integration tests for the real M1 AI Decision Engine and M2 orchestration layer."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import pytest

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
from ai.prediction.train import train_baseline
from ai.prediction.test_train import _varied_samples
from ai.routing.graph import Edge, build_graph
from ai.routing.planner import RoutePlanner
from shared.schemas.route_action import ActionSource, RouteAction
from shared.schemas.signal_action import SignalAction
from shared.schemas.traffic_state import TrafficState, LaneFeature
from simulation.sumo.actuation import ActionDispatcher
from simulation.sumo.control_loop import SimulationControlLoop
from simulation.sumo.m1_adapter import (
    HAS_M1,
    RealM1DecisionEngine,
    build_signal_context,
    build_urban_grid_road_network,
)
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import TraCIBridge, is_sumo_available

REQUIRES_SUMO = pytest.mark.skipif(
    not is_sumo_available(),
    reason="SUMO executable or traci package is unavailable in this environment.",
)
REQUIRES_M1 = pytest.mark.skipif(
    not HAS_M1,
    reason="M1 AI package is unavailable in this environment (feature/ai-prediction not present).",
)


@pytest.fixture
def running_bridge():
    """Start and yield a live TraCIBridge, then cleanly close it."""
    bridge = TraCIBridge()
    bridge.start()
    yield bridge
    bridge.close()


# =============================================================================
# Architectural Invariant Tests
# =============================================================================


@REQUIRES_M1
def test_m1_has_no_direct_traci_dependencies() -> None:
    """Verify that M1 remains completely unaware of TraCI and SUMO internals."""
    ai_dir = Path(__file__).resolve().parent.parent.parent.parent / "ai"
    if not ai_dir.is_dir():
        pytest.skip("ai/ directory not present in workspace")

    forbidden_terms = ["traci", "TraCIBridge", "traci_bridge", "sumolib"]

    for root, _, files in os.walk(ai_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = Path(root) / file
            content = path.read_text(encoding="utf-8")
            for term in forbidden_terms:
                assert term not in content, (
                    f"Forbidden dependency '{term}' found in M1 file: {path}"
                )


# =============================================================================
# Context Construction and Prediction Tests
# =============================================================================


@REQUIRES_M1
def test_canonical_traffic_state_feeds_m1_prediction() -> None:
    """Canonical TrafficState v1 dictionary is directly accepted by M1 predict()."""
    tr = train_baseline(_varied_samples(24))

    state = TrafficState(
        timestamp=100.0,
        intersection_id="I1",
        lane_features=[
            LaneFeature(
                lane_id="E_W1_I1_0",
                vehicle_count=8,
                mean_speed=6.0,
                queue_length=5,
                occupancy=0.6,
                arrival_rate=3.0,
                density=0.4,
                flow=18.0,
            )
        ],
        total_queue=5,
        mean_speed=6.0,
        arrival_rate=3.0,
        density=0.4,
        signal_phase="GREEN",
        green_remaining=15.0,
    )

    pred = predict(tr, state.model_dump())
    assert isinstance(pred, PredictionResult)
    assert 0.0 <= pred.probability <= 1.0
    assert pred.severity in {"LOW", "MEDIUM", "HIGH"}
    assert pred.horizon_seconds == 300.0


def test_signal_context_construction_from_traffic_state() -> None:
    """SignalContext is correctly normalized from canonical TrafficState."""
    state = TrafficState(
        timestamp=100.0,
        intersection_id="I1",
        lane_features=[],
        total_queue=10,
        mean_speed=12.0,
        arrival_rate=4.0,
        density=0.35,
        signal_phase="GREEN",
        green_remaining=18.0,
    )

    ctx = build_signal_context(state)
    assert ctx.node == "I1"
    assert 0.0 <= ctx.normalized_queue <= 1.0
    assert 0.0 <= ctx.normalized_arrival_rate <= 1.0
    assert ctx.downstream_pressure >= 0.0
    assert ctx.current_green == 18.0
    assert ctx.min_green == 5.0
    assert ctx.max_green == 60.0


@REQUIRES_M1
def test_road_network_routing_context_produces_sumo_edges() -> None:
    """RoadNetwork planned paths directly yield executable SUMO edge route sequences."""
    network = build_urban_grid_road_network()
    planner = RoutePlanner(network)

    planned = planner.plan("E_W1_I1", "E_I4_E4")
    assert planned.reachable is True
    # The alternate path in the network:
    assert list(planned.path) == ["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"]


# =============================================================================
# M1 Decision Engine + Adapter Action Flow Tests
# =============================================================================


@REQUIRES_SUMO
@REQUIRES_M1
def test_m1_signal_action_flow_to_dispatcher(running_bridge: TraCIBridge) -> None:
    """M1 signal decision -> adapter -> SignalAction -> ActionDispatcher -> TraCI."""
    state_dict = {
        "timestamp": 10.0,
        "intersection_id": "I1",
        "lane_features": [],
        "total_queue": 15,
        "mean_speed": 3.0,
        "arrival_rate": 5.0,
        "density": 0.8,
        "signal_phase": "GREEN",
        "green_remaining": 10.0,
    }
    pred = PredictionResult(0.95, "HIGH", 300.0, "v1", "xgb-v1")
    sig_ctx = SignalContext(
        node="I1",
        normalized_queue=0.8,
        normalized_arrival_rate=0.7,
        downstream_pressure=0.6,
        base_green=20.0,
        min_green=5.0,
        max_green=60.0,
        current_green=10.0,
    )

    # 1. M1 decides
    m1_action = m1_decide(state_dict, pred, signal=sig_ctx)
    assert m1_action.type == ActionKind.SIGNAL
    assert m1_action.target == "I1"

    # 2. M1 adapter converts with explicit UTC datetime
    now = datetime.now(timezone.utc)
    shared_action = m1_convert_action(m1_action, timestamp=now)
    assert isinstance(shared_action, SignalAction)
    assert shared_action.target == "I1"
    assert shared_action.source == ActionSource.AI
    assert shared_action.timestamp == now

    # 3. M2 ActionDispatcher applies to SUMO
    dispatcher = ActionDispatcher(running_bridge)
    res = dispatcher.dispatch(shared_action)
    assert res.success is True
    assert res.target == "I1"


@REQUIRES_SUMO
@REQUIRES_M1
def test_m1_route_action_flow_to_dispatcher(running_bridge: TraCIBridge) -> None:
    """M1 route decision -> adapter (with vehicle_id) -> RouteAction -> ActionDispatcher -> TraCI."""
    running_bridge.step()  # insert flow vehicles
    vehicles = running_bridge.get_vehicle_ids()
    assert len(vehicles) > 0
    conn = running_bridge.raw_connection
    target_veh = None
    for vid in vehicles:
        route = list(conn.vehicle.getRoute(vid))
        if route and route[0] == "E_W1_I1":
            target_veh = vid
            break
    assert target_veh is not None, "Expected vehicle starting on E_W1_I1"

    network = build_urban_grid_road_network()
    planner = RoutePlanner(network)
    routing_ctx = RoutingContext(
        planner=planner,
        source="E_W1_I1",
        destination="E_I4_E4",
        current_path=("E_W1_I1", "E_I1_I2", "E_I2_E2"),
        current_cost=50.0,
    )

    state_dict = {"timestamp": 10.0, "intersection_id": "I1"}
    pred = PredictionResult(0.9, "HIGH", 300.0, "v1", "xgb-v1")
    config = DecisionConfig(signal_enabled=False, routing_enabled=True)

    # 1. M1 decides
    m1_action = m1_decide(state_dict, pred, routing=routing_ctx, config=config)
    assert m1_action.type == ActionKind.ROUTE
    assert m1_action.target == "E_I4_E4"

    # 2. M1 adapter converts with live vehicle_id from SUMO
    now = datetime.now(timezone.utc)
    shared_action = m1_convert_action(m1_action, timestamp=now, vehicle_id=target_veh)
    assert isinstance(shared_action, RouteAction)
    assert shared_action.target == target_veh
    assert shared_action.target != "E_I4_E4"  # critical requirement: target is vehicle_id
    assert shared_action.route == ["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"]
    assert shared_action.source == ActionSource.AI

    # 3. M2 ActionDispatcher applies to SUMO
    dispatcher = ActionDispatcher(running_bridge)
    res = dispatcher.dispatch(shared_action)
    assert res.success is True
    assert res.target == target_veh


# =============================================================================
# Full Closed-Loop Orchestration Integration Tests
# =============================================================================


@REQUIRES_SUMO
@REQUIRES_M1
def test_full_closed_loop_orchestration_with_real_m1_engine(running_bridge: TraCIBridge) -> None:
    """Full closed-loop test: SUMO -> TrafficState -> M1 predict -> M1 decide -> TraCI -> next cycle."""
    provider = TrafficStateProvider(running_bridge)
    dispatcher = ActionDispatcher(running_bridge)

    # Create real M1 Decision Engine configured to actively intervene
    config = DecisionConfig(
        prediction_probability_threshold=0.0,  # allow intervention
        minimum_severity="LOW",
        signal_enabled=True,
        routing_enabled=True,
    )
    real_m1_engine = RealM1DecisionEngine(bridge=running_bridge, config=config)

    loop = SimulationControlLoop(
        provider=provider,
        dispatcher=dispatcher,
        decision_engine=real_m1_engine,
        step_interval=1,
    )

    # Cycle 1: step SUMO, get state, run M1, dispatch action, record post state
    res1 = loop.step_cycle()
    assert res1.success is True
    assert res1.cycle == 1
    assert set(res1.states.keys()) == {"I1", "I2", "I3", "I4"}
    assert res1.actions_attempted >= 1
    assert len(res1.action_results) >= 1
    assert res1.errors == []

    # Cycle 2: advance simulation and observe updated traffic state
    res2 = loop.step_cycle()
    assert res2.success is True
    assert res2.cycle == 2
    assert res2.simulation_time > res1.simulation_time
    assert set(res2.states.keys()) == {"I1", "I2", "I3", "I4"}
