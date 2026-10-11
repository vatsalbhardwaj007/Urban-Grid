"""TraCI bridge for Urban Grid SUMO simulation.

Provides a clean, reusable Python interface for:
- Starting SUMO / SUMO-GUI without hardcoded paths
- Managing TraCI lifecycle, connection establishment, and clean shutdown
- Stepping the simulation (single-step and multi-step)
- Extracting live vehicle, lane, and traffic-light states
"""

from __future__ import annotations

import os
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any


try:
    import sumolib
except ImportError:  # pragma: no cover
    sumolib = None

try:
    import traci
    from traci.connection import Connection
except ImportError:  # pragma: no cover
    traci = None
    Connection = Any  # type: ignore[misc,assignment]


class TraCIBridgeError(Exception):
    """Exception raised for errors in TraCI bridge operations."""
    pass


def find_sumo_binary(use_gui: bool = False) -> str:
    """Locate the SUMO or SUMO-GUI executable using sumolib, SUMO_HOME, or PATH.

    Args:
        use_gui: If True, search for 'sumo-gui'. If False, search for 'sumo'.

    Returns:
        Absolute path to the resolved executable.

    Raises:
        TraCIBridgeError: If the binary could not be found.
    """
    binary_name = "sumo-gui" if use_gui else "sumo"

    # 1. Try sumolib checkBinary if sumolib is available
    if sumolib is not None:
        try:
            bin_path = sumolib.checkBinary(binary_name)
            if bin_path and Path(bin_path).exists():
                return str(Path(bin_path).resolve())
        except Exception:
            pass

    # 2. Try SUMO_HOME environment variable
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        bin_dir = Path(sumo_home) / "bin"
        for ext in ["", ".exe"]:
            candidate = bin_dir / f"{binary_name}{ext}"
            if candidate.exists():
                return str(candidate.resolve())

    # 3. Try system PATH
    which_bin = shutil.which(binary_name) or shutil.which(f"{binary_name}.exe")
    if which_bin:
        return str(Path(which_bin).resolve())

    raise TraCIBridgeError(
        f"SUMO executable '{binary_name}' could not be located. "
        f"Ensure SUMO is installed and SUMO_HOME is set in your environment."
    )


def is_sumo_available(use_gui: bool = False) -> bool:
    """Check if the required SUMO binary and traci package are available."""
    if traci is None:
        return False
    try:
        find_sumo_binary(use_gui=use_gui)
        return True
    except TraCIBridgeError:
        return False


