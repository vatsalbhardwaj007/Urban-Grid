"""Concurrency and serialization tests for shared TraCI connection access.

Ensures that:
1. TraCIBridge._lock serializes all access to the shared self._conn.
2. Concurrent simulation stepping, sensor readings, and signal actuations
   execute without deadlocks or TraCI socket protocol desynchronization.
3. The lock is properly reentrant (RLock) allowing nested operations.
"""

from __future__ import annotations

import concurrent.futures
import threading
from datetime import datetime, timezone

import pytest

from shared.schemas.route_action import ActionSource
from shared.schemas.signal_action import SignalAction
from simulation.sumo.actuation import ActionDispatcher, SignalActuator
from simulation.sumo.state_provider import TrafficStateProvider
from simulation.sumo.traci_bridge import TraCIBridge, is_sumo_available

REQUIRES_SUMO = pytest.mark.skipif(
    not is_sumo_available(),
    reason="SUMO executable or traci package is unavailable in this environment.",
)


@pytest.fixture
def running_bridge():
    """Start and yield a live TraCIBridge, then cleanly close it."""
    bridge = TraCIBridge()
    bridge.start()
    yield bridge
    bridge.close()


class TestTraCISerialization:
    """Test suite verifying serialization of TraCI access across threads."""

    def test_bridge_lock_is_reentrant(self, disconnected_bridge: TraCIBridge = None) -> None:
        """Verify bridge.lock is a threading.RLock and supports reentrancy."""
        bridge = TraCIBridge()
        assert isinstance(bridge.lock, type(threading.RLock()))

        # Reentrant acquisition on the same thread must succeed
        with bridge.lock:
            with bridge.lock:
                assert True

    @REQUIRES_SUMO
    def test_concurrent_stepping_and_actuation(self, running_bridge: TraCIBridge) -> None:
        """Verify concurrent steps and signal actuations across threads do not crash or deadlock."""
        provider = TrafficStateProvider(running_bridge)
        actuator = SignalActuator(running_bridge)

        errors: list[Exception] = []
        step_results: list[dict] = []
        actuation_results: list[dict] = []

        def step_worker(worker_id: int):
            try:
                for _ in range(5):
                    states = provider.step_and_get_states(steps=1)
                    step_results.append(states)
            except Exception as exc:
                errors.append(exc)

        def actuation_worker(worker_id: int):
            try:
                for i in range(5):
                    action = SignalAction(
                        target="I1",
                        green_duration=25.0 + (i % 10),
                        source=ActionSource.AI,
                        timestamp=datetime.now(timezone.utc),
                    )
                    res = actuator.apply(action)
                    actuation_results.append(res.model_dump(mode="json"))
            except Exception as exc:
                errors.append(exc)

        # Run 2 step workers and 2 actuation workers simultaneously
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            f1 = executor.submit(step_worker, 1)
            f2 = executor.submit(step_worker, 2)
            f3 = executor.submit(actuation_worker, 1)
            f4 = executor.submit(actuation_worker, 2)
            concurrent.futures.wait([f1, f2, f3, f4], timeout=30.0)

        assert not errors, f"Concurrent workers encountered errors: {errors}"
        assert len(step_results) == 10
        assert len(actuation_results) == 10
        assert running_bridge.is_connected

    @REQUIRES_SUMO
    def test_concurrent_queries_and_dispatcher(self, running_bridge: TraCIBridge) -> None:
        """Verify concurrent dispatcher actuations and state reads execute safely."""
        provider = TrafficStateProvider(running_bridge)
        dispatcher = ActionDispatcher(running_bridge)

        errors: list[Exception] = []

        def reader_task():
            try:
                for _ in range(8):
                    _ = provider.get_all_states()
                    _ = running_bridge.get_all_lanes()
                    _ = running_bridge.get_traffic_light_ids()
            except Exception as exc:
                errors.append(exc)

        def writer_task():
            try:
                for i in range(8):
                    action = SignalAction(
                        target="I2",
                        green_duration=20.0 + (i % 15),
                        source=ActionSource.AI,
                        timestamp=datetime.now(timezone.utc),
                    )
                    _ = dispatcher.dispatch(action)
            except Exception as exc:
                errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(reader_task),
                executor.submit(reader_task),
                executor.submit(writer_task),
                executor.submit(writer_task),
            ]
            concurrent.futures.wait(futures, timeout=30.0)

        assert not errors, f"Errors encountered during concurrent queries: {errors}"
        assert running_bridge.is_connected
