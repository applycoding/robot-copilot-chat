from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

VehicleKind = Literal["drone", "rover"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class _VehicleBase(_Frozen):
    cruise_speed_mps: float
    max_speed_mps: float
    battery_capacity_wh: float
    reserve_pct: float
    photo_s: float
    photo_wh: float
    max_hover_s: float
    max_actions: int
    max_distance_m: float
    max_duration_s: float


class DroneProfile(_VehicleBase):
    kind: Literal["drone"] = "drone"
    vertical_speed_mps: float
    min_altitude_m: float
    max_altitude_m: float
    default_altitude_m: float
    rth_altitude_m: float
    cruise_power_w: float
    hover_power_w: float
    climb_wh_per_m: float


class RoverProfile(_VehicleBase):
    kind: Literal["rover"] = "rover"
    drive_power_w: float
    idle_power_w: float


class VehicleConfigError(Exception):
    pass


def _check_positive(name: str, val: float, problems: list[str]) -> None:
    if val <= 0:
        problems.append(f"{name} must be positive")


def _validate_drone(d: DroneProfile, problems: list[str]) -> None:
    _check_positive("cruise_speed_mps", d.cruise_speed_mps, problems)
    _check_positive("max_speed_mps", d.max_speed_mps, problems)
    _check_positive("vertical_speed_mps", d.vertical_speed_mps, problems)
    _check_positive("battery_capacity_wh", d.battery_capacity_wh, problems)
    _check_positive("cruise_power_w", d.cruise_power_w, problems)
    _check_positive("hover_power_w", d.hover_power_w, problems)
    _check_positive("max_hover_s", d.max_hover_s, problems)
    if d.cruise_speed_mps > d.max_speed_mps:
        problems.append("cruise_speed_mps exceeds max_speed_mps")
    if not (d.min_altitude_m <= d.default_altitude_m <= d.rth_altitude_m <= d.max_altitude_m):
        problems.append("altitude ordering must satisfy min <= default <= rth <= max")
    if d.photo_s < 0 or d.photo_wh < 0 or d.climb_wh_per_m < 0:
        problems.append("photo_s, photo_wh, climb_wh_per_m must be non-negative")
    if not (0 <= d.reserve_pct <= 100):
        problems.append("reserve_pct must be in [0, 100]")
    if d.max_actions < 1:
        problems.append("max_actions must be at least 1")


def _validate_rover(r: RoverProfile, problems: list[str]) -> None:
    _check_positive("cruise_speed_mps", r.cruise_speed_mps, problems)
    _check_positive("max_speed_mps", r.max_speed_mps, problems)
    _check_positive("battery_capacity_wh", r.battery_capacity_wh, problems)
    _check_positive("drive_power_w", r.drive_power_w, problems)
    _check_positive("idle_power_w", r.idle_power_w, problems)
    _check_positive("max_hover_s", r.max_hover_s, problems)
    if r.cruise_speed_mps > r.max_speed_mps:
        problems.append("cruise_speed_mps exceeds max_speed_mps")
    if r.photo_s < 0 or r.photo_wh < 0:
        problems.append("photo_s and photo_wh must be non-negative")
    if not (0 <= r.reserve_pct <= 100):
        problems.append("reserve_pct must be in [0, 100]")
    if r.max_actions < 1:
        problems.append("max_actions must be at least 1")


def load_vehicles(path: Path) -> dict[VehicleKind, DroneProfile | RoverProfile]:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    problems: list[str] = []
    drone = DroneProfile.model_validate(raw["drone"])
    rover = RoverProfile.model_validate(raw["rover"])
    _validate_drone(drone, problems)
    _validate_rover(rover, problems)
    if problems:
        raise VehicleConfigError("; ".join(problems))
    return {"drone": drone, "rover": rover}
