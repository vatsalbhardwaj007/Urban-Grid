"""Canonical SignalAction contract for Urban-Grid.

Defines the shared data model for traffic signal timing recommendations
across M1 (AI / Traffic Intelligence) and M2 (SUMO Simulation / Backend).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import math

from pydantic import BaseModel, Field, field_validator


class ActionSource(str, Enum):
    """Originating source of the control action."""

    AI = "AI"
    FALLBACK = "FALLBACK"
    MANUAL = "MANUAL"


class SignalAction(BaseModel):
    """Canonical signal action recommendation for a traffic light intersection."""

    target: str = Field(
        min_length=1,
        description="Identifier of the target SUMO traffic light / intersection."
    )
    green_duration: float = Field(
        gt=0.0,
        description="Recommended green duration in seconds. Must be strictly positive."
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

    @field_validator("green_duration")
    @classmethod
    def validate_green_duration_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("green_duration must be a finite number.")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: object) -> object:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            raise ValueError("timestamp must be an ISO-8601 datetime string or datetime object.")
        return v
