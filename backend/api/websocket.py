"""WebSocket connection management and event broadcasting for Urban Grid M2.

Architecture:
SUMO -> M2 / TrafficStateProvider -> WebSocket Broadcaster -> M3 (Frontend) / M4 (Analytics)

Provides:
- ConnectionManager: thread-safe / async manager for tracking connected WebSocket clients,
  culling stale connections, and broadcasting canonical traffic.update events.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from shared.schemas.traffic_state import TrafficState

logger = logging.getLogger("urbangrid.websocket")


def build_traffic_event(state: TrafficState) -> dict[str, Any]:
    """Construct the canonical event envelope for a traffic update."""
    return {
        "event": "traffic.update",
        "data": state.model_dump(mode="json"),
    }


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts traffic state updates."""

    def __init__(self) -> None:
        self._active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def active_connections_count(self) -> int:
        """Return the number of currently active connections."""
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)
        logger.info("WebSocket client connected. Active: %d", self.active_connections_count)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a disconnected WebSocket connection."""
        async with self._lock:
            self._active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Active: %d", self.active_connections_count)

    async def disconnect_all(self) -> None:
        """Cleanly close and unregister all active connections on shutdown."""
        async with self._lock:
            connections = list(self._active_connections)
            self._active_connections.clear()

        for conn in connections:
            try:
                await conn.close(code=1000)
            except Exception:
                pass
        logger.info("All WebSocket connections closed.")

    async def send_traffic_state(self, websocket: WebSocket, state: TrafficState) -> None:
        """Send a single canonical TrafficState event to a specific client."""
        payload = build_traffic_event(state)
        await websocket.send_json(payload)

    async def broadcast_traffic_state(self, state: TrafficState) -> None:
        """Broadcast a single canonical TrafficState event to all connected clients."""
        payload = build_traffic_event(state)
        await self._broadcast_json(payload)

    async def broadcast_all_states(self, states: dict[str, TrafficState]) -> None:
        """Broadcast canonical TrafficState events for multiple intersections.

        Sends one canonical traffic.update event per intersection.
        """
        for state in states.values():
            await self.broadcast_traffic_state(state)

    async def _broadcast_json(self, payload: dict[str, Any]) -> None:
        """Internal broadcast helper that culls stale/broken connections safely."""
        async with self._lock:
            connections = list(self._active_connections)

        if not connections:
            return

        stale_connections: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_json(payload)
            except (WebSocketDisconnect, RuntimeError, ConnectionResetError, Exception) as exc:
                logger.debug("Failed to send to client; marking stale: %s", exc)
                stale_connections.append(connection)

        if stale_connections:
            async with self._lock:
                for stale in stale_connections:
                    self._active_connections.discard(stale)
            logger.info("Culled %d stale connections. Active: %d", len(stale_connections), self.active_connections_count)


# Global singleton connection manager
_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Return the managed ConnectionManager singleton."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
