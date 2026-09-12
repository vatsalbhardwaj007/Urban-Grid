"""Virtual Sensor Layer for Urban Grid SUMO Simulation.

Emulates roadside traffic sensors converting raw TraCI measurements
into standardized traffic measurements directly compatible with
the canonical TrafficState v1 contract (shared.schemas.traffic_state).

Provides:
- LaneSensor: measures per-lane vehicle count, speed, queue, occupancy,
  arrival rate, density, and flow.
- IntersectionSensor: aggregates incoming approach lanes and signal states
  for an intersection into canonical TrafficState observations.
- Helper functions: signal phase mapping and sensor factory.

Definitions and Formulas:
- vehicle_count: Current number of vehicles on the lane (int >= 0).
- mean_speed: Mean vehicle speed in m/s; 0.0 if vehicle_count == 0 (float >= 0.0).
- queue_length: Count of vehicles with speed <= queue_speed_threshold (default 0.1 m/s).
- occupancy: Fraction of lane occupied [0.0, 1.0], sourced from SUMO's detector model.
- density: Vehicles per kilometre = (vehicle_count / lane_length_meters) * 1000.0.
- arrival_rate: Newly entered vehicles per second = (new_vehicles / dt) over step dt.
- flow: Vehicles per hour = arrival_rate * 3600.0.
- signal_phase: Canonical mapping to "RED", "YELLOW", or "GREEN".
- green_remaining: Remaining seconds of green if signal_phase == "GREEN", else 0.0.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

# Ensure workspace root is in sys.path so shared.schemas can be imported
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from shared.schemas.traffic_state import LaneFeature, TrafficState
from simulation.sumo.traci_bridge import TraCIBridge, TraCIBridgeError


def map_signal_phase(state_str: str, phase_name: str = "") -> Literal["RED", "YELLOW", "GREEN"]:
    """Map SUMO traffic light state and phase name to canonical Urban Grid signal phase.

    Args:
        state_str: Raw TraCI signal state string (e.g. 'GGGgrrrrGGGgrrrr').
        phase_name: Optional program phase name (e.g. 'NS_GREEN', 'EW_YELLOW').

    Returns:
        One of 'RED', 'YELLOW', 'GREEN'.
    """
    name_upper = (phase_name or "").upper()
    if "GREEN" in name_upper:
        return "GREEN"
    if "YELLOW" in name_upper:
        return "YELLOW"
    if "RED" in name_upper:
        return "RED"

    # Fallback to inspecting signal characters in state string
    chars = set((state_str or "").upper())
    if "G" in chars:
        return "GREEN"
    if "Y" in chars:
        return "YELLOW"
    return "RED"


class LaneSensor:
    """Virtual roadside sensor monitoring a specific lane."""

    def __init__(
        self,
        lane_id: str,
        bridge: TraCIBridge,
        queue_speed_threshold: float = 0.1,
    ) -> None:
        """Initialize LaneSensor.

        Args:
            lane_id: Monitored lane ID (e.g. 'E_W1_I1_0').
            bridge: Active TraCIBridge instance.
            queue_speed_threshold: Speed threshold in m/s at or below which
                a vehicle is considered queued (default 0.1 m/s).
        """
        self.lane_id = lane_id
        self.bridge = bridge
        self.queue_speed_threshold = queue_speed_threshold

        self._lane_length: float | None = None
        self._prev_vehicle_ids: set[str] | None = None
        self._prev_timestamp: float | None = None

    @property
    def lane_length(self) -> float:
        """Return the physical length of the monitored lane in meters."""
        if self._lane_length is None:
            self._ensure_connected()
            with self.bridge.lock:
                conn = self.bridge.raw_connection
                try:
                    self._lane_length = float(conn.lane.getLength(self.lane_id))
                except Exception as exc:
                    raise ValueError(f"Lane '{self.lane_id}' not found in simulation network: {exc}") from exc
        return self._lane_length

    def _ensure_connected(self) -> None:
        if not self.bridge.is_connected:
            raise TraCIBridgeError("TraCI bridge must be connected to take sensor measurements.")

    def reset(self) -> None:
        """Reset temporal state (cached vehicle IDs and timestamps)."""
        self._prev_vehicle_ids = None
        self._prev_timestamp = None

    def measure(self, timestamp: float | None = None) -> LaneFeature:
        """Collect live measurements from the monitored lane and return LaneFeature.

        Args:
            timestamp: Optional current timestamp override. If None, queries bridge.

        Returns:
            Validated canonical LaneFeature instance.
        """
        self._ensure_connected()

        with self.bridge.lock:
            conn = self.bridge.raw_connection

            current_time = float(timestamp if timestamp is not None else self.bridge.simulation_time)

            try:
                vehicle_ids = list(conn.lane.getLastStepVehicleIDs(self.lane_id))
            except Exception as exc:
                raise ValueError(f"Failed to inspect lane '{self.lane_id}': {exc}") from exc

            count = len(vehicle_ids)
            length = self.lane_length

            if count == 0:
                mean_speed = 0.0
                queue_length = 0
                occupancy = 0.0
                density = 0.0
            else:
                speeds = [float(conn.vehicle.getSpeed(vid)) for vid in vehicle_ids]
                mean_speed = sum(speeds) / count if count > 0 else 0.0
                queue_length = sum(1 for spd in speeds if spd <= self.queue_speed_threshold)
                raw_occupancy = float(conn.lane.getLastStepOccupancy(self.lane_id))
                occupancy = min(1.0, max(0.0, raw_occupancy))
                density = (count / length) * 1000.0 if length > 0.0 else 0.0

        # Arrival rate derived from newly entered vehicles across steps
        curr_vehicle_set = set(vehicle_ids)
        if self._prev_timestamp is not None and self._prev_vehicle_ids is not None:
            dt = current_time - self._prev_timestamp
            new_arrivals = len(curr_vehicle_set - self._prev_vehicle_ids)
            arrival_rate = (new_arrivals / dt) if dt > 0.0 else 0.0
        else:
            arrival_rate = 0.0

        self._prev_vehicle_ids = curr_vehicle_set
        self._prev_timestamp = current_time

        # Flow in vehicles per hour
        flow = arrival_rate * 3600.0

        return LaneFeature(
            lane_id=self.lane_id,
            vehicle_count=count,
            mean_speed=round(mean_speed, 4),
            queue_length=queue_length,
            occupancy=round(occupancy, 4),
            arrival_rate=round(arrival_rate, 4),
            density=round(density, 4),
            flow=round(flow, 4),
        )


class IntersectionSensor:
    """Virtual intersection sensor aggregating incoming lanes and traffic-light state."""

    def __init__(
        self,
        intersection_id: str,
        bridge: TraCIBridge,
        lane_ids: list[str] | None = None,
        queue_speed_threshold: float = 0.1,
    ) -> None:
        """Initialize IntersectionSensor.

        Args:
            intersection_id: Intersection / traffic light ID (e.g. 'I1', 'I2').
            bridge: Active TraCIBridge instance.
            lane_ids: Optional list of incoming lane IDs. If None, dynamically
                discovered from SUMO's traffic light controlled lanes.
            queue_speed_threshold: Speed threshold in m/s for queue detection.
        """
        self.intersection_id = intersection_id
        self.bridge = bridge
        self.queue_speed_threshold = queue_speed_threshold

        self._monitored_lanes: list[str] | None = list(lane_ids) if lane_ids is not None else None
        self._lane_sensors: dict[str, LaneSensor] | None = None
        self._prev_vehicle_ids: set[str] | None = None
        self._prev_timestamp: float | None = None

    def _ensure_connected(self) -> None:
        if not self.bridge.is_connected:
            raise TraCIBridgeError("TraCI bridge must be connected to take sensor measurements.")

    @property
    def monitored_lanes(self) -> list[str]:
        """Return list of monitored incoming approach lane IDs."""
        if self._monitored_lanes is None:
            self._ensure_connected()
            with self.bridge.lock:
                conn = self.bridge.raw_connection
                tls_list = conn.trafficlight.getIDList()
                if self.intersection_id not in tls_list:
                    raise ValueError(
                        f"Traffic light / intersection '{self.intersection_id}' not found in simulation network."
                    )
                # Discover controlled incoming lanes, filtering out duplicates and internal lanes
                raw_lanes = conn.trafficlight.getControlledLanes(self.intersection_id)
                seen: set[str] = set()
                unique_lanes: list[str] = []
                for lid in raw_lanes:
                    if not lid.startswith(":") and lid not in seen:
                        seen.add(lid)
                        unique_lanes.append(lid)
                self._monitored_lanes = unique_lanes

        return self._monitored_lanes

    @property
    def lane_sensors(self) -> dict[str, LaneSensor]:
        """Return mapping of lane_id to LaneSensor instances."""
        if self._lane_sensors is None:
            self._lane_sensors = {
                lid: LaneSensor(
                    lane_id=lid,
                    bridge=self.bridge,
                    queue_speed_threshold=self.queue_speed_threshold,
                )
                for lid in self.monitored_lanes
            }
        return self._lane_sensors

    def reset(self) -> None:
        """Reset temporal state across intersection and all constituent lane sensors."""
        self._prev_vehicle_ids = None
        self._prev_timestamp = None
        if self._lane_sensors:
            for sensor in self._lane_sensors.values():
                sensor.reset()

    def measure(self, timestamp: float | None = None) -> TrafficState:
        """Measure live intersection traffic state and return canonical TrafficState.

        Args:
            timestamp: Optional current timestamp override. If None, queries bridge.

        Returns:
            Validated canonical TrafficState instance.
        """
        self._ensure_connected()

        with self.bridge.lock:
            current_time = float(timestamp if timestamp is not None else self.bridge.simulation_time)

            # Measure each constituent approach lane
            lane_features: list[LaneFeature] = [
                sensor.measure(timestamp=current_time)
                for sensor in self.lane_sensors.values()
            ]

            # Total queue: sum of lane queues
            total_queue = sum(lf.queue_length for lf in lane_features)

            # Total vehicles across all approach lanes
            total_vehicles = sum(lf.vehicle_count for lf in lane_features)

            # Aggregate mean speed: vehicle-weighted average across lanes (0.0 if no vehicles)
            if total_vehicles > 0:
                weighted_speed_sum = sum(lf.mean_speed * lf.vehicle_count for lf in lane_features)
                mean_speed = weighted_speed_sum / total_vehicles
            else:
                mean_speed = 0.0

            # Aggregate density: total vehicles / total monitored lane length in km
            total_length_km = sum(sensor.lane_length for sensor in self.lane_sensors.values()) / 1000.0
            density = (total_vehicles / total_length_km) if total_length_km > 0.0 else 0.0

            # Aggregate arrival rate: unique new vehicles entering intersection approaches
            conn = self.bridge.raw_connection
            all_curr_vids: set[str] = set()
            for lid in self.monitored_lanes:
                all_curr_vids.update(conn.lane.getLastStepVehicleIDs(lid))

            if self._prev_timestamp is not None and self._prev_vehicle_ids is not None:
                dt = current_time - self._prev_timestamp
                new_arrivals = len(all_curr_vids - self._prev_vehicle_ids)
                arrival_rate = (new_arrivals / dt) if dt > 0.0 else 0.0
            else:
                arrival_rate = 0.0

            self._prev_vehicle_ids = all_curr_vids
            self._prev_timestamp = current_time

            # Traffic light signal phase and remaining green time
            tls_state = self.bridge.get_traffic_light_state(self.intersection_id)
            signal_phase = map_signal_phase(
                state_str=tls_state.get("state", ""),
                phase_name=tls_state.get("phase_name", ""),
            )

            if signal_phase == "GREEN":
                green_remaining = float(tls_state.get("remaining_phase_time", 0.0))
            else:
                green_remaining = 0.0

            return TrafficState(
                timestamp=round(current_time, 4),
                intersection_id=self.intersection_id,
                lane_features=lane_features,
            total_queue=total_queue,
            mean_speed=round(mean_speed, 4),
            arrival_rate=round(arrival_rate, 4),
            density=round(density, 4),
            signal_phase=signal_phase,
            green_remaining=round(green_remaining, 4),
        )

    def build_traffic_state(self, timestamp: float | None = None) -> TrafficState:
        """Alias for measure(), constructing the canonical TrafficState model."""
        return self.measure(timestamp=timestamp)


def create_intersection_sensors(
    bridge: TraCIBridge,
    intersection_ids: list[str] | None = None,
    queue_speed_threshold: float = 0.1,
) -> dict[str, IntersectionSensor]:
    """Create IntersectionSensor instances for all signalized intersections in the network.

    Args:
        bridge: Active TraCIBridge instance.
        intersection_ids: Optional list of intersection IDs. If None, queries
            bridge.get_traffic_light_ids().
        queue_speed_threshold: Speed threshold for queue detection.

    Returns:
        Dictionary mapping intersection ID to IntersectionSensor.
    """
    if intersection_ids is None:
        intersection_ids = bridge.get_traffic_light_ids()

    return {
        iid: IntersectionSensor(
            intersection_id=iid,
            bridge=bridge,
            queue_speed_threshold=queue_speed_threshold,
        )
        for iid in intersection_ids
    }
