"""Canonical TrafficState v1 contract for Urban-Grid.

Defines the shared data models for traffic state observations at intersections,
consumed across simulation (SUMO), backend API, AI prediction, and downstream services.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LaneFeature(BaseModel):
    """Traffic measurements for an individual lane associated with an intersection."""

    lane_id: str = Field(
        description="Unique identifier of the lane."
    )
    vehicle_count: int = Field(
        ge=0,
        description="Number of vehicles detected on the lane."
    )
    mean_speed: float = Field(
        ge=0.0,
        description="Mean vehicle speed, measured in meters per second."
    )
    queue_length: int = Field(
        ge=0,
        description="Number of queued vehicles."
    )
    occupancy: float = Field(
        ge=0.0,
        description="Lane occupancy represented as a numeric value."
    )
    arrival_rate: float = Field(
        ge=0.0,
        description="Vehicle arrival rate, measured in vehicles per second."
    )
    density: float = Field(
        ge=0.0,
        description="Traffic density represented as vehicles per unit distance."
    )
    flow: float = Field(
        ge=0.0,
        description="Traffic flow represented as vehicles per unit time."
    )


class TrafficState(BaseModel):
    """Canonical traffic state observation for an intersection."""

    timestamp: float = Field(
        ge=0.0,
        description="Simulation/Unix timestamp representing when this traffic state was observed."
    )
    intersection_id: str = Field(
        description="Unique identifier of the intersection."
    )
    lane_features: list[LaneFeature] = Field(
        description="List of traffic measurements for the lanes associated with the intersection."
    )
    total_queue: int = Field(
        ge=0,
        description="Total queued vehicles at the intersection."
    )
    mean_speed: float = Field(
        ge=0.0,
        description="Mean vehicle speed, measured in meters per second."
    )
    arrival_rate: float = Field(
        ge=0.0,
        description="Vehicle arrival rate, measured in vehicles per second."
    )
    density: float = Field(
        ge=0.0,
        description="Traffic density represented as vehicles per unit distance."
    )
    signal_phase: Literal["RED", "YELLOW", "GREEN"] = Field(
        description="Current traffic-signal phase identifier. Must be one of: RED, YELLOW, GREEN."
    )
    green_remaining: float = Field(
        ge=0.0,
        description="Remaining green time for the current signal phase, measured in seconds."
    )
