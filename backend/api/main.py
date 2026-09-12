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

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    get_state_provider,
    start_simulation,
    stop_simulation,
)
from shared.schemas.traffic_state import TrafficState
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import TraCIBridgeError


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
def step_simulation(
    request: StepRequest = StepRequest(),
    provider: TrafficStateProvider = Depends(get_state_provider),
) -> dict[str, TrafficState]:
    """Advance SUMO by the requested steps and return updated states."""
    try:
        return provider.step_and_get_states(steps=request.steps)
    except TraCIBridgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Simulation unavailable: {exc}",
        ) from exc
