"""Dependencies and simulation lifecycle management for FastAPI backend."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.api.websocket import get_connection_manager
from simulation.sumo.actuation import ActionDispatcher
from simulation.sumo.control_loop import (
    NullDecisionEngine,
    RealM1DecisionEngine,
    SimulationControlLoop,
)
from simulation.sumo.m1_adapter import HAS_M1
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import TraCIBridge

_bridge: TraCIBridge | None = None
_provider: TrafficStateProvider | None = None
_dispatcher: ActionDispatcher | None = None
_control_loop: SimulationControlLoop | None = None


def get_bridge() -> TraCIBridge:
    """Return the managed TraCIBridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = TraCIBridge()
    return _bridge


def get_state_provider() -> TrafficStateProvider:
    """Return the managed TrafficStateProvider singleton.

    Ensures the underlying simulation is connected before returning.
    """
    global _provider
    if _provider is None:
        bridge = get_bridge()
        _provider = TrafficStateProvider(bridge)
    if not _provider.is_connected:
        _provider.bridge.start()
    return _provider


def get_action_dispatcher() -> ActionDispatcher:
    """Return the managed ActionDispatcher singleton.

    Ensures the underlying simulation is connected before returning.
    """
    global _dispatcher
    if _dispatcher is None:
        bridge = get_bridge()
        _dispatcher = ActionDispatcher(bridge)
    if not _dispatcher.signal_actuator.bridge.is_connected:
        _dispatcher.signal_actuator.bridge.start()
    return _dispatcher


def get_control_loop() -> SimulationControlLoop:
    """Return the managed SimulationControlLoop singleton.

    Wires together TrafficStateProvider, ActionDispatcher, WebSocket broadcaster,
    and the production RealM1DecisionEngine.
    """
    global _control_loop
    if _control_loop is None:
        provider = get_state_provider()
        dispatcher = get_action_dispatcher()
        broadcaster = get_connection_manager()
        bridge = get_bridge()
        if HAS_M1:
            decision_engine = RealM1DecisionEngine(bridge=bridge)
        else:
            decision_engine = NullDecisionEngine()
        _control_loop = SimulationControlLoop(
            provider=provider,
            dispatcher=dispatcher,
            broadcaster=broadcaster,
            decision_engine=decision_engine,
        )
    return _control_loop


def start_simulation() -> TrafficStateProvider:
    """Initialize and start the simulation connection on application startup."""
    provider = get_state_provider()
    if not provider.is_connected:
        provider.bridge.start()
    return provider


def stop_simulation() -> None:
    """Terminate TraCI and cleanly shut down the SUMO process."""
    global _bridge, _provider, _dispatcher, _control_loop
    if _control_loop is not None:
        _control_loop._is_running = False
    _control_loop = None
    if _bridge is not None:
        _bridge.close()
    _bridge = None
    _provider = None
    _dispatcher = None
