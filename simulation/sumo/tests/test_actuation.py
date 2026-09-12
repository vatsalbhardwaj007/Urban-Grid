"""Unit and integration tests for M2 Action actuation and ActionDispatcher."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from shared.schemas.route_action import ActionSource, RouteAction
from shared.schemas.signal_action import SignalAction
from simulation.sumo.actuation import (
    ActionDispatcher,
    InvalidRouteEdgeError,
    InvalidRouteError,
    InvalidSignalDurationError,
    RouteActuationResult,
    RouteActuator,
    SignalActuationResult,
    SignalActuator,
    SimulationDisconnectedError,
    UnknownTrafficLightError,
    UnknownVehicleError,
)
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
def disconnected_bridge():
    """Return an unstarted/disconnected TraCIBridge."""
    return TraCIBridge()


# =============================================================================
# PART 1: Signal Actuator Tests
# =============================================================================


class TestSignalActuator:
    """Test suite for SignalActuator."""

    @REQUIRES_SUMO
    def test_valid_signal_action_succeeds(self, running_bridge: TraCIBridge) -> None:
        """1. Valid SignalAction is successfully applied to a known traffic light."""
        actuator = SignalActuator(running_bridge)
        action = SignalAction(
            target="I1",
            green_duration=45.0,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        result = actuator.apply(action)
        assert isinstance(result, SignalActuationResult)
        assert result.success is True
        assert result.target == "I1"
        assert result.applied_duration == 45.0
        assert result.source == ActionSource.AI
        assert result.applied_to in {"active_green", "upcoming_green"}

    @REQUIRES_SUMO
    def test_signal_action_all_four_intersections(self, running_bridge: TraCIBridge) -> None:
        """2. Valid SignalActions can be applied to all 4 intersections (I1-I4)."""
        actuator = SignalActuator(running_bridge)
        for iid in ["I1", "I2", "I3", "I4"]:
            action = SignalAction(
                target=iid,
                green_duration=35.0,
                source=ActionSource.FALLBACK,
                timestamp=datetime.now(timezone.utc),
            )
            res = actuator.apply(action)
            assert res.success is True
            assert res.target == iid

    @REQUIRES_SUMO
    def test_unknown_traffic_light_target_raises_error(self, running_bridge: TraCIBridge) -> None:
        """3. Targeting a non-existent traffic light raises UnknownTrafficLightError."""
        actuator = SignalActuator(running_bridge)
        action = SignalAction(
            target="I99",
            green_duration=30.0,
            source="MANUAL",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(UnknownTrafficLightError) as exc_info:
            actuator.apply(action)
        assert "I99" in str(exc_info.value)

    @REQUIRES_SUMO
    @pytest.mark.parametrize("invalid_duration", [1.0, 4.9, 185.0, 300.0])
    def test_invalid_signal_duration_bounds_rejected(
        self, running_bridge: TraCIBridge, invalid_duration: float
    ) -> None:
        """4. Duration violating min (5.0s) or max (180.0s) bounds raises InvalidSignalDurationError."""
        actuator = SignalActuator(running_bridge)
        action = SignalAction(
            target="I1",
            green_duration=invalid_duration,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(InvalidSignalDurationError) as exc_info:
            actuator.apply(action)
        assert str(invalid_duration) in str(exc_info.value)

    def test_disconnected_sumo_raises_error(self, disconnected_bridge: TraCIBridge) -> None:
        """5. Applying SignalAction when TraCI is disconnected raises SimulationDisconnectedError."""
        actuator = SignalActuator(disconnected_bridge)
        action = SignalAction(
            target="I1",
            green_duration=30.0,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(SimulationDisconnectedError):
            actuator.apply(action)

    @REQUIRES_SUMO
    def test_actual_traci_signal_mutation(self, running_bridge: TraCIBridge) -> None:
        """6. Verifies that TraCI signal state actually mutates in SUMO."""
        conn = running_bridge.raw_connection
        actuator = SignalActuator(running_bridge)

        # Initial duration in program is 31.0
        assert conn.trafficlight.getPhaseDuration("I1") == 31.0

        # Actuate green duration to 55.0s
        action = SignalAction(
            target="I1",
            green_duration=55.0,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )
        res = actuator.apply(action)
        assert res.success is True
        assert res.applied_to == "active_green"

        # Check that TraCI reported phase duration was updated
        assert conn.trafficlight.getPhaseDuration("I1") == 55.0
        assert conn.trafficlight.getNextSwitch("I1") == 55.0

    @REQUIRES_SUMO
    def test_signal_mutation_during_yellow_preserves_clearance(self, running_bridge: TraCIBridge) -> None:
        """7. Actuation during yellow clearance updates upcoming green without changing yellow."""
        conn = running_bridge.raw_connection
        actuator = SignalActuator(running_bridge)

        # Step into yellow phase (NS_GREEN is 31s, at t=32s it enters NS_YELLOW)
        running_bridge.step_many(32)
        phase_name = conn.trafficlight.getPhaseName("I1")
        assert "YELLOW" in phase_name

        # Yellow duration before actuation
        yellow_duration_before = conn.trafficlight.getPhaseDuration("I1")
        assert yellow_duration_before == 4.0

        action = SignalAction(
            target="I1",
            green_duration=60.0,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )
        res = actuator.apply(action)
        assert res.success is True
        assert res.applied_to == "upcoming_green"

        # Yellow duration remains unchanged
        assert conn.trafficlight.getPhaseDuration("I1") == 4.0

        # Step through yellow into the new green phase (4s yellow -> t=36)
        running_bridge.step_many(5)
        new_phase_name = conn.trafficlight.getPhaseName("I1")
        assert "GREEN" in new_phase_name
        assert conn.trafficlight.getPhaseDuration("I1") == 60.0


# =============================================================================
# PART 2: Route Actuator Tests
# =============================================================================


class TestRouteActuator:
    """Test suite for RouteActuator."""

    @REQUIRES_SUMO
    def test_valid_route_action_succeeds(self, running_bridge: TraCIBridge) -> None:
        """1. Valid RouteAction successfully reroutes an active vehicle to the alternate route."""
        # Step once to insert initial flow vehicles
        running_bridge.step()

        actuator = RouteActuator(running_bridge)
        target_veh = "flow_norm_prim.0"

        # Alternate route from routes.rou.xml: route_alternate
        alternate_route = ["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"]
        action = RouteAction(
            target=target_veh,
            route=alternate_route,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        res = actuator.apply(action)
        assert isinstance(res, RouteActuationResult)
        assert res.success is True
        assert res.target == target_veh
        assert res.applied_route == alternate_route
        assert res.previous_route == ["E_W1_I1", "E_I1_I2", "E_I2_I4", "E_I4_E4"]
        assert res.source == ActionSource.AI

    @REQUIRES_SUMO
    def test_actual_traci_route_mutation(self, running_bridge: TraCIBridge) -> None:
        """2. Verifies TraCI vehicle route changes to match the new route."""
        running_bridge.step()
        conn = running_bridge.raw_connection
        target_veh = "flow_norm_prim.0"

        actuator = RouteActuator(running_bridge)
        alternate_route = ["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"]
        action = RouteAction(
            target=target_veh,
            route=alternate_route,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        actuator.apply(action)
        # Verify via direct TraCI query
        assert list(conn.vehicle.getRoute(target_veh)) == alternate_route

    @REQUIRES_SUMO
    def test_unknown_vehicle_raises_error(self, running_bridge: TraCIBridge) -> None:
        """3. Rerouting an inactive or non-existent vehicle raises UnknownVehicleError."""
        actuator = RouteActuator(running_bridge)
        action = RouteAction(
            target="veh_nonexistent_99",
            route=["E_W1_I1", "E_I1_I2", "E_I2_I4", "E_I4_E4"],
            source="MANUAL",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(UnknownVehicleError) as exc_info:
            actuator.apply(action)
        assert "veh_nonexistent_99" in str(exc_info.value)

    @REQUIRES_SUMO
    def test_unknown_edge_raises_error(self, running_bridge: TraCIBridge) -> None:
        """4. Providing an edge not in the SUMO network raises InvalidRouteEdgeError."""
        running_bridge.step()
        actuator = RouteActuator(running_bridge)
        target_veh = "flow_norm_prim.0"

        action = RouteAction(
            target=target_veh,
            route=["E_W1_I1", "E_FAKE_EDGE_XYZ", "E_I4_E4"],
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(InvalidRouteEdgeError) as exc_info:
            actuator.apply(action)
        assert "E_FAKE_EDGE_XYZ" in str(exc_info.value)

    @REQUIRES_SUMO
    def test_disconnected_route_raises_error(self, running_bridge: TraCIBridge) -> None:
        """5. Supplying topologically disconnected edges raises InvalidRouteError."""
        running_bridge.step()
        actuator = RouteActuator(running_bridge)
        target_veh = "flow_norm_prim.0"

        # E_W1_I1 and E_I4_E4 are disconnected (missing intermediate edges)
        action = RouteAction(
            target=target_veh,
            route=["E_W1_I1", "E_I4_E4"],
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(InvalidRouteError) as exc_info:
            actuator.apply(action)
        assert "cannot be applied" in str(exc_info.value).lower() or "no connection" in str(exc_info.value).lower()

    def test_disconnected_sumo_raises_error(self, disconnected_bridge: TraCIBridge) -> None:
        """6. Applying RouteAction when TraCI is disconnected raises SimulationDisconnectedError."""
        actuator = RouteActuator(disconnected_bridge)
        action = RouteAction(
            target="flow_norm_prim.0",
            route=["E_W1_I1", "E_I1_I2"],
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(SimulationDisconnectedError):
            actuator.apply(action)


# =============================================================================
# PART 3: Action Dispatcher Tests
# =============================================================================


class TestActionDispatcher:
    """Test suite for ActionDispatcher."""

    @REQUIRES_SUMO
    def test_dispatcher_routes_signal_action(self, running_bridge: TraCIBridge) -> None:
        """1. ActionDispatcher correctly dispatches SignalAction to SignalActuator."""
        dispatcher = ActionDispatcher(running_bridge)
        action = SignalAction(
            target="I2",
            green_duration=40.0,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        res = dispatcher.dispatch(action)
        assert isinstance(res, SignalActuationResult)
        assert res.success is True
        assert res.target == "I2"
        assert res.applied_duration == 40.0

    @REQUIRES_SUMO
    def test_dispatcher_routes_route_action(self, running_bridge: TraCIBridge) -> None:
        """2. ActionDispatcher correctly dispatches RouteAction to RouteActuator."""
        running_bridge.step()
        dispatcher = ActionDispatcher(running_bridge)
        target_veh = "flow_norm_prim.0"

        action = RouteAction(
            target=target_veh,
            route=["E_W1_I1", "E_I1_I3", "E_I3_I4", "E_I4_E4"],
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        res = dispatcher.dispatch(action)
        assert isinstance(res, RouteActuationResult)
        assert res.success is True
        assert res.target == target_veh

    def test_dispatcher_unsupported_type_raises_type_error(self, disconnected_bridge: TraCIBridge) -> None:
        """3. Passing an unsupported object raises TypeError."""
        dispatcher = ActionDispatcher(disconnected_bridge)

        with pytest.raises(TypeError) as exc_info:
            dispatcher.dispatch("not_an_action")  # type: ignore[arg-type]
        assert "Unsupported action type" in str(exc_info.value)

    @REQUIRES_SUMO
    def test_dispatcher_safe_error_propagation(self, running_bridge: TraCIBridge) -> None:
        """4. Actuation failure produces expected controlled exception without crashing."""
        dispatcher = ActionDispatcher(running_bridge)
        bad_action = SignalAction(
            target="I_NONEXISTENT",
            green_duration=30.0,
            source="AI",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(UnknownTrafficLightError):
            dispatcher.dispatch(bad_action)
