"""Focused integration and unit tests for M2 Control Modes (AUTO, MANUAL, EMERGENCY).

Verifies the 15 core requirements:
1. default mode is AUTO
2. reading current mode
3. changing AUTO -> MANUAL
4. changing MANUAL -> AUTO
5. entering EMERGENCY (from AUTO and from MANUAL)
6. leaving EMERGENCY (to AUTO and to MANUAL)
7. AI actions execute in AUTO
8. AI actions do NOT execute in MANUAL
9. AI actions do NOT override EMERGENCY
10. manual signal action works in MANUAL
11. manual route action works in MANUAL
12. invalid mode is rejected
13. mode changes do not create duplicate loops
14. existing control-loop behavior remains intact
15. existing M1 integration remains intact
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import pytest

from shared.schemas.control_mode import ControlMode
from shared.schemas.route_action import RouteAction
from shared.schemas.signal_action import ActionSource, SignalAction
from shared.schemas.traffic_state import TrafficState
from simulation.sumo.actuation import (
    ActionDispatcher,
    ModeRestrictedActionError,
    SignalActuationResult,
)
from simulation.sumo.control_loop import (
    CallableDecisionAdapter,
    ControlCycleResult,
    NullDecisionEngine,
    SimulationControlLoop,
)
from simulation.sumo.m1_adapter import HAS_M1, RealM1DecisionEngine
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


class TestControlModes:
    """Test suite for AUTO, MANUAL, and EMERGENCY control modes."""

    # 1. Default mode
    def test_default_mode(self, loop_components) -> None:
        """1. Default operating mode is AUTO on both ControlLoop and ActionDispatcher."""
        control_loop, _, dispatcher, _ = loop_components
        assert control_loop.mode == ControlMode.AUTO
        assert dispatcher.mode == ControlMode.AUTO
        assert control_loop.previous_mode is None

    # 2. Reading current mode
    def test_reading_current_mode(self, loop_components) -> None:
        """2. Mode and previous_mode properties accurately reflect current state."""
        control_loop, _, _, _ = loop_components
        assert control_loop.mode == ControlMode.AUTO
        assert isinstance(control_loop.mode, ControlMode)

    # 3. Changing AUTO -> MANUAL
    def test_changing_auto_to_manual(self, loop_components) -> None:
        """3. Transitioning AUTO -> MANUAL updates state and synchronizes dispatcher."""
        control_loop, _, dispatcher, _ = loop_components
        new_mode, prev_mode = control_loop.set_mode(ControlMode.MANUAL)
        assert new_mode == ControlMode.MANUAL
        assert prev_mode == ControlMode.AUTO
        assert control_loop.mode == ControlMode.MANUAL
        assert control_loop.previous_mode == ControlMode.AUTO
        assert dispatcher.mode == ControlMode.MANUAL

    # 4. Changing MANUAL -> AUTO
    def test_changing_manual_to_auto(self, loop_components) -> None:
        """4. Transitioning MANUAL -> AUTO updates state and synchronizes dispatcher."""
        control_loop, _, dispatcher, _ = loop_components
        control_loop.set_mode(ControlMode.MANUAL)
        new_mode, prev_mode = control_loop.set_mode(ControlMode.AUTO)
        assert new_mode == ControlMode.AUTO
        assert prev_mode == ControlMode.MANUAL
        assert control_loop.mode == ControlMode.AUTO
        assert control_loop.previous_mode == ControlMode.MANUAL
        assert dispatcher.mode == ControlMode.AUTO

    # 5. Entering EMERGENCY
    def test_entering_emergency(self, loop_components) -> None:
        """5. Entering EMERGENCY from AUTO and from MANUAL."""
        control_loop, _, dispatcher, _ = loop_components
        # From AUTO
        new_mode, prev = control_loop.set_mode(ControlMode.EMERGENCY)
        assert new_mode == ControlMode.EMERGENCY
        assert prev == ControlMode.AUTO
        assert dispatcher.mode == ControlMode.EMERGENCY

        # From MANUAL
        control_loop.set_mode(ControlMode.MANUAL)
        new_mode, prev = control_loop.set_mode(ControlMode.EMERGENCY)
        assert new_mode == ControlMode.EMERGENCY
        assert prev == ControlMode.MANUAL
        assert dispatcher.mode == ControlMode.EMERGENCY

    # 6. Leaving EMERGENCY
    def test_leaving_emergency(self, loop_components) -> None:
        """6. Leaving EMERGENCY returns safely to selected normal mode (AUTO or MANUAL)."""
        control_loop, _, dispatcher, _ = loop_components
        control_loop.set_mode(ControlMode.EMERGENCY)

        # Transition EMERGENCY -> AUTO
        new_mode, prev = control_loop.set_mode(ControlMode.AUTO)
        assert new_mode == ControlMode.AUTO
        assert prev == ControlMode.EMERGENCY
        assert dispatcher.mode == ControlMode.AUTO

        # Transition AUTO -> EMERGENCY -> MANUAL
        control_loop.set_mode(ControlMode.EMERGENCY)
        new_mode, prev = control_loop.set_mode(ControlMode.MANUAL)
        assert new_mode == ControlMode.MANUAL
        assert prev == ControlMode.EMERGENCY
        assert dispatcher.mode == ControlMode.MANUAL

    # 7. AI actions execute in AUTO
    @REQUIRES_SUMO
    def test_ai_actions_execute_in_auto(self, loop_components) -> None:
        """7. In AUTO mode, M1 AI-generated actions are automatically dispatched and executed."""
        control_loop, _, _, _ = loop_components

        def ai_decide(states: dict[str, TrafficState]) -> SignalAction:
            return SignalAction(
                target="I1",
                green_duration=35.0,
                source=ActionSource.AI,
                timestamp=datetime.now(timezone.utc),
            )

        control_loop.set_decision_engine(CallableDecisionAdapter(ai_decide))
        control_loop.set_mode(ControlMode.AUTO)

        result = control_loop.step_cycle()
        assert result.mode == ControlMode.AUTO
        assert result.actions_attempted == 1
        assert len(result.action_results) == 1
        assert result.action_results[0]["success"] is True
        assert result.action_results[0]["target"] == "I1"
        assert result.action_results[0]["source"] == "AI"

    # 8. AI actions do NOT execute in MANUAL
    @REQUIRES_SUMO
    def test_ai_actions_do_not_execute_in_manual(self, loop_components) -> None:
        """8. In MANUAL mode, AI decisions are suppressed from automated actuation."""
        control_loop, _, dispatcher, _ = loop_components

        ai_called = False

        def ai_decide(states: dict[str, TrafficState]) -> SignalAction:
            nonlocal ai_called
            ai_called = True
            return SignalAction(
                target="I1",
                green_duration=35.0,
                source=ActionSource.AI,
                timestamp=datetime.now(timezone.utc),
            )

        control_loop.set_decision_engine(CallableDecisionAdapter(ai_decide))
        control_loop.set_mode(ControlMode.MANUAL)

        result = control_loop.step_cycle()
        assert result.mode == ControlMode.MANUAL
        assert ai_called is True  # M1 can still observe states
        assert result.actions_attempted == 0  # But actions are NOT dispatched
        assert len(result.action_results) == 0

        # Also verify that if an AI action attempts direct dispatch, dispatcher rejects it
        ai_action = SignalAction(
            target="I1",
            green_duration=35.0,
            source=ActionSource.AI,
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(ModeRestrictedActionError, match="restricted in MANUAL"):
            dispatcher.dispatch(ai_action)

    # 9. AI actions do NOT override EMERGENCY
    @REQUIRES_SUMO
    def test_ai_actions_do_not_override_emergency(self, loop_components) -> None:
        """9. In EMERGENCY mode, normal AI control is overridden by deterministic corridor policy."""
        control_loop, _, dispatcher, _ = loop_components

        def ai_decide(states: dict[str, TrafficState]) -> SignalAction:
            return SignalAction(
                target="I1",
                green_duration=20.0,
                source=ActionSource.AI,
                timestamp=datetime.now(timezone.utc),
            )

        control_loop.set_decision_engine(CallableDecisionAdapter(ai_decide))
        control_loop.set_mode(ControlMode.EMERGENCY)

        result = control_loop.step_cycle()
        assert result.mode == ControlMode.EMERGENCY
        # Emergency policy dispatched FALLBACK actions for all 4 intersections (I1-I4)
        assert result.actions_attempted == 4
        targets = [res["target"] for res in result.action_results]
        assert sorted(targets) == ["I1", "I2", "I3", "I4"]
        for res in result.action_results:
            assert res["success"] is True
            assert res["applied_duration"] == 60.0
            assert res["source"] == "FALLBACK"

        # Direct AI action attempted during EMERGENCY is rejected
        ai_action = SignalAction(
            target="I1",
            green_duration=20.0,
            source=ActionSource.AI,
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(ModeRestrictedActionError, match="cannot override EMERGENCY"):
            dispatcher.dispatch(ai_action)

    # 10. Manual signal action works in MANUAL
    @REQUIRES_SUMO
    def test_manual_signal_action_works_in_manual(self, loop_components) -> None:
        """10. Operator manual signal actions actuate successfully while in MANUAL mode."""
        control_loop, _, dispatcher, _ = loop_components
        control_loop.set_mode(ControlMode.MANUAL)

        manual_action = SignalAction(
            target="I1",
            green_duration=45.0,
            source=ActionSource.MANUAL,
            timestamp=datetime.now(timezone.utc),
        )
        res = dispatcher.dispatch(manual_action)
        assert isinstance(res, SignalActuationResult)
        assert res.success is True
        assert res.target == "I1"
        assert res.applied_duration == 45.0
        assert res.source == ActionSource.MANUAL

    # 11. Manual route action works in MANUAL
    @REQUIRES_SUMO
    def test_manual_route_action_works_in_manual(self, loop_components) -> None:
        """11. Operator manual route actions actuate successfully while in MANUAL mode."""
        control_loop, _, dispatcher, _ = loop_components
        control_loop.set_mode(ControlMode.MANUAL)

        # Step once to insert flow vehicle
        control_loop.provider.bridge.step()

        manual_route = RouteAction(
            target="flow_norm_prim.0",
            route=["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"],
            source=ActionSource.MANUAL,
            timestamp=datetime.now(timezone.utc),
        )
        res = dispatcher.dispatch(manual_route)
        assert res.success is True
        assert res.target == "flow_norm_prim.0"
        assert res.applied_route == ["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"]
        assert res.source == ActionSource.MANUAL

    # 12. Invalid mode is rejected
    def test_invalid_mode_is_rejected(self, loop_components) -> None:
        """12. Providing an invalid mode raises a ValueError without modifying state."""
        control_loop, _, dispatcher, _ = loop_components
        initial_mode = control_loop.mode

        with pytest.raises(ValueError, match="Invalid control mode"):
            control_loop.set_mode("SUPER_MODE")

        with pytest.raises(ValueError, match="Invalid control mode"):
            control_loop.set_mode(123)  # type: ignore

        # State remains unchanged
        assert control_loop.mode == initial_mode
        assert dispatcher.mode == initial_mode

        with pytest.raises(ValueError, match="Invalid control mode"):
            dispatcher.mode = "INVALID"  # type: ignore

    # 13. Mode changes do not create duplicate loops
    @pytest.mark.asyncio
    async def test_mode_changes_do_not_create_duplicate_loops(self, loop_components) -> None:
        """13. Changing mode does not restart loop tasks or create duplicate loops."""
        control_loop, _, _, _ = loop_components

        control_loop.cycle_delay = 0.01
        await control_loop.start_background(max_cycles=10)
        assert control_loop.is_running is True

        # Calling start_background while running is rejected
        with pytest.raises(RuntimeError, match="already running"):
            await control_loop.start_background()

        # Change mode while running
        task_before = control_loop._background_task
        control_loop.set_mode(ControlMode.MANUAL)
        task_after = control_loop._background_task

        # Task reference is identical (no duplicate task created)
        assert task_before is task_after

        # Clean shutdown
        await control_loop.stop()
        assert control_loop.is_running is False

    # 14. Existing control-loop behavior remains intact
    @REQUIRES_SUMO
    def test_existing_control_loop_behavior_remains_intact(self, loop_components) -> None:
        """14. Stepping, cycles, state collection, and error policies remain intact."""
        control_loop, provider, _, _ = loop_components
        t_start = provider.simulation_time

        results = control_loop.run_steps(3)
        assert len(results) == 3
        assert results[0].cycle == 1
        assert results[1].cycle == 2
        assert results[2].cycle == 3
        assert results[2].simulation_time == t_start + 3.0
        assert set(results[2].states.keys()) == {"I1", "I2", "I3", "I4"}

    # 15. Existing M1 integration remains intact
    @REQUIRES_SUMO
    def test_existing_m1_integration_remains_intact(self, loop_components) -> None:
        """15. RealM1DecisionEngine seamlessly integrates with SimulationControlLoop."""
        if not HAS_M1:
            pytest.skip("M1 module is not available in environment.")

        control_loop, _, _, running_bridge = loop_components
        real_engine = RealM1DecisionEngine(bridge=running_bridge)
        control_loop.set_decision_engine(real_engine)
        control_loop.set_mode(ControlMode.AUTO)

        result = control_loop.step_cycle()
        assert result.success is True
        assert result.cycle == 1
        assert set(result.states.keys()) == {"I1", "I2", "I3", "I4"}
