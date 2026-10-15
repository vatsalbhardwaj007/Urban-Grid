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

# ---------------------------------------------------------------------------
# 6. M2 Canonical TrafficState Test Fixtures (TEST DATA ONLY)
# ---------------------------------------------------------------------------
MOCK_TRAFFIC_STATE_EMPTY: dict[str, Any] = {
    "_label": "TEST DATA ONLY - EMPTY TRAFFIC STATE",
    "timestamp": 0.0,
    "intersection_id": "int_0",
    "lane_features": [],
    "total_queue": 0.0,
    "mean_speed": 0.0,
    "arrival_rate": 0.0,
    "density": 0.0,
    "signal_phase": 0,
    "green_remaining": 0.0,
}

MOCK_TRAFFIC_STATE_SINGLE: dict[str, Any] = {
    "_label": "TEST DATA ONLY - SINGLE INTERSECTION SNAPSHOT",
    "timestamp": 10.0,
    "intersection_id": "int_main_1",
    "lane_features": [
        {
            "lane_id": "lane_north_0",
            "vehicle_count": 4,
            "mean_speed": 12.0,
            "queue_length": 3.0,
            "occupancy": 0.25,
            "arrival_rate": 1.2,
            "density": 20.0,
            "flow": 15.0,
        },
        {
            "lane_id": "lane_south_0",
            "vehicle_count": 6,
            "mean_speed": 14.0,
            "queue_length": 5.0,
            "occupancy": 0.35,
            "arrival_rate": 1.8,
            "density": 30.0,
            "flow": 25.0,
        },
    ],
    "total_queue": 8.0,
    "mean_speed": 13.0,
    "arrival_rate": 3.0,
    "density": 25.0,
    "signal_phase": 2,
    "green_remaining": 15.5,
}

# Baseline run: 3 timesteps with high queues and sluggish speeds
MOCK_TRAFFIC_STATE_BASELINE_STREAM: list[dict[str, Any]] = [
    {
        "_label": "TEST DATA ONLY - BASELINE TIMESTEP 0",
        "timestamp": 0.0,
        "intersection_id": "int_main_1",
        "lane_features": [
            {
                "lane_id": "lane_0",
                "vehicle_count": 8,
                "mean_speed": 9.0,
                "queue_length": 7.0,
                "occupancy": 0.40,
                "arrival_rate": 2.0,
                "density": 40.0,
                "flow": 10.0,
            },
            {
                "lane_id": "lane_1",
                "vehicle_count": 10,
                "mean_speed": 7.0,
                "queue_length": 9.0,
                "occupancy": 0.50,
                "arrival_rate": 2.5,
                "density": 50.0,
                "flow": 12.0,
            },
        ],
        "total_queue": 16.0,
        "mean_speed": 8.0,
        "arrival_rate": 4.5,
        "density": 45.0,
        "signal_phase": 1,
        "green_remaining": 5.0,
    },
    {
        "_label": "TEST DATA ONLY - BASELINE TIMESTEP 10",
        "timestamp": 10.0,
        "intersection_id": "int_main_1",
        "lane_features": [
            {
                "lane_id": "lane_0",
                "vehicle_count": 10,
                "mean_speed": 8.0,
                "queue_length": 9.0,
                "occupancy": 0.55,
                "arrival_rate": 2.2,
                "density": 48.0,
                "flow": 11.0,
            },
            {
                "lane_id": "lane_1",
                "vehicle_count": 12,
                "mean_speed": 6.0,
                "queue_length": 11.0,
                "occupancy": 0.65,
                "arrival_rate": 2.8,
                "density": 60.0,
                "flow": 13.0,
            },
        ],
        "total_queue": 20.0,
        "mean_speed": 7.0,
        "arrival_rate": 5.0,
        "density": 54.0,
        "signal_phase": 1,
        "green_remaining": 0.0,
    },
]

# Urban Grid run: same demand scenario, AI-optimized signal progression
MOCK_TRAFFIC_STATE_URBAN_GRID_STREAM: list[dict[str, Any]] = [
    {
        "_label": "TEST DATA ONLY - URBAN GRID TIMESTEP 0",
        "timestamp": 0.0,
        "intersection_id": "int_main_1",
        "lane_features": [
            {
                "lane_id": "lane_0",
                "vehicle_count": 4,
                "mean_speed": 16.0,
                "queue_length": 2.0,
                "occupancy": 0.18,
                "arrival_rate": 2.0,
                "density": 18.0,
                "flow": 18.0,
            },
            {
                "lane_id": "lane_1",
                "vehicle_count": 5,
                "mean_speed": 18.0,
                "queue_length": 3.0,
                "occupancy": 0.22,
                "arrival_rate": 2.5,
                "density": 22.0,
                "flow": 22.0,
            },
        ],
        "total_queue": 5.0,
        "mean_speed": 17.0,
        "arrival_rate": 4.5,
        "density": 20.0,
        "signal_phase": 2,
        "green_remaining": 20.0,
    },
    {
        "_label": "TEST DATA ONLY - URBAN GRID TIMESTEP 10",
        "timestamp": 10.0,
        "intersection_id": "int_main_1",
        "lane_features": [
            {
                "lane_id": "lane_0",
                "vehicle_count": 3,
                "mean_speed": 19.0,
                "queue_length": 1.0,
                "occupancy": 0.15,
                "arrival_rate": 2.2,
                "density": 15.0,
                "flow": 20.0,
            },
            {
                "lane_id": "lane_1",
                "vehicle_count": 4,
                "mean_speed": 21.0,
                "queue_length": 2.0,
                "occupancy": 0.18,
                "arrival_rate": 2.8,
                "density": 18.0,
                "flow": 24.0,
            },
        ],
        "total_queue": 3.0,
        "mean_speed": 20.0,
        "arrival_rate": 5.0,
        "density": 16.5,
        "signal_phase": 2,
        "green_remaining": 10.0,
    },
]

# ---------------------------------------------------------------------------
# 7. Multi-Intersection Service Layer Test Fixtures (dict[str, TrafficState])
# ---------------------------------------------------------------------------
MOCK_MULTI_INTERSECTION_SNAPSHOT: dict[str, Any] = {
    "int_main_1": MOCK_TRAFFIC_STATE_SINGLE,
    "int_side_2": {
        "_label": "TEST DATA ONLY - SECOND INTERSECTION SNAPSHOT",
        "timestamp": 10.0,
        "intersection_id": "int_side_2",
        "lane_features": [
            {
                "lane_id": "lane_east_0",
                "vehicle_count": 2,
                "mean_speed": 16.0,
                "queue_length": 1.0,
                "occupancy": 0.10,
                "arrival_rate": 0.8,
                "density": 12.0,
                "flow": 10.0,
            }
        ],
        "total_queue": 1.0,
        "mean_speed": 16.0,
        "arrival_rate": 0.8,
        "density": 12.0,
        "signal_phase": 1,
        "green_remaining": 8.0,
    },
}

MOCK_SERVICE_BASELINE_RUN: list[dict[str, Any]] = [
    {"int_main_1": MOCK_TRAFFIC_STATE_BASELINE_STREAM[0]},
    {"int_main_1": MOCK_TRAFFIC_STATE_BASELINE_STREAM[1]},
]

MOCK_SERVICE_URBAN_GRID_RUN: list[dict[str, Any]] = [
    {"int_main_1": MOCK_TRAFFIC_STATE_URBAN_GRID_STREAM[0]},
    {"int_main_1": MOCK_TRAFFIC_STATE_URBAN_GRID_STREAM[1]},
]
