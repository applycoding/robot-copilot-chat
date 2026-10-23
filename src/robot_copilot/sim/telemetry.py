from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Frame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t_s: float
    x_m: float
    y_m: float
    alt_m: float
    battery_wh: float
    action_index: int
    event: Literal["takeoff", "waypoint", "hover_start", "photo", "land", "home"] | None = None


class FinalState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_m: float
    y_m: float
    alt_m: float
    battery_wh: float
    landed: bool
    at_home: bool


class PhotoEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t_s: float
    x_m: float
    y_m: float
    alt_m: float
    label: str | None
    action_index: int
