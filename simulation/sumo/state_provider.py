"""TrafficState integration provider for Urban Grid SUMO simulation.

Establishes the boundary between the simulation layer and downstream consumers:
SUMO -> TraCI Bridge -> Virtual Sensors -> TrafficStateProvider -> TrafficState v1

Provides:
- TrafficStateProvider: cohesive interface to query single or all intersection
  canonical TrafficState observations at deterministic simulation timestamps.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from shared.schemas.traffic_state import TrafficState
from simulation.sumo.sensors import (
    IntersectionSensor,
    create_intersection_sensors,
)
from simulation.sumo.traci_bridge import TraCIBridge, TraCIBridgeError


class TrafficStateProvider:
    """Provides canonical TrafficState v1 observations from SUMO virtual sensors."""

    def __init__(
        self,
        bridge: TraCIBridge,
        intersection_ids: list[str] | None = None,
        queue_speed_threshold: float = 0.1,
    ) -> None:
        """Initialize TrafficStateProvider.

        Args:
            bridge: Active or configured TraCIBridge instance.
            intersection_ids: Optional list of monitored intersection IDs.
                Defaults to auto-discovering all signalized intersections in network.
            queue_speed_threshold: Speed threshold in m/s for queue classification.
        """
        self._bridge = bridge
        self._configured_intersection_ids = list(intersection_ids) if intersection_ids is not None else None
        self._queue_speed_threshold = queue_speed_threshold
        self._sensors: dict[str, IntersectionSensor] | None = None

    @property
    def bridge(self) -> TraCIBridge:
        """Return the underlying TraCIBridge instance."""
        return self._bridge

    @property
    def is_connected(self) -> bool:
        """Return True if the underlying TraCI bridge is connected."""
        return self._bridge.is_connected

    @property
    def simulation_time(self) -> float:
        """Return the current SUMO simulation time in seconds."""
        self._ensure_connected()
        return self._bridge.simulation_time

    @property
    def intersection_ids(self) -> list[str]:
        """Return list of valid monitored intersection IDs."""
        self._ensure_connected()
        self._ensure_sensors()
        assert self._sensors is not None
        return list(self._sensors.keys())

    def _ensure_connected(self) -> None:
        if not self._bridge.is_connected:
            raise TraCIBridgeError("TraCI bridge must be connected to access TrafficState.")

    def _ensure_sensors(self) -> None:
        """Lazily initialize IntersectionSensor instances once connected."""
        if self._sensors is None:
            self._ensure_connected()
            self._sensors = create_intersection_sensors(
                bridge=self._bridge,
                intersection_ids=self._configured_intersection_ids,
                queue_speed_threshold=self._queue_speed_threshold,
            )

    def get_sensor(self, intersection_id: str) -> IntersectionSensor:
        """Return the IntersectionSensor instance for the specified intersection.

        Args:
            intersection_id: Intersection identifier (e.g. 'I1').

        Returns:
            IntersectionSensor instance.

        Raises:
            ValueError: If intersection_id is not monitored or invalid.
        """
        self._ensure_connected()
        self._ensure_sensors()
        assert self._sensors is not None

        if intersection_id not in self._sensors:
            raise ValueError(
                f"Invalid intersection ID '{intersection_id}'. "
                f"Valid intersections: {list(self._sensors.keys())}"
            )

        return self._sensors[intersection_id]

    def get_state(self, intersection_id: str) -> TrafficState:
        """Obtain the latest canonical TrafficState for a single intersection.

        Args:
            intersection_id: Intersection identifier (e.g. 'I1', 'I2').

        Returns:
            Validated canonical TrafficState instance.

        Raises:
            ValueError: If intersection_id is not valid.
            TraCIBridgeError: If TraCI bridge is not connected.
        """
        with self._bridge.lock:
            sensor = self.get_sensor(intersection_id)
            current_time = self.simulation_time
            return sensor.measure(timestamp=current_time)

    def get_all_states(self) -> dict[str, TrafficState]:
        """Obtain canonical TrafficState observations for all monitored intersections.

        All observations are measured at the exact same simulation timestamp without
        advancing the simulation.

        Returns:
            Dictionary mapping intersection_id to canonical TrafficState instance.
        """
        with self._bridge.lock:
            self._ensure_connected()
            self._ensure_sensors()
            assert self._sensors is not None

            current_time = self.simulation_time
            return {
                iid: sensor.measure(timestamp=current_time)
                for iid, sensor in self._sensors.items()
            }

    def step_and_get_states(self, steps: int = 1) -> dict[str, TrafficState]:
        """Advance simulation and return consistent states for all intersections.

        Args:
            steps: Number of steps to advance simulation (default 1).

        Returns:
            Dictionary mapping intersection_id to canonical TrafficState observed
            at the newly advanced simulation timestamp.
        """
        with self._bridge.lock:
            self._ensure_connected()
            if steps > 0:
                self._bridge.step_many(steps)
            return self.get_all_states()

    def reset(self) -> None:
        """Reset temporal state across all constituent sensors."""
        if self._sensors is not None:
            for sensor in self._sensors.values():
                sensor.reset()

    def __enter__(self) -> TrafficStateProvider:
        if not self._bridge.is_connected:
            self._bridge.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._bridge.close()
