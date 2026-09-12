"""FastAPI application exposing Urban Grid simulation TrafficState.

Architecture:
HTTP client -> FastAPI -> TrafficStateProvider -> Virtual Sensors -> TraCI / SUMO
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import json
import logging

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    get_action_dispatcher,
    get_control_loop,
    get_state_provider,
    start_simulation,
    stop_simulation,
)
from backend.api.websocket import ConnectionManager, get_connection_manager
from shared.schemas.route_action import RouteAction
from shared.schemas.signal_action import SignalAction
from shared.schemas.traffic_state import TrafficState
from simulation.sumo.actuation import (
    ActionDispatcher,
    ActuationError,
    InvalidRouteEdgeError,
    InvalidRouteError,
    InvalidSignalDurationError,
    RouteActuationResult,
    SignalActuationResult,
    SimulationDisconnectedError,
    UnknownTrafficLightError,
    UnknownVehicleError,
)
from simulation.sumo.control_loop import ControlCycleResult, SimulationControlLoop
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import TraCIBridgeError

logger = logging.getLogger("urbangrid.api")


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(default="ok", description="Application health status.")
    simulation_connected: bool = Field(
        description="Whether the TraCI simulation bridge is currently connected."
    )
    simulation_time: float | None = Field(
        default=None,
        description="Current SUMO simulation time in seconds, or None if disconnected.",
    )


class StepRequest(BaseModel):
    """Optional request payload for simulation stepping."""

    steps: int = Field(
        default=1,
        ge=1,
        description="Number of simulation steps to advance.",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application simulation lifecycle (startup and shutdown)."""
    try:
        start_simulation()
    except Exception as exc:
        # Keep application running so health check can report simulation status
        print(f"Warning: Failed to auto-start simulation during startup: {exc}")
    try:
        yield
    finally:
        await get_control_loop().stop()
        await get_connection_manager().disconnect_all()
        stop_simulation()


app = FastAPI(
    title="Urban Grid API",
    version="1.0.0",
    description="FastAPI service exposing live SUMO TrafficState for Urban Grid.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["Health"],
)
def health_check() -> HealthResponse:
    """Confirm backend process is alive and report simulation connectivity."""
    try:
        provider = get_state_provider()
        connected = provider.is_connected
        sim_time = provider.simulation_time if connected else None
    except Exception:
        connected = False
        sim_time = None

    return HealthResponse(
        status="ok",
        simulation_connected=connected,
        simulation_time=sim_time,
    )


@app.get(
    "/api/intersections",
    response_model=list[str],
    summary="List monitored intersections",
    tags=["Intersections"],
)
def list_intersections(
    provider: TrafficStateProvider = Depends(get_state_provider),
) -> list[str]:
    """Return the known Urban Grid intersections (I1, I2, I3, I4)."""
    try:
        return provider.intersection_ids
    except TraCIBridgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Simulation unavailable: {exc}",
        ) from exc


@app.get(
    "/api/traffic-state/{intersection_id}",
    response_model=TrafficState,
    summary="Get canonical TrafficState for a single intersection",
    tags=["Traffic State"],
)
def get_traffic_state(
    intersection_id: str,
    provider: TrafficStateProvider = Depends(get_state_provider),
) -> TrafficState:
    """Return the current canonical TrafficState for the requested intersection."""
    try:
        return provider.get_state(intersection_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intersection '{intersection_id}' not found.",
        ) from exc
    except TraCIBridgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Simulation unavailable: {exc}",
        ) from exc


@app.get(
    "/api/traffic-state",
    response_model=dict[str, TrafficState],
    summary="Get canonical TrafficState for all monitored intersections",
    tags=["Traffic State"],
)
def get_all_traffic_states(
    provider: TrafficStateProvider = Depends(get_state_provider),
) -> dict[str, TrafficState]:
    """Return the current TrafficState for all monitored intersections at the current timestep."""
    try:
        return provider.get_all_states()
    except TraCIBridgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Simulation unavailable: {exc}",
        ) from exc


@app.post(
    "/api/simulation/step",
    response_model=dict[str, TrafficState],
    summary="Step simulation and return updated TrafficState for all intersections",
    tags=["Simulation Control"],
)
async def step_simulation(
    request: StepRequest = StepRequest(),
    provider: TrafficStateProvider = Depends(get_state_provider),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> dict[str, TrafficState]:
    """Advance SUMO by the requested steps and return updated states.

    Also broadcasts canonical traffic.update events to all connected WebSocket clients.
    """
    try:
        states = provider.step_and_get_states(steps=request.steps)
        await manager.broadcast_all_states(states)
        return states
    except TraCIBridgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Simulation unavailable: {exc}",
        ) from exc


