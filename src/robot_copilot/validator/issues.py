from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from robot_copilot.json_util import canonical_json
from robot_copilot.plan import MissionPlan

VALIDATOR_VERSION: str = "1.0.0"


class IssueCode(StrEnum):
    SCHEMA = "schema"
    MALFORMED_OUTPUT = "malformed_output"
    VEHICLE_MISMATCH = "vehicle_mismatch"
    UNSUPPORTED_ACTION_FOR_VEHICLE = "unsupported_action_for_vehicle"
    SEQUENCE = "sequence"
    UNKNOWN_PLACE = "unknown_place"
    BAD_POINT_INDEX = "bad_point_index"
    ALTITUDE_LOW = "altitude_low"
    ALTITUDE_HIGH = "altitude_high"
    ALTITUDE_ON_GROUND_VEHICLE = "altitude_on_ground_vehicle"
    SPEED_HIGH = "speed_high"
    SPEED_NONPOSITIVE = "speed_nonpositive"
    HOVER_INVALID = "hover_invalid"
    HOVER_TOO_LONG = "hover_too_long"
    TOO_MANY_ACTIONS = "too_many_actions"
    OUTSIDE_GEOFENCE = "outside_geofence"
    ENTERS_KEEP_OUT = "enters_keep_out"
    TOO_LONG_DISTANCE = "too_long_distance"
    TOO_LONG_DURATION = "too_long_duration"
    BATTERY_INSUFFICIENT = "battery_insufficient"
    RTH_RESERVE_VIOLATED = "rth_reserve_violated"
    RTH_PATH_BLOCKED = "rth_path_blocked"
    MUST_END_AT_HOME = "must_end_at_home"


class _Art(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ValidationIssue(_Art):
    code: IssueCode
    severity: Literal["error", "warning"]
    action_index: int | None
    params: tuple[tuple[str, str | int | float], ...]
    message: str
    hint: str


class XYZ(_Art):
    x_m: float
    y_m: float
    alt_m: float


class Leg(_Art):
    action_index: int
    kind: Literal["climb", "move", "descend", "hover", "photo"]
    start: XYZ
    end: XYZ
    speed_mps: float
    distance_m: float
    duration_s: float
    energy_wh: float
    battery_after_wh: float
    rth_wh: float
    rth_margin_wh: float


class PlanStats(_Art):
    distance_m: float
    vertical_m: float
    duration_s: float
    energy_wh: float
    battery_start_wh: float
    battery_end_wh: float
    reserve_wh: float
    photos: int
    min_rth_margin_wh: float


class ResolvedPlan(_Art):
    plan: MissionPlan
    legs: tuple[Leg, ...]
    stats: PlanStats


class ValidationReport(_Art):
    ok: bool
    issues: tuple[ValidationIssue, ...]
    resolved: ResolvedPlan | None
    plan_hash: str | None
    validator_version: str


def issue_sort_key(i: ValidationIssue) -> tuple[int, int, str, str]:
    return (
        0 if i.action_index is None else 1,
        0 if i.action_index is None else i.action_index,
        i.code.value,
        canonical_json(dict(i.params)),
    )