class TraCIBridge:
    """Bridge controller managing SUMO execution and TraCI state retrieval."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        use_gui: bool = False,
        step_length: float | None = None,
        extra_params: list[str] | None = None,
        label: str | None = None,
    ) -> None:
        """Initialize TraCIBridge configuration.

        Args:
            config_path: Path to .sumocfg file. Defaults to urban_grid.sumocfg.
            use_gui: If True, launches sumo-gui. Otherwise launches headless sumo.
            step_length: Simulation step length in seconds (optional override).
            extra_params: Additional command-line flags to pass to SUMO.
            label: Unique TraCI connection label (auto-generated if omitted).
        """
        if config_path is None:
            self._config_path = Path(__file__).resolve().parent / "urban_grid.sumocfg"
        else:
            self._config_path = Path(config_path)

        self._use_gui = use_gui
        self._step_length = step_length
        self._extra_params = list(extra_params) if extra_params is not None else []
        self._label = label or f"urban_grid_{uuid.uuid4().hex[:8]}"
        self._conn: Connection | None = None
        self._is_connected: bool = False
        self._lock = threading.RLock()

    # -------------------------------------------------------------------------
    # Connection Lifecycle
    # -------------------------------------------------------------------------

    @property
    def lock(self) -> threading.RLock:
        """Return the reentrant lock serializing all TraCI access."""
        return self._lock

    def start(self) -> None:
        """Start the SUMO process and establish a TraCI connection.

        Raises:
            TraCIBridgeError: If TraCI is unavailable or connection fails.
            FileNotFoundError: If the configuration file does not exist.
        """
        with self._lock:
            if self._is_connected:
                return

            if traci is None:
                raise TraCIBridgeError("traci package is not installed or available.")

            if not self._config_path.exists():
                raise FileNotFoundError(f"SUMO configuration file not found: {self._config_path}")

            binary_path = find_sumo_binary(use_gui=self._use_gui)

            cmd = [binary_path, "-c", str(self._config_path.resolve())]

            if self._step_length is not None:
                cmd.extend(["--step-length", str(self._step_length)])

            # Sensible defaults for TraCI automation if not explicitly provided
            if "--no-step-log" not in self._extra_params:
                cmd.extend(["--no-step-log", "true"])

            if self._use_gui:
                if "--start" not in self._extra_params:
                    cmd.append("--start")
                if "--quit-on-end" not in self._extra_params:
                    cmd.append("--quit-on-end")

            cmd.extend(self._extra_params)

            try:
                traci.start(cmd, label=self._label)
                self._conn = traci.getConnection(self._label)
                self._is_connected = True
            except Exception as exc:
                self._is_connected = False
                self._conn = None
                raise TraCIBridgeError(f"Failed to start SUMO / TraCI connection: {exc}") from exc

    def connect(self) -> None:
        """Alias for start()."""
        self.start()

    def close(self) -> None:
        """Close the TraCI connection and terminate the SUMO process cleanly.

        Safe to call multiple times or when not connected.
        """
        with self._lock:
            if not self._is_connected or self._conn is None:
                self._is_connected = False
                self._conn = None
                return

            try:
                self._conn.close()
            except Exception:
                pass
            finally:
                self._conn = None
                self._is_connected = False

    def __enter__(self) -> TraCIBridge:
        if not self._is_connected:
            self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # -------------------------------------------------------------------------
    # State & Verification Helpers
    # -------------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return whether the TraCI connection is currently active."""
        with self._lock:
            return self._is_connected and self._conn is not None

    @property
    def label(self) -> str:
        """Return the unique TraCI connection label."""
        return self._label

    @property
    def raw_connection(self) -> Connection:
        """Provide access to the underlying TraCI Connection instance."""
        self._ensure_connected()
        assert self._conn is not None
        return self._conn

    @property
    def simulation_time(self) -> float:
        """Return the current simulation time in seconds."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return float(self._conn.simulation.getTime())

    @property
    def current_time(self) -> float:
        """Alias for simulation_time."""
        return self.simulation_time

    @property
    def has_active_vehicles(self) -> bool:
        """Return True if there are still vehicles running or waiting to be inserted."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return int(self._conn.simulation.getMinExpectedNumber()) > 0

    def _ensure_connected(self) -> None:
        if not self._is_connected or self._conn is None:
            raise TraCIBridgeError("Bridge is not connected to SUMO. Call start() or use context manager.")

    # -------------------------------------------------------------------------
    # Simulation Stepping
    # -------------------------------------------------------------------------

    def step(self, target_time: float | None = None) -> float:
        """Advance the simulation by one step or until target_time.

        Args:
            target_time: Optional target time in seconds.

        Returns:
            Current simulation time after stepping.
        """
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            if target_time is not None:
                self._conn.simulationStep(target_time)
            else:
                self._conn.simulationStep()
            return float(self._conn.simulation.getTime())

    def step_many(self, steps: int) -> float:
        """Advance the simulation by a given number of steps.

        Args:
            steps: Number of simulation steps to advance.

        Returns:
            Current simulation time after stepping.
        """
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            if steps <= 0:
                return float(self._conn.simulation.getTime())
            for _ in range(steps):
                self._conn.simulationStep()
            return float(self._conn.simulation.getTime())

    # -------------------------------------------------------------------------
    # Vehicle State Methods
    # -------------------------------------------------------------------------

    def get_vehicle_ids(self) -> list[str]:
        """Return list of active vehicle IDs in the simulation."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return list(self._conn.vehicle.getIDList())

    def get_vehicle_state(self, vehicle_id: str) -> dict[str, Any]:
        """Return state dictionary for a specific vehicle.

        Args:
            vehicle_id: Vehicle ID.

        Returns:
            Dictionary with vehicle_id, speed, lane_id, position, etc.
        """
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return {
                "vehicle_id": vehicle_id,
                "speed": float(self._conn.vehicle.getSpeed(vehicle_id)),
                "lane_id": str(self._conn.vehicle.getLaneID(vehicle_id)),
                "lane_position": float(self._conn.vehicle.getLanePosition(vehicle_id)),
                "route_id": str(self._conn.vehicle.getRouteID(vehicle_id)),
                "type_id": str(self._conn.vehicle.getTypeID(vehicle_id)),
                "waiting_time": float(self._conn.vehicle.getWaitingTime(vehicle_id)),
            }

    def get_all_vehicles(self) -> list[dict[str, Any]]:
        """Return state dictionaries for all active vehicles."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return [self.get_vehicle_state(vid) for vid in self.get_vehicle_ids()]

    # -------------------------------------------------------------------------
    # Lane State Methods
    # -------------------------------------------------------------------------

    def get_lane_ids(self, include_internal: bool = False) -> list[str]:
        """Return list of lane IDs in the network.

        Args:
            include_internal: If True, includes internal junction lanes (starting with ':').
        """
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            lane_ids = list(self._conn.lane.getIDList())
            if not include_internal:
                lane_ids = [lid for lid in lane_ids if not lid.startswith(":")]
            return lane_ids

    def get_lane_vehicle_count(self, lane_id: str) -> int:
        """Return number of vehicles on the specified lane."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return int(self._conn.lane.getLastStepVehicleNumber(lane_id))

    def get_lane_vehicle_ids(self, lane_id: str) -> list[str]:
        """Return list of vehicle IDs currently on the specified lane."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return list(self._conn.lane.getLastStepVehicleIDs(lane_id))

    def get_lane_state(self, lane_id: str) -> dict[str, Any]:
        """Return state dictionary for a specific lane."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return {
                "lane_id": lane_id,
                "vehicle_count": int(self._conn.lane.getLastStepVehicleNumber(lane_id)),
                "mean_speed": float(self._conn.lane.getLastStepMeanSpeed(lane_id)),
                "occupancy": float(self._conn.lane.getLastStepOccupancy(lane_id)),
                "length": float(self._conn.lane.getLength(lane_id)),
                "max_speed": float(self._conn.lane.getMaxSpeed(lane_id)),
                "vehicle_ids": list(self._conn.lane.getLastStepVehicleIDs(lane_id)),
            }

    def get_all_lanes(self, include_internal: bool = False) -> list[dict[str, Any]]:
        """Return state dictionaries for all lanes."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return [self.get_lane_state(lid) for lid in self.get_lane_ids(include_internal=include_internal)]

    # -------------------------------------------------------------------------
    # Traffic-Light State Methods
    # -------------------------------------------------------------------------

    def get_traffic_light_ids(self) -> list[str]:
        """Return list of traffic light IDs in the network."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return list(self._conn.trafficlight.getIDList())

    def get_traffic_light_state(self, tls_id: str) -> dict[str, Any]:
        """Return live state for a specific traffic light.

        Important: SUMO internal numeric phase IDs remain an internal detail.
        Only the phase name, signal state string ('r/y/g/G'), duration, and
        remaining time are exposed in the standard output.
        """
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            current_time = float(self._conn.simulation.getTime())
            next_switch = float(self._conn.trafficlight.getNextSwitch(tls_id))
            remaining = max(0.0, next_switch - current_time)
            return {
                "tls_id": tls_id,
                "state": str(self._conn.trafficlight.getRedYellowGreenState(tls_id)),
                "phase_name": str(self._conn.trafficlight.getPhaseName(tls_id)),
                "phase_duration": float(self._conn.trafficlight.getPhaseDuration(tls_id)),
                "remaining_phase_time": remaining,
                "next_switch": next_switch,
            }

    def get_all_traffic_lights(self) -> list[dict[str, Any]]:
        """Return live states for all traffic lights."""
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            return [self.get_traffic_light_state(tid) for tid in self.get_traffic_light_ids()]