@app.websocket("/ws/traffic")
async def traffic_websocket_endpoint(
    websocket: WebSocket,
    provider: TrafficStateProvider = Depends(get_state_provider),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> None:
    """WebSocket stream publishing live canonical TrafficState updates.

    SUMO -> M2 -> WebSocket -> M3/M4
    """
    await manager.connect(websocket)
    try:
        # Immediately send latest known TrafficState snapshot upon connection
        if provider.is_connected:
            try:
                states = provider.get_all_states()
                for state in states.values():
                    await manager.send_traffic_state(websocket, state)
            except Exception as exc:
                logger.warning("Could not send initial traffic states to client: %s", exc)

        # Keep stream open, handle incoming frames (ping/step/keepalive) cleanly
        while True:
            try:
                message = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                # Transport or framing failure, close out connection
                break

            # Handle optional client message gracefully
            try:
                data = json.loads(message)
                if isinstance(data, dict):
                    action = data.get("action") or data.get("type")
                    if action == "ping":
                        await websocket.send_json({"event": "pong"})
                    elif action == "step":
                        steps = int(data.get("steps", 1))
                        states = provider.step_and_get_states(steps=steps)
                        await manager.broadcast_all_states(states)
            except Exception:
                # Malformed JSON or handling error is ignored without crashing
                pass
    finally:
        await manager.disconnect(websocket)


@app.post(
    "/api/control/signal",
    response_model=SignalActuationResult,
    summary="Apply M1 SignalAction timing recommendation",
    tags=["Control Actions"],
)
def control_signal(
    action: SignalAction,
    dispatcher: ActionDispatcher = Depends(get_action_dispatcher),
) -> SignalActuationResult:
    """Validate and actuate a traffic signal timing recommendation from M1."""
    try:
        return dispatcher.apply_signal(action)
    except (UnknownTrafficLightError, InvalidSignalDurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SimulationDisconnectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ActuationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signal actuation failed: {exc}",
        ) from exc


@app.post(
    "/api/control/route",
    response_model=RouteActuationResult,
    summary="Apply M1 RouteAction rerouting directive",
    tags=["Control Actions"],
)
def control_route(
    action: RouteAction,
    dispatcher: ActionDispatcher = Depends(get_action_dispatcher),
) -> RouteActuationResult:
    """Validate and actuate a vehicle rerouting directive from M1."""
    try:
        return dispatcher.apply_route(action)
    except (UnknownVehicleError, InvalidRouteEdgeError, InvalidRouteError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SimulationDisconnectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ActuationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Route actuation failed: {exc}",
        ) from exc


class ControlLoopStatusResponse(BaseModel):
    """Response model reporting current simulation control loop status."""

    is_running: bool = Field(description="Whether the control loop is currently running.")
    current_cycle: int = Field(description="Total cycles executed so far.")
    step_interval: int = Field(description="Simulation steps per control cycle.")
    cycle_delay: float = Field(description="Configured delay in seconds between cycles.")
    error_policy: str = Field(description="Action error handling policy ('continue' or 'stop').")
    decision_engine: str = Field(description="Class name of the active M1 decision engine.")


@app.get(
    "/api/control/loop/status",
    response_model=ControlLoopStatusResponse,
    summary="Get status of M2 simulation control loop",
    tags=["Control Loop"],
)
def get_control_loop_status(
    control_loop: SimulationControlLoop = Depends(get_control_loop),
) -> ControlLoopStatusResponse:
    """Return live status of the closed-loop orchestrator."""
    return ControlLoopStatusResponse(
        is_running=control_loop.is_running,
        current_cycle=control_loop.current_cycle,
        step_interval=control_loop.step_interval,
        cycle_delay=control_loop.cycle_delay,
        error_policy=control_loop.error_policy,
        decision_engine=type(control_loop.decision_engine).__name__,
    )


@app.post(
    "/api/control/loop/step",
    response_model=ControlCycleResult,
    summary="Execute one closed-loop control cycle",
    tags=["Control Loop"],
)
def execute_control_loop_cycle(
    control_loop: SimulationControlLoop = Depends(get_control_loop),
) -> ControlCycleResult:
    """Advance simulation and execute one closed-loop cycle (step -> state -> M1 -> TraCI)."""
    try:
        return control_loop.step_cycle()
    except SimulationDisconnectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ActuationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Control loop cycle failed: {exc}",
        ) from exc


