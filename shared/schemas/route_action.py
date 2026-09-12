"""Canonical RouteAction contract for Urban-Grid.

Defines the shared data model for vehicle rerouting directives
across M1 (AI / Traffic Intelligence) and M2 (SUMO Simulation / Backend).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ActionSource(str, Enum):
    """Originating source of the control action."""

    AI = "AI"
    FALLBACK = "FALLBACK"
    MANUAL = "MANUAL"


class RouteAction(BaseModel):
    """Canonical route action directive for a vehicle."""

    target: str = Field(
        min_length=1,
        description="Identifier of the target SUMO vehicle."
    )
    route: list[str] = Field(
        min_length=1,
        description="Ordered list of SUMO edge IDs defining the rerouted path."
    )
    source: ActionSource = Field(
        description="Originating source of the action. Must be one of: AI, FALLBACK, MANUAL."
    )
    timestamp: datetime = Field(
        description="ISO-8601 datetime representing when the action was generated."
    )

    @field_validator("target")
    @classmethod
    def validate_target(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("target must be a non-empty string.")
        return v

    @field_validator("route")
    @classmethod
    def validate_route(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("route must contain at least one edge ID.")
        for idx, edge in enumerate(v):
            if not isinstance(edge, str) or not edge.strip():
                raise ValueError(f"route edge at index {idx} must be a non-empty string.")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: object) -> object:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            raise ValueError("timestamp must be an ISO-8601 datetime string or datetime object.")
        return v
