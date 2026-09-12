"""M2 Action Actuation and Dispatcher Layer for Urban Grid.

Translates high-level M1 Action contracts into concrete TraCI mutations in SUMO:
- SignalAction -> SignalActuator -> TraCI traffic-light program & duration adjustment
- RouteAction  -> RouteActuator  -> TraCI vehicle rerouting
- ActionDispatcher -> Unified M2 entry point ensuring M1 never calls TraCI directly
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pydantic import BaseModel, Field

from shared.schemas.control_mode import ControlMode
from shared.schemas.route_action import RouteAction
from shared.schemas.signal_action import ActionSource, SignalAction
from simulation.sumo.traci_bridge import TraCIBridge, TraCIBridgeError


# =============================================================================
# Actuation Exceptions
# =============================================================================


class ActuationError(Exception):
    """Base exception for all simulation actuation failures."""
    pass


class ModeRestrictedActionError(ActuationError):
    """Raised when an action source is restricted under the active ControlMode."""
    pass



class SimulationDisconnectedError(ActuationError):
    """Raised when actuation is attempted while TraCI is disconnected."""
    pass


class UnknownTrafficLightError(ActuationError):
    """Raised when target traffic light ID is not found in the simulation."""
    pass


class InvalidSignalDurationError(ActuationError):
    """Raised when green_duration violates safety or timing bounds."""
    pass


class SignalActuationError(ActuationError):
    """Raised when TraCI fails during signal timing adjustment."""
    pass


class UnknownVehicleError(ActuationError):
    """Raised when target vehicle ID is not currently active in simulation."""
    pass


class InvalidRouteEdgeError(ActuationError):
    """Raised when an edge in the supplied route does not exist in network."""
    pass


class InvalidRouteError(ActuationError):
    """Raised when the route is topologically disconnected or inapplicable."""
    pass


class RouteActuationError(ActuationError):
    """Raised when TraCI fails during vehicle rerouting."""
    pass


# =============================================================================
# Actuation Result Models
# =============================================================================


class SignalActuationResult(BaseModel):
    """Result of applying a SignalAction."""

    success: bool = Field(description="Whether the signal actuation succeeded.")
    target: str = Field(description="Target traffic light ID.")
    applied_duration: float = Field(description="Duration in seconds applied to signal logic.")
    current_phase: str = Field(description="Name of current phase at actuation time.")
    applied_to: str = Field(description="Whether applied to 'active_green' or 'upcoming_green'.")
    source: ActionSource = Field(description="Source that originated the action.")
    message: str = Field(description="Human-readable actuation summary.")


class RouteActuationResult(BaseModel):
    """Result of applying a RouteAction."""

    success: bool = Field(description="Whether the route actuation succeeded.")
    target: str = Field(description="Target vehicle ID.")
    applied_route: list[str] = Field(description="The newly applied route edge list.")
    previous_route: list[str] = Field(description="The vehicle's route prior to actuation.")
    source: ActionSource = Field(description="Source that originated the action.")
    message: str = Field(description="Human-readable actuation summary.")


# =============================================================================
# Signal Actuator
# =============================================================================

DEFAULT_MIN_GREEN_DURATION: float = 5.0
DEFAULT_MAX_GREEN_DURATION: float = 180.0


class SignalActuator:
    """M2-owned actuator applying SignalAction to SUMO traffic lights via TraCI."""

    def __init__(
        self,
        bridge: TraCIBridge,
        min_green_duration: float = DEFAULT_MIN_GREEN_DURATION,
        max_green_duration: float = DEFAULT_MAX_GREEN_DURATION,
    ) -> None:
        self._bridge = bridge
        self._min_green = min_green_duration
        self._max_green = max_green_duration

    @property
    def bridge(self) -> TraCIBridge:
        return self._bridge

    @property
    def min_green_duration(self) -> float:
        return self._min_green

    @property
    def max_green_duration(self) -> float:
        return self._max_green

    def apply(self, action: SignalAction) -> SignalActuationResult:
        """Validate and apply a SignalAction recommendation to the simulation.

        Args:
            action: Validated SignalAction contract.

        Returns:
            SignalActuationResult describing the outcome.

        Raises:
            SimulationDisconnectedError: If TraCI is not connected.
            UnknownTrafficLightError: If target is not a known traffic light.
            InvalidSignalDurationError: If green_duration violates bounds.
            SignalActuationError: If TraCI command fails.
        """
        if not self._bridge.is_connected:
            raise SimulationDisconnectedError("Cannot actuate traffic signal: SUMO is not connected.")

        conn = self._bridge.raw_connection

        # 1. Validate target traffic light exists
        try:
            valid_tls = set(conn.trafficlight.getIDList())
        except Exception as exc:
            raise SignalActuationError(f"Failed to query traffic lights from TraCI: {exc}") from exc

        if action.target not in valid_tls:
            raise UnknownTrafficLightError(
                f"Traffic light target '{action.target}' is unknown. Valid targets: {sorted(valid_tls)}"
            )

        # 2. Validate green_duration against sensible SUMO/control constraints
        if action.green_duration < self._min_green or action.green_duration > self._max_green:
            raise InvalidSignalDurationError(
                f"green_duration {action.green_duration}s is invalid. "
                f"Must be between {self._min_green}s and {self._max_green}s."
            )

        # 3. Determine current signal phase/state
        try:
            current_phase_idx = conn.trafficlight.getPhase(action.target)
            current_phase_name = conn.trafficlight.getPhaseName(action.target)
            current_state_str = conn.trafficlight.getRedYellowGreenState(action.target)
            logics = conn.trafficlight.getAllProgramLogics(action.target)
        except Exception as exc:
            raise SignalActuationError(
                f"Failed to inspect phase for traffic light '{action.target}': {exc}"
            ) from exc

        if not logics:
            raise SignalActuationError(f"No program logics found for traffic light '{action.target}'.")

        logic = logics[0]
        is_green = "GREEN" in current_phase_name.upper() or "G" in current_state_str or "g" in current_state_str

        # 4. Apply requested green duration through TraCI
        try:
            if is_green:
                # Active phase is GREEN: update logic program definition and active remaining phase duration
                logic.phases[current_phase_idx].duration = float(action.green_duration)
                conn.trafficlight.setProgramLogic(action.target, logic)
                conn.trafficlight.setPhaseDuration(action.target, float(action.green_duration))
                applied_to = "active_green"
            else:
                # Active phase is YELLOW (clearance): preserve yellow safety clearance,
                # find and update the upcoming green phase in the logic definition.
                target_green_idx = None
                for offset in range(1, len(logic.phases) + 1):
                    cand_idx = (current_phase_idx + offset) % len(logic.phases)
                    cand_phase = logic.phases[cand_idx]
                    if "GREEN" in cand_phase.name.upper() or "G" in cand_phase.state or "g" in cand_phase.state:
                        target_green_idx = cand_idx
                        break

                if target_green_idx is None:
                    target_green_idx = (current_phase_idx + 1) % len(logic.phases)

                logic.phases[target_green_idx].duration = float(action.green_duration)
                conn.trafficlight.setProgramLogic(action.target, logic)
                applied_to = "upcoming_green"
        except Exception as exc:
            raise SignalActuationError(
                f"TraCI failed to apply green duration to '{action.target}': {exc}"
            ) from exc

        return SignalActuationResult(
            success=True,
            target=action.target,
            applied_duration=action.green_duration,
            current_phase=current_phase_name,
            applied_to=applied_to,
            source=action.source,
            message=(
                f"Applied green duration {action.green_duration}s to '{action.target}' "
                f"({applied_to}: {current_phase_name})"
            ),
        )


# =============================================================================
# Route Actuator
# =============================================================================


class RouteActuator:
    """M2-owned actuator applying RouteAction to SUMO vehicles via TraCI."""

    def __init__(self, bridge: TraCIBridge) -> None:
        self._bridge = bridge

    @property
    def bridge(self) -> TraCIBridge:
        return self._bridge

    def apply(self, action: RouteAction) -> RouteActuationResult:
        """Validate and apply a RouteAction reroute directive to the simulation.

        Args:
            action: Validated RouteAction contract.

        Returns:
            RouteActuationResult describing the outcome.

        Raises:
            SimulationDisconnectedError: If TraCI is not connected.
            UnknownVehicleError: If target is not an active vehicle.
            InvalidRouteEdgeError: If an edge does not exist in the network.
            InvalidRouteError: If route is disconnected or rejected by SUMO.
            RouteActuationError: If TraCI command fails.
        """
        if not self._bridge.is_connected:
            raise SimulationDisconnectedError("Cannot actuate vehicle route: SUMO is not connected.")

        conn = self._bridge.raw_connection

        # 1. Validate vehicle exists and is active
        try:
            active_vehicles = set(conn.vehicle.getIDList())
        except Exception as exc:
            raise RouteActuationError(f"Failed to query vehicle list from TraCI: {exc}") from exc

        if action.target not in active_vehicles:
            raise UnknownVehicleError(
                f"Vehicle '{action.target}' is not active or does not exist in simulation."
            )

        # 2. Validate every supplied edge exists in the current SUMO network
        try:
            network_edges = set(conn.edge.getIDList())
        except Exception as exc:
            raise RouteActuationError(f"Failed to query edges from TraCI: {exc}") from exc

        for edge in action.route:
            if edge not in network_edges:
                raise InvalidRouteEdgeError(
                    f"Edge '{edge}' does not exist in the SUMO network."
                )

        # 3. Retrieve previous route for logging and result reporting
        try:
            previous_route = list(conn.vehicle.getRoute(action.target))
        except Exception as exc:
            raise RouteActuationError(
                f"Failed to read current route for vehicle '{action.target}': {exc}"
            ) from exc

        # 4. Apply route through TraCI
        try:
            conn.vehicle.setRoute(action.target, action.route)
        except Exception as exc:
            raise InvalidRouteError(
                f"Route cannot be applied to vehicle '{action.target}': {exc}"
            ) from exc

        return RouteActuationResult(
            success=True,
            target=action.target,
            applied_route=list(action.route),
            previous_route=previous_route,
            source=action.source,
            message=(
                f"Successfully rerouted vehicle '{action.target}' "
                f"from {len(previous_route)} edges to {len(action.route)} edges."
            ),
        )


# =============================================================================
# Action Dispatcher
# =============================================================================


class ActionDispatcher:
    """M2-owned dispatcher coordinating incoming M1 control actions to TraCI actuators.

    Boundary:
    M1 -> SignalAction / RouteAction -> ActionDispatcher -> Actuator -> TraCI -> SUMO
    """

    def __init__(
        self,
        bridge: TraCIBridge,
        signal_actuator: SignalActuator | None = None,
        route_actuator: RouteActuator | None = None,
        mode: ControlMode = ControlMode.AUTO,
    ) -> None:
        self._bridge = bridge
        self._signal_actuator = signal_actuator or SignalActuator(bridge)
        self._route_actuator = route_actuator or RouteActuator(bridge)
        self._mode: ControlMode = mode

    @property
    def mode(self) -> ControlMode:
        """Return the current control mode governing dispatch enforcement."""
        return self._mode

    @mode.setter
    def mode(self, new_mode: ControlMode) -> None:
        """Set the control mode for dispatch enforcement."""
        if not isinstance(new_mode, ControlMode):
            raise ValueError(f"Invalid control mode '{new_mode}'. Must be an instance of ControlMode.")
        self._mode = new_mode

    @property
    def signal_actuator(self) -> SignalActuator:
        """Return the managed SignalActuator instance."""
        return self._signal_actuator

    @property
    def route_actuator(self) -> RouteActuator:
        """Return the managed RouteActuator instance."""
        return self._route_actuator

    def _check_mode_permission(self, action: SignalAction | RouteAction) -> None:
        """Verify whether the action source is permitted under current control mode."""
        if self._mode == ControlMode.MANUAL:
            if action.source == ActionSource.AI:
                raise ModeRestrictedActionError(
                    f"Action from source '{action.source.value}' is restricted in MANUAL mode."
                )
        elif self._mode == ControlMode.EMERGENCY:
            if action.source == ActionSource.AI:
                raise ModeRestrictedActionError(
                    f"AI action from source '{action.source.value}' cannot override EMERGENCY mode."
                )

    def apply_signal(self, action: SignalAction) -> SignalActuationResult:
        """Direct entry point for SignalAction."""
        self._check_mode_permission(action)
        return self._signal_actuator.apply(action)

    def apply_route(self, action: RouteAction) -> RouteActuationResult:
        """Direct entry point for RouteAction."""
        self._check_mode_permission(action)
        return self._route_actuator.apply(action)

    def dispatch(
        self, action: SignalAction | RouteAction
    ) -> SignalActuationResult | RouteActuationResult:
        """Dynamically dispatch any supported Action contract to its actuator.

        Args:
            action: Either SignalAction or RouteAction.

        Returns:
            SignalActuationResult or RouteActuationResult.

        Raises:
            TypeError: If action is not a recognized Action schema.
            ActuationError: Subclass error if actuation fails.
        """
        if isinstance(action, SignalAction):
            return self.apply_signal(action)
        elif isinstance(action, RouteAction):
            return self.apply_route(action)
        else:
            raise TypeError(
                f"Unsupported action type '{type(action).__name__}'. "
                f"Expected SignalAction or RouteAction."
            )

