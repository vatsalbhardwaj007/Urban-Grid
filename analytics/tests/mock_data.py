"""=============================================================================
TEST DATA ONLY — SYNTHETIC MOCK DATASETS FOR UNIT & INTEGRATION TESTING
=============================================================================
WARNING: The numbers in this file are purely synthetic test fixtures.
They are NOT real Urban Grid experimental results or benchmark data.
They are strictly used to verify mathematical formulas, edge cases,
and comparator logic in automated tests.
=============================================================================
"""

from typing import Any

# ---------------------------------------------------------------------------
# 1. Empty Dataset (Edge Case: no traffic, empty network, uninitialized run)
# ---------------------------------------------------------------------------
MOCK_EMPTY_DATASET: dict[str, Any] = {
    "_label": "TEST DATA ONLY - EMPTY NETWORK",
    "vehicles": [],
    "speeds": [],
    "queue_lengths": [],
    "completed_vehicles": [],
    "time_window_seconds": 0.0,
    "delays": [],
    "actual_travel_times": [],
    "free_flow_travel_times": [],
}

# ---------------------------------------------------------------------------
# 2. Simple Known Dataset (Trivial numbers where answers are mathematically obvious)
#    - speeds: [10.0, 20.0, 30.0] -> avg = 20.0
#    - vehicles: ["veh_1", "veh_2", "veh_3"] -> count = 3
#    - queue_lengths: [2.0, 4.0, 6.0, 8.0] -> avg = 5.0, max = 8.0
#    - completed_vehicles: 60, time_window_seconds: 60.0 -> throughput = 1.0 veh/s (3600 veh/h)
#    - delays: [10.0, 20.0, 30.0] -> avg = 20.0
# ---------------------------------------------------------------------------
MOCK_KNOWN_DATASET: dict[str, Any] = {
    "_label": "TEST DATA ONLY - SIMPLE KNOWN FIXTURE",
    "vehicles": ["veh_1", "veh_2", "veh_3"],
    "speeds": [10.0, 20.0, 30.0],
    "queue_lengths": [2.0, 4.0, 6.0, 8.0],
    "completed_vehicles": 60,
    "time_window_seconds": 60.0,
    "delays": [10.0, 20.0, 30.0],
    "actual_travel_times": [50.0, 60.0, 70.0],
    "free_flow_travel_times": [40.0, 40.0, 40.0],  # delays: [10.0, 20.0, 30.0] -> avg 20.0
}

# ---------------------------------------------------------------------------
# 3. Synthetic Baseline Dataset (Fixed-time signals, high delay, lower speed)
# ---------------------------------------------------------------------------
MOCK_BASELINE_DATASET: dict[str, Any] = {
    "_label": "TEST DATA ONLY - SYNTHETIC BASELINE RUN",
    "vehicles": [f"veh_base_{i}" for i in range(1, 11)],
    "speeds": [12.0, 15.0, 14.0, 11.0, 13.0, 10.0, 16.0, 12.0, 14.0, 13.0],  # sum=130, avg=13.0
    "queue_lengths": [8.0, 12.0, 15.0, 10.0, 15.0],  # sum=60, avg=12.0, max=15.0
    "completed_vehicles": 120,
    "time_window_seconds": 3600.0,  # 120 veh/h
    "delays": [45.0, 55.0, 50.0, 60.0, 40.0],  # sum=250, avg=50.0
}

# ---------------------------------------------------------------------------
# 4. Synthetic Urban Grid Dataset (AI-optimized signals, reduced delay, higher speed)
# ---------------------------------------------------------------------------
MOCK_URBAN_GRID_DATASET: dict[str, Any] = {
    "_label": "TEST DATA ONLY - SYNTHETIC URBAN GRID OPTIMIZED RUN",
    "vehicles": [f"veh_ug_{i}" for i in range(1, 11)],
    "speeds": [18.0, 20.0, 19.0, 21.0, 22.0, 20.0, 19.0, 21.0, 20.0, 20.0],  # sum=200, avg=20.0
    "queue_lengths": [3.0, 4.0, 5.0, 2.0, 6.0],  # sum=20, avg=4.0, max=6.0
    "completed_vehicles": 150,
    "time_window_seconds": 3600.0,  # 150 veh/h
    "delays": [25.0, 30.0, 20.0, 25.0, 25.0],  # sum=125, avg=25.0
}

# ---------------------------------------------------------------------------
# 5. Pre-calculated Summary Dictionaries for Direct Comparator Testing
# ---------------------------------------------------------------------------
MOCK_BASELINE_METRICS_SUMMARY: dict[str, float] = {
    "average_speed": 13.0,
    "average_queue_length": 12.0,
    "maximum_queue_length": 15.0,
    "throughput": 120.0,
    "average_delay": 50.0,
    "vehicle_count": 10.0,
}

MOCK_URBAN_GRID_METRICS_SUMMARY: dict[str, float] = {
    "average_speed": 20.0,
    "average_queue_length": 4.0,
    "maximum_queue_length": 6.0,
    "throughput": 150.0,
    "average_delay": 25.0,
    "vehicle_count": 10.0,
}
