"""M2 Simulation and Control-Loop Orchestration Layer for Urban Grid.

Implements the closed loop:
TrafficState -> M1 decision boundary -> SignalAction / RouteAction -> ActionDispatcher -> TraCI / SUMO -> new TrafficState

Responsibilities:
- Advance SUMO simulation via TraCI bridge / TrafficStateProvider
- Acquire canonical TrafficState v1 observations
- Consult M1 Decision Engine via agreed DecisionEngineProtocol boundary
- Validate and dispatch interventions through ActionDispatcher
- Broadcast state updates over WebSocket
- Enforce simulation safety (configurable intervals, duplicate prevention, clean shutdown)
- Isolate M1 from direct TraCI access
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence, runtime_checkable

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pydantic import BaseModel, Field

from shared.schemas.control_mode import ControlMode
from shared.schemas.route_action import RouteAction
from shared.schemas.signal_action import ActionSource, SignalAction
from shared.schemas.traffic_state import TrafficState
from simulation.sumo.actuation import (
    ActionDispatcher,
    ActuationError,
    ModeRestrictedActionError,
    RouteActuationResult,
    SignalActuationResult,
    SimulationDisconnectedError,
)

from simulation.sumo.m1_adapter import RealM1DecisionEngine
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import TraCIBridgeError

logger = logging.getLogger("urbangrid.control_loop")


# =============================================================================
# M1 Decision Engine Interface Boundary
# =============================================================================


@runtime_checkable
class DecisionEngineProtocol(Protocol):
    """Agreed M1 Decision Engine protocol boundary.

    M1 intelligence modules must implement `decide(states)` returning either:
    - SignalAction
    - RouteAction
    - Sequence of SignalAction / RouteAction
    - None (no intervention)
    """

    def decide(
        self,
        states: dict[str, TrafficState],
    ) -> SignalAction | RouteAction | Sequence[SignalAction | RouteAction] | None:
        """Evaluate canonical traffic states and return control actions."""
        ...


class NullDecisionEngine:
    """Default passive decision engine performing no interventions.

    Used when M1 is not connected or for baseline traffic benchmarking.
    """

    def decide(
        self,
        states: dict[str, TrafficState],
    ) -> None:
        """Passively observe without intervening."""
        return None


class CallableDecisionAdapter:
    """Adapts any Python callable to DecisionEngineProtocol."""

    def __init__(
        self,
        func: Callable[
            [dict[str, TrafficState]],
            SignalAction | RouteAction | Sequence[SignalAction | RouteAction] | None,
        ],
    ) -> None:
        self._func = func

    def decide(
        self,
        states: dict[str, TrafficState],
    ) -> SignalAction | RouteAction | Sequence[SignalAction | RouteAction] | None:
        return self._func(states)


# =============================================================================
# Control Cycle Reporting Model
# =============================================================================


class ControlCycleResult(BaseModel):
    """Structured report of a single closed-loop control cycle."""

    cycle: int = Field(description="Sequential cycle index.")
    simulation_time: float = Field(description="SUMO simulation timestamp at the end of the cycle.")
    states: dict[str, TrafficState] = Field(description="Canonical TrafficState for all intersections.")
    mode: ControlMode = Field(default=ControlMode.AUTO, description="Active control mode during this cycle.")
    actions_attempted: int = Field(default=0, description="Total actions received from decision engine.")
    action_results: list[dict[str, Any]] = Field(
        default_factory=list, description="Results of successfully applied actions."
    )
    errors: list[str] = Field(
        default_factory=list, description="Errors or warnings encountered during actuation."
    )
    success: bool = Field(default=True, description="Whether the cycle executed without fatal crash.")



# =============================================================================
# Control Loop Orchestrator
# =============================================================================


class SimulationControlLoop:
    """M2 closed-loop simulation orchestrator.

    Executes: step SUMO -> collect TrafficState -> M1 decide -> ActionDispatcher -> repeat.
    """

    def __init__(
        self,
        provider: TrafficStateProvider,
        dispatcher: ActionDispatcher,
        decision_engine: DecisionEngineProtocol | None = None,
        broadcaster: Any | None = None,
        step_interval: int = 1,
        cycle_delay: float = 0.0,
        error_policy: str = "continue",
        mode: ControlMode = ControlMode.AUTO,
    ) -> None:
        """Initialize SimulationControlLoop.

        Args:
            provider: TrafficStateProvider for sensor queries and stepping.
            dispatcher: ActionDispatcher for applying actions through TraCI.
            decision_engine: M1 DecisionEngineProtocol implementation (defaults to NullDecisionEngine).
            broadcaster: Optional WebSocket broadcaster (ConnectionManager).
            step_interval: Number of SUMO simulation steps per cycle (default 1).
            cycle_delay: Real-world delay in seconds between cycles (default 0.0).
            error_policy: 'continue' (log error and proceed) or 'stop' (halt loop on error).
            mode: Initial ControlMode (default AUTO).
        """
        self._provider = provider
        self._dispatcher = dispatcher
        self._decision_engine: DecisionEngineProtocol = decision_engine or NullDecisionEngine()
        self._broadcaster = broadcaster
        self._step_interval = max(1, step_interval)
        self._cycle_delay = max(0.0, cycle_delay)
        self._error_policy = error_policy

        self._mode: ControlMode = mode
        self._previous_mode: ControlMode | None = None
        self._dispatcher.mode = self._mode

        self._is_running: bool = False
        self._current_cycle: int = 0
        self._background_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def mode(self) -> ControlMode:
        """Return the current system control mode (single source of truth)."""
        return self._mode

    @property
    def previous_mode(self) -> ControlMode | None:
        """Return the previous control mode prior to the latest transition."""
        return self._previous_mode

    def set_mode(self, mode: ControlMode | str) -> tuple[ControlMode, ControlMode | None]:
        """Safely transition system control mode and synchronize with dispatcher.

        Does not restart background loop or create duplicate background tasks.

        Args:
            mode: Target ControlMode (or valid string representation).

        Returns:
            Tuple of (new_mode, previous_mode).

        Raises:
            ValueError: If mode is not a valid ControlMode.
        """
        if isinstance(mode, str):
            try:
                mode = ControlMode(mode.upper())
            except ValueError:
                raise ValueError(
                    f"Invalid control mode '{mode}'. Allowed values: {[m.value for m in ControlMode]}"
                )
        elif not isinstance(mode, ControlMode):
            raise ValueError(
                f"Invalid control mode '{mode}'. Expected ControlMode enum."
            )

        if mode == self._mode:
            return self._mode, self._previous_mode

        prev = self._mode
        self._previous_mode = prev
        self._mode = mode
        self._dispatcher.mode = mode
        logger.info("Control mode transitioned: %s -> %s", prev.value, mode.value)
        return self._mode, self._previous_mode

    @property
    def provider(self) -> TrafficStateProvider:
        """Return the underlying TrafficStateProvider."""
        return self._provider

    @property
    def dispatcher(self) -> ActionDispatcher:
        """Return the underlying ActionDispatcher."""
        return self._dispatcher

    @property
    def decision_engine(self) -> DecisionEngineProtocol:
        """Return the current M1 decision engine."""
        return self._decision_engine

    @property
    def is_running(self) -> bool:
        """Return True if background loop is currently running."""
        return self._is_running

    @property
    def current_cycle(self) -> int:
        """Return total cycles completed."""
        return self._current_cycle

    @property
    def step_interval(self) -> int:
        """Return simulation steps advanced per cycle."""
        return self._step_interval

    @step_interval.setter
    def step_interval(self, value: int) -> None:
        self._step_interval = max(1, value)

    @property
    def cycle_delay(self) -> float:
        """Return delay between cycles in seconds."""
        return self._cycle_delay

    @cycle_delay.setter
    def cycle_delay(self, value: float) -> None:
        self._cycle_delay = max(0.0, value)

    @property
    def error_policy(self) -> str:
        """Return error policy ('continue' or 'stop')."""
        return self._error_policy

    @error_policy.setter
    def error_policy(self, value: str) -> None:
        if value not in {"continue", "stop"}:
            raise ValueError(f"Invalid error_policy '{value}'. Must be 'continue' or 'stop'.")
        self._error_policy = value

    def set_decision_engine(self, engine: DecisionEngineProtocol) -> None:
        """Attach or update the M1 Decision Engine."""
        self._decision_engine = engine

    # -------------------------------------------------------------------------
    # Execution Methods
    # -------------------------------------------------------------------------

    def step_cycle(self) -> ControlCycleResult:
        """Execute exactly one synchronous closed-loop cycle.

        Sequence:
        1. Ensure TraCI connection
        2. Advance SUMO by step_interval & collect TrafficState
        3. Broadcast TrafficState over WebSocket (if broadcaster present)
        4. Apply control policy based on active ControlMode:
           - AUTO: Request decisions from M1 AI and dispatch to ActionDispatcher
           - MANUAL: M1 passively observes; M1 actions are NOT automatically dispatched
           - EMERGENCY: Suppress normal AI control; generate deterministic FALLBACK
             SignalActions (green_duration=60.0) for I1-I4 via ActionDispatcher
        5. Return detailed ControlCycleResult

        Returns:
            ControlCycleResult describing the executed cycle.

        Raises:
            SimulationDisconnectedError: If SUMO is not connected.
            ActuationError: If an actuation fails and error_policy == 'stop'.
        """
        if not self._provider.is_connected:
            raise SimulationDisconnectedError("Cannot execute control cycle: SUMO simulation is disconnected.")

        self._current_cycle += 1
        cycle_idx = self._current_cycle
        errors: list[str] = []
        action_results: list[dict[str, Any]] = []

        # 1. Step simulation and obtain canonical TrafficState
        try:
            states = self._provider.step_and_get_states(steps=self._step_interval)
            sim_time = self._provider.simulation_time
        except (TraCIBridgeError, Exception) as exc:
            logger.error("Simulation stepping failed in cycle %d: %s", cycle_idx, exc)
            raise SimulationDisconnectedError(f"Simulation stepping failed: {exc}") from exc

        # 2. Publish to WebSocket stream if broadcaster is attached
        if self._broadcaster is not None:
            self._safe_broadcast(states)

        # 3. Determine actions to dispatch based on active ControlMode
        actions_to_dispatch: list[SignalAction | RouteAction] = []

        if self._mode == ControlMode.AUTO:
            # AUTO: Normal closed-loop AI operation
            raw_actions = self._invoke_decision_engine(states)
            actions_to_dispatch = self._normalize_actions(raw_actions)

        elif self._mode == ControlMode.MANUAL:
            # MANUAL: M1 observes traffic passively; AI actions must NOT automatically actuate SUMO
            self._invoke_decision_engine(states)
            actions_to_dispatch = []

        elif self._mode == ControlMode.EMERGENCY:
            # EMERGENCY: Deterministic corridor emergency policy
            # AI actions suppressed; generate deterministic FALLBACK SignalActions for I1-I4 (60.0s)
            actions_to_dispatch = self._generate_emergency_actions(states)

        actions_attempted = len(actions_to_dispatch)

        # 4. Dispatch actions through existing ActionDispatcher
        for action in actions_to_dispatch:
            try:
                res = self._dispatcher.dispatch(action)
                action_results.append(res.model_dump(mode="json"))
                logger.debug("Applied %s in cycle %d: %s", type(action).__name__, cycle_idx, res)
            except ActuationError as exc:
                err_msg = f"Actuation error for {type(action).__name__} (target={getattr(action, 'target', 'unknown')}): {exc}"
                logger.warning(err_msg)
                errors.append(err_msg)
                if self._error_policy == "stop":
                    self._is_running = False
                    raise
            except Exception as exc:
                err_msg = f"Unexpected error during actuation: {exc}"
                logger.error(err_msg)
                errors.append(err_msg)
                if self._error_policy == "stop":
                    self._is_running = False
                    raise

        return ControlCycleResult(
            cycle=cycle_idx,
            simulation_time=sim_time,
            states=states,
            mode=self._mode,
            actions_attempted=actions_attempted,
            action_results=action_results,
            errors=errors,
            success=(len(errors) == 0),
        )


    def run_steps(self, n_cycles: int) -> list[ControlCycleResult]:
        """Run a fixed number of synchronous control cycles."""
        results: list[ControlCycleResult] = []
        for _ in range(n_cycles):
            results.append(self.step_cycle())
        return results

    async def run_async(self, max_cycles: int | None = None) -> list[ControlCycleResult]:
        """Run closed loop asynchronously, respecting cycle_delay and stop()."""
        self._is_running = True

        results: list[ControlCycleResult] = []
        try:
            while self._is_running:
                if max_cycles is not None and len(results) >= max_cycles:
                    break

                try:
                    result = self.step_cycle()
                    results.append(result)
                except SimulationDisconnectedError as exc:
                    logger.warning("Simulation disconnected, halting control loop: %s", exc)
                    break
                except ActuationError:
                    if self._error_policy == "stop":
                        break

                if self._cycle_delay > 0.0:
                    await asyncio.sleep(self._cycle_delay)
                else:
                    await asyncio.sleep(0)  # Yield to event loop
        finally:
            self._is_running = False

        return results

    async def start_background(self, max_cycles: int | None = None) -> None:
        """Start control loop as an independent background task."""
        if self._is_running:
            raise RuntimeError("SimulationControlLoop is already running.")

        self._is_running = True
        self._background_task = asyncio.create_task(self.run_async(max_cycles=max_cycles))
        logger.info("Background control loop task started.")

    async def stop(self) -> None:
        """Signal the control loop to stop and await termination."""
        self._is_running = False
        if self._background_task is not None and not self._background_task.done():
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning("Error awaiting control loop task termination: %s", exc)
            self._background_task = None
        logger.info("Control loop stopped.")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _invoke_decision_engine(
        self, states: dict[str, TrafficState]
    ) -> Any:
        """Invoke M1 decision engine, supporting synchronous or coroutine responses."""
        try:
            res = self._decision_engine.decide(states)
            if inspect.isawaitable(res):
                # If an async engine was supplied, run it synchronously if loop is sync
                try:
                    loop = asyncio.get_running_loop()
                    future = asyncio.run_coroutine_threadsafe(res, loop)
                    return future.result()
                except RuntimeError:
                    return asyncio.run(res)
            return res
        except Exception as exc:
            logger.error("M1 Decision engine raised exception: %s", exc)
            return None

    def _normalize_actions(
        self, raw: Any
    ) -> list[SignalAction | RouteAction]:
        """Normalize M1 output into a list of valid Action objects."""
        if raw is None:
            return []
        if isinstance(raw, (SignalAction, RouteAction)):
            return [raw]
        if isinstance(raw, (list, tuple)):
            return [act for act in raw if isinstance(act, (SignalAction, RouteAction))]
        logger.warning("M1 returned unrecognized action output type: %s", type(raw))
        return []

    def _safe_broadcast(self, states: dict[str, TrafficState]) -> None:
        """Schedule WebSocket broadcast without crashing sync context."""
        try:
            loop = asyncio.get_running_loop()
            if inspect.iscoroutinefunction(getattr(self._broadcaster, "broadcast_all_states", None)):
                loop.create_task(self._broadcaster.broadcast_all_states(states))
        except RuntimeError:
            # No active asyncio event loop in thread; skip non-blocking broadcast
            pass

    def _generate_emergency_actions(
        self, states: dict[str, TrafficState]
    ) -> list[SignalAction]:
        """Generate deterministic emergency corridor priority actions for I1-I4.

        Produces FALLBACK SignalActions with green_duration=60.0 for all intersections.
        Actuation flows through ActionDispatcher -> SignalActuator -> TraCI,
        updating the green phase (NS_GREEN/EW_GREEN) while safely preserving yellow phases.
        """
        now = datetime.now(timezone.utc)
        target_ids = list(states.keys()) if states else ["I1", "I2", "I3", "I4"]
        target_ids.sort()

        return [
            SignalAction(
                target=target_id,
                green_duration=60.0,
                source=ActionSource.FALLBACK,
                timestamp=now,
            )
            for target_id in target_ids
        ]

