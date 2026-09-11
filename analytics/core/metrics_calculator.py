"""Standardized traffic metrics calculation engine.

This module provides reusable, pure-Python functions to compute core traffic metrics:
average speed, vehicle count, average queue length, maximum queue length,
throughput, and average delay.

All functions are strictly decoupled from SUMO/TraCI internals and web frameworks.
They safely handle empty inputs and prevent division-by-zero errors.
"""

from typing import Any, Mapping, Sequence


def vehicle_count(vehicles: Sequence[Any] | None) -> int:
    """Calculate the total number of unique or active vehicles.

    Args:
        vehicles: A sequence of vehicle identifiers, snapshot records,
            or None.

    Returns:
        The total count of vehicles as a non-negative integer.
        Returns 0 if the input is None or empty.
    """
    if not vehicles:
        return 0
    return len(vehicles)


def average_speed(speeds: Sequence[float | int] | None) -> float:
    """Calculate the arithmetic mean speed of vehicles.

    Args:
        speeds: A sequence of observed speeds (e.g. in m/s or km/h),
            or None.

    Returns:
        The average speed as a float, rounded to 4 decimal places.
        Returns 0.0 if the input is None or empty.
    """
    if not speeds:
        return 0.0
    total = sum(speeds)
    return round(float(total) / len(speeds), 4)


def average_queue_length(queue_lengths: Sequence[float | int] | None) -> float:
    """Calculate the average queue length across observed timesteps or lanes.

    Args:
        queue_lengths: A sequence of observed queue lengths (e.g. in vehicles
            or meters), or None.

    Returns:
        The average queue length as a float, rounded to 4 decimal places.
        Returns 0.0 if the input is None or empty.
    """
    if not queue_lengths:
        return 0.0
    total = sum(queue_lengths)
    return round(float(total) / len(queue_lengths), 4)


def maximum_queue_length(queue_lengths: Sequence[float | int] | None) -> float:
    """Calculate the maximum observed queue length.

    Args:
        queue_lengths: A sequence of observed queue lengths, or None.

    Returns:
        The maximum queue length as a float.
        Returns 0.0 if the input is None or empty.
    """
    if not queue_lengths:
        return 0.0
    return float(max(queue_lengths))


def throughput(
    completed_vehicles: int | Sequence[Any] | None,
    time_window_seconds: float | int,
    per_hour: bool = False,
) -> float:
    """Calculate traffic throughput over a defined observation window.

    Args:
        completed_vehicles: Either the integer count of completed trips,
            a sequence of completed vehicle identifiers/records, or None.
        time_window_seconds: Total duration of the observation window in seconds.
            Must be greater than 0 to compute a rate.
        per_hour: If True, returns vehicles per hour (veh/h).
            If False, returns vehicles per second (veh/s). Default is False.

    Returns:
        Throughput rate as a float, rounded to 4 decimal places.
        Returns 0.0 if time_window_seconds <= 0, completed_vehicles is None/empty,
        or count <= 0.
    """
    if time_window_seconds <= 0 or completed_vehicles is None:
        return 0.0

    if isinstance(completed_vehicles, (int, float)):
        count = float(completed_vehicles)
    else:
        count = float(len(completed_vehicles))

    if count <= 0.0:
        return 0.0

    rate = count / float(time_window_seconds)
    if per_hour:
        rate *= 3600.0

    return round(rate, 4)


def average_delay(
    delays: Sequence[float | int] | None = None,
    actual_travel_times: Sequence[float | int] | None = None,
    free_flow_travel_times: Sequence[float | int] | None = None,
) -> float:
    """Calculate average vehicle delay.

    Accepts either direct delay values or paired actual and free-flow travel times.
    Delay = max(0, actual_travel_time - free_flow_travel_time).

    Args:
        delays: A sequence of vehicle delay values in seconds, or None.
        actual_travel_times: Sequence of observed travel times in seconds.
        free_flow_travel_times: Sequence of theoretical free-flow travel times
            corresponding to the actual travel times.

    Returns:
        Average delay in seconds as a float, rounded to 4 decimal places.
        Returns 0.0 if inputs are None or empty.
    """
    if delays is not None and len(delays) > 0:
        # Direct delays provided: ensure no negative delays from noisy inputs
        sanitized = [max(0.0, float(d)) for d in delays]
        return round(sum(sanitized) / len(sanitized), 4)

    if actual_travel_times and free_flow_travel_times:
        paired = min(len(actual_travel_times), len(free_flow_travel_times))
        if paired == 0:
            return 0.0
        computed_delays = [
            max(0.0, float(actual_travel_times[i]) - float(free_flow_travel_times[i]))
            for i in range(paired)
        ]
        return round(sum(computed_delays) / paired, 4)

    return 0.0


def calculate_traffic_summary(data: Mapping[str, Any]) -> dict[str, float]:
    """Convenience aggregator to compute a standard traffic metrics summary.

    Args:
        data: A dictionary containing traffic observation lists, such as:
            - 'speeds': Sequence[float]
            - 'vehicles': Sequence[Any]
            - 'queue_lengths': Sequence[float]
            - 'completed_vehicles': int or Sequence[Any]
            - 'time_window_seconds': float
            - 'delays': Sequence[float]

    Returns:
        Dictionary mapping metric names to their calculated float values.
    """
    time_window = data.get("time_window_seconds", 0.0)
    return {
        "vehicle_count": float(vehicle_count(data.get("vehicles") or data.get("speeds"))),
        "average_speed": average_speed(data.get("speeds")),
        "average_queue_length": average_queue_length(data.get("queue_lengths")),
        "maximum_queue_length": maximum_queue_length(data.get("queue_lengths")),
        "throughput": throughput(
            data.get("completed_vehicles"),
            time_window_seconds=time_window,
            per_hour=data.get("throughput_per_hour", False),
        ),
        "average_delay": average_delay(
            delays=data.get("delays"),
            actual_travel_times=data.get("actual_travel_times"),
            free_flow_travel_times=data.get("free_flow_travel_times"),
        ),
    }
