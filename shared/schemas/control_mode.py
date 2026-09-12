"""Canonical ControlMode contract for Urban-Grid.

Defines the system operating modes governing how control actions reach TraCI/SUMO:
- AUTO: Normal closed-loop AI operation (TrafficState -> M1 AI -> Action -> SUMO).
- MANUAL: Operator manual control (operator actions reach SUMO; M1 AI actions are suppressed).
- EMERGENCY: Emergency override (AI actions suppressed; deterministic emergency policy controls SUMO).
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class ControlMode(str, Enum):
    """System control mode governing actuation dispatch to SUMO."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


class ControlModeResponse(BaseModel):
    """Structured response model reporting current control mode state."""

    mode: ControlMode = Field(description="Currently active control mode.")
    description: str = Field(description="Human-readable explanation of active control mode.")
    previous_mode: ControlMode | None = Field(
        default=None,
        description="Previous control mode prior to the latest transition, if known.",
    )


class SetControlModeRequest(BaseModel):
    """Request model for setting system control mode."""

    mode: ControlMode = Field(description="Target control mode to activate (AUTO, MANUAL, EMERGENCY).")
