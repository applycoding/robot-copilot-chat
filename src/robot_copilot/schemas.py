from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from robot_copilot.plan import MissionPlan
from robot_copilot.sim.telemetry import FinalState, Frame, PhotoEvent
from robot_copilot.validator.issues import XYZ, PlanStats, ValidationIssue
from robot_copilot.vehicles import VehicleKind


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)
    vehicle: VehicleKind = "drone"
    battery_pct: int = Field(default=100, ge=1, le=100)


class RepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MissionStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    REPAIRING = "repairing"
    DECLINED = "declined"
    REPAIR_EXHAUSTED = "repair_exhausted"
    SUPERSEDED = "superseded"
    EXECUTED = "executed"
    ABORTED = "aborted"


class MissionView(BaseModel):
    id: str
    status: MissionStatus
    revision: int
    vehicle: VehicleKind
    battery_pct: int
    plan: MissionPlan | None
    plan_hash: str | None
    explanation: str
    issues: list[ValidationIssue]
    stats: PlanStats | None
    path_preview: list[XYZ]
    repair_attempts: int
    max_repairs: int
    can_repair: bool
    can_confirm: bool
    confirm_expires_at: datetime | None


class ChatResponse(BaseModel):
    conversation_id: str
    kind: str
    assistant_message: str
    mission: MissionView | None


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class RunView(BaseModel):
    id: str
    mission_id: str
    status: str
    frames: list[Frame]
    photos: list[PhotoEvent]
    final_state: FinalState


class HealthView(BaseModel):
    status: str
    provider: str
    model: str
    site: str
    version: str
    instance: str
