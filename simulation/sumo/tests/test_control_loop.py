"""Integration and unit tests for M2 SimulationControlLoop orchestrator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import pytest

from shared.schemas.route_action import RouteAction
from shared.schemas.signal_action import SignalAction
from shared.schemas.traffic_state import TrafficState
from simulation.sumo.actuation import (
    ActionDispatcher,
    RouteActuationResult,
    SignalActuationResult,
    SimulationDisconnectedError,
    UnknownTrafficLightError,
)
from simulation.sumo.control_loop import (
    CallableDecisionAdapter,
    ControlCycleResult,
    NullDecisionEngine,
    SimulationControlLoop,
)
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import TraCIBridge, is_sumo_available

REQUIRES_SUMO = pytest.mark.skipif(
    not is_sumo_available(),
    reason="SUMO executable or traci package is unavailable in this environment.",
)


@pytest.fixture
def running_bridge():
    """Start and yield a live TraCIBridge, then cleanly close it."""
    bridge = TraCIBridge()
    bridge.start()
    yield bridge
    bridge.close()


@pytest.fixture
def loop_components(running_bridge: TraCIBridge):
    """Create wired components for SimulationControlLoop with live SUMO."""
    provider = TrafficStateProvider(running_bridge)
    dispatcher = ActionDispatcher(running_bridge)
    control_loop = SimulationControlLoop(
        provider=provider,
        dispatcher=dispatcher,
        decision_engine=NullDecisionEngine(),
        step_interval=1,
    )
    return control_loop, provider, dispatcher, running_bridge


class TestSimulationControlLoop:
    """Test suite for closed-loop orchestration."""

    @REQUIRES_SUMO
    def test_one_control_cycle(self, loop_components) -> None:
        """1. A single control cycle advances SUMO and returns a valid ControlCycleResult."""
        control_loop, provider, _, _ = loop_components
        t_start = provider.simulation_time

        result = control_loop.step_cycle()
        assert isinstance(result, ControlCycleResult)
        assert result.cycle == 1
        assert result.simulation_time == t_start + 1.0
        assert result.success is True
        assert result.actions_attempted == 0
        assert len(result.errors) == 0

    @REQUIRES_SUMO
    def test_multiple_control_cycles(self, loop_components) -> None:
        """2. Multiple control cycles sequentially advance time and increment cycle counter."""
        control_loop, provider, _, _ = loop_components
        t_start = provider.simulation_time

        results = control_loop.run_steps(n_cycles=3)
        assert len(results) == 3
        assert [r.cycle for r in results] == [1, 2, 3]
        assert control_loop.current_cycle == 3
        assert provider.simulation_time == t_start + 3.0

    @REQUIRES_SUMO
    def test_state_acquisition(self, loop_components) -> None:
        """3. Control cycle acquires valid canonical TrafficState for all 4 intersections."""
        control_loop, _, _, _ = loop_components

        result = control_loop.step_cycle()
        assert set(result.states.keys()) == {"I1", "I2", "I3", "I4"}

        for iid, state in result.states.items():
            assert isinstance(state, TrafficState)
            assert state.intersection_id == iid
            assert len(state.lane_features) == 8
            assert state.signal_phase in {"RED", "YELLOW", "GREEN"}

    @REQUIRES_SUMO
    def test_signal_action_path(self, loop_components) -> None:
        """4. Decision engine providing SignalAction has it dispatched and applied to TraCI."""
        control_loop, _, _, running_bridge = loop_components

        # Mock M1 decision engine returning SignalAction
        class SignalInterventionEngine:
            def decide(self, states: dict[str, TrafficState]) -> SignalAction:
                return SignalAction(
                    target="I1",
                    green_duration=50.0,
                    source="AI",
                    timestamp=datetime.now(timezone.utc),
                )

        control_loop.set_decision_engine(SignalInterventionEngine())
        result = control_loop.step_cycle()

        assert result.actions_attempted == 1
        assert len(result.action_results) == 1
        assert result.success is True

        res_data = result.action_results[0]
        assert res_data["target"] == "I1"
        assert res_data["applied_duration"] == 50.0

        # Confirm TraCI traffic light program updated
        conn = running_bridge.raw_connection
        assert conn.trafficlight.getPhaseDuration("I1") == 50.0

    @REQUIRES_SUMO
    def test_route_action_path(self, loop_components) -> None:
        """5. Decision engine providing RouteAction has it dispatched and applied to vehicle."""
        control_loop, _, _, running_bridge = loop_components

        # Step once to ensure vehicle flow is inserted
        control_loop.step_cycle()

        alternate_route = ["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"]

        class RouteInterventionEngine:
            def decide(self, states: dict[str, TrafficState]) -> RouteAction:
                return RouteAction(
                    target="flow_norm_prim.0",
                    route=alternate_route,
                    source="AI",
                    timestamp=datetime.now(timezone.utc),
                )

        control_loop.set_decision_engine(RouteInterventionEngine())
        result = control_loop.step_cycle()

        assert result.actions_attempted == 1
        assert len(result.action_results) == 1
        res_data = result.action_results[0]
        assert res_data["target"] == "flow_norm_prim.0"
        assert res_data["applied_route"] == alternate_route

        # Confirm TraCI vehicle updated
        conn = running_bridge.raw_connection
        assert list(conn.vehicle.getRoute("flow_norm_prim.0")) == alternate_route

    @REQUIRES_SUMO
    def test_multiple_actions_in_single_cycle(self, loop_components) -> None:
        """6. Decision engine returning a sequence of actions applies all in the same cycle."""
        control_loop, _, _, _ = loop_components
        control_loop.step_cycle()  # Insert vehicles

        class MultiInterventionEngine:
            def decide(self, states: dict[str, TrafficState]) -> list[SignalAction | RouteAction]:
                return [
                    SignalAction(
                        target="I2",
                        green_duration=40.0,
                        source="AI",
                        timestamp=datetime.now(timezone.utc),
                    ),
                    RouteAction(
                        target="flow_norm_prim.0",
                        route=["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"],
                        source="AI",
                        timestamp=datetime.now(timezone.utc),
                    ),
                ]

        control_loop.set_decision_engine(MultiInterventionEngine())
        result = control_loop.step_cycle()

        assert result.actions_attempted == 2
        assert len(result.action_results) == 2
        assert result.success is True

    @REQUIRES_SUMO
    def test_invalid_action_handling_continue_policy(self, loop_components) -> None:
        """7. Invalid action under 'continue' policy logs error and does not crash simulation."""
        control_loop, _, _, _ = loop_components
        control_loop.error_policy = "continue"

        class BadActionEngine:
            def decide(self, states: dict[str, TrafficState]) -> SignalAction:
                return SignalAction(
                    target="I_NONEXISTENT",
                    green_duration=30.0,
                    source="AI",
                    timestamp=datetime.now(timezone.utc),
                )

        control_loop.set_decision_engine(BadActionEngine())
        result = control_loop.step_cycle()

        assert result.actions_attempted == 1
        assert len(result.action_results) == 0
        assert len(result.errors) == 1
        assert "I_NONEXISTENT" in result.errors[0]
        assert result.success is False

        # Verify simulation can continue normally in subsequent cycle
        control_loop.set_decision_engine(NullDecisionEngine())
        next_res = control_loop.step_cycle()
        assert next_res.success is True

    @REQUIRES_SUMO
    def test_invalid_action_handling_stop_policy(self, loop_components) -> None:
        """8. Invalid action under 'stop' policy raises controlled ActuationError."""
        control_loop, _, _, _ = loop_components
        control_loop.error_policy = "stop"

        class BadActionEngine:
            def decide(self, states: dict[str, TrafficState]) -> SignalAction:
                return SignalAction(
                    target="I_NONEXISTENT",
                    green_duration=30.0,
                    source="AI",
                    timestamp=datetime.now(timezone.utc),
                )

        control_loop.set_decision_engine(BadActionEngine())
        with pytest.raises(UnknownTrafficLightError):
            control_loop.step_cycle()

    def test_sumo_disconnect_handling(self) -> None:
        """9. Executing cycle with disconnected SUMO raises SimulationDisconnectedError."""
        bridge = TraCIBridge()  # Not started
        provider = TrafficStateProvider(bridge)
        dispatcher = ActionDispatcher(bridge)
        control_loop = SimulationControlLoop(provider=provider, dispatcher=dispatcher)

        with pytest.raises(SimulationDisconnectedError):
            control_loop.step_cycle()

    @REQUIRES_SUMO
    @pytest.mark.asyncio
    async def test_start_and_stop_background_loop(self, loop_components) -> None:
        """10. Background loop starts, executes cycles, and stops cleanly."""
        control_loop, _, _, _ = loop_components
        control_loop.cycle_delay = 0.01

        await control_loop.start_background(max_cycles=10)
        assert control_loop.is_running is True

        # Let it run several cycles
        await asyncio.sleep(0.08)
        assert control_loop.current_cycle > 0

        await control_loop.stop()
        assert control_loop.is_running is False
        cycle_count_after_stop = control_loop.current_cycle

        # Ensure no further cycles run
        await asyncio.sleep(0.05)
        assert control_loop.current_cycle == cycle_count_after_stop

    @REQUIRES_SUMO
    @pytest.mark.asyncio
    async def test_prevention_of_duplicate_loops(self, loop_components) -> None:
        """11. Starting background loop while already running raises RuntimeError."""
        control_loop, _, _, _ = loop_components
        control_loop.cycle_delay = 0.05

        await control_loop.start_background(max_cycles=10)
        try:
            with pytest.raises(RuntimeError) as exc_info:
                await control_loop.start_background(max_cycles=5)
            assert "already running" in str(exc_info.value)
        finally:
            await control_loop.stop()

    @REQUIRES_SUMO
    def test_callable_decision_adapter(self, loop_components) -> None:
        """12. CallableDecisionAdapter correctly wraps a raw function as decision engine."""
        control_loop, _, _, _ = loop_components

        def my_policy(states: dict[str, TrafficState]) -> SignalAction | None:
            if "I1" in states:
                return SignalAction(
                    target="I1",
                    green_duration=35.0,
                    source="FALLBACK",
                    timestamp=datetime.now(timezone.utc),
                )
            return None

        control_loop.set_decision_engine(CallableDecisionAdapter(my_policy))
        result = control_loop.step_cycle()
        assert result.actions_attempted == 1
        assert result.success is True
        assert result.action_results[0]["target"] == "I1"
