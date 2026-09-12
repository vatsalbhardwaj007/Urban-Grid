"""Dependencies and simulation lifecycle management for FastAPI backend."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from simulation.sumo.actuation import ActionDispatcher
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import TraCIBridge

_bridge: TraCIBridge | None = None
_provider: TrafficStateProvider | None = None
_dispatcher: ActionDispatcher | None = None


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


def start_simulation() -> TrafficStateProvider:
    """Initialize and start the simulation connection on application startup."""
    provider = get_state_provider()
    if not provider.is_connected:
        provider.bridge.start()
    return provider


def stop_simulation() -> None:
    """Terminate TraCI and cleanly shut down the SUMO process."""
    global _bridge, _provider, _dispatcher
    if _bridge is not None:
        _bridge.close()
    _bridge = None
    _provider = None
    _dispatcher = None
