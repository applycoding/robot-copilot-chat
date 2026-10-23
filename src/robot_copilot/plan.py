from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False, strict=True)


class XY(_Strict):
    x_m: float = Field(ge=-10_000, le=10_000)
    y_m: float = Field(ge=-10_000, le=10_000)


class Takeoff(_Strict):
    type: Literal["takeoff"]
    altitude_m: float = Field(description="Target altitude above home, metres")


class Goto(_Strict):
    type: Literal["goto"]
    place: str | None = Field(default=None, max_length=64)
    point_index: int | None = Field(default=None, ge=0)
    xy: XY | None = Field(default=None)
    altitude_m: float | None = Field(default=None)
    speed_mps: float | None = Field(default=None)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        has_place = self.place is not None
        has_xy = self.xy is not None
        if has_place == has_xy:
            raise ValueError("exactly one of place or xy required")
        return self


class Hover(_Strict):
    type: Literal["hover"]
    seconds: float


class Photo(_Strict):
    type: Literal["photo"]
    label: str | None = Field(default=None, max_length=64)


class Land(_Strict):
    type: Literal["land"]


class ReturnHome(_Strict):
    type: Literal["return_home"]


Action = Annotated[
    Takeoff | Goto | Hover | Photo | Land | ReturnHome,
    Field(discriminator="type"),
]


class MissionPlan(_Strict):
    vehicle: Literal["drone", "rover"]
    summary: str = Field(max_length=280)
    actions: tuple[Action, ...] = Field(min_length=1, max_length=200)


class DeclineRequest(_Strict):
    reason: str = Field(min_length=1, max_length=500)
    category: Literal["unsafe", "unsupported", "ambiguous", "out_of_scope"]
