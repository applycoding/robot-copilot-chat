from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from robot_copilot.plan import DeclineRequest, MissionPlan
from robot_copilot.site import Site
from robot_copilot.vehicles import DroneProfile, RoverProfile, VehicleKind

PROPOSE_TOOL = "propose_mission_plan"
DECLINE_TOOL = "decline_request"


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


def _strip_meta(schema: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k in ("title", "discriminator", "$defs", "definitions"):
            continue
        if isinstance(v, dict):
            out[k] = _strip_meta(v)
        elif isinstance(v, list):
            out[k] = [_strip_meta(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


def _inline_refs(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        ref = schema["$ref"]
        name = ref.split("/")[-1]
        return _inline_refs(defs[name].copy(), defs)
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k == "$ref":
            continue
        if isinstance(v, dict):
            out[k] = _inline_refs(v, defs)
        elif isinstance(v, list):
            out[k] = [_inline_refs(x, defs) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.get("$defs", {})
    base = {k: v for k, v in raw.items() if k not in ("$defs",)}
    inlined = _inline_refs(base, defs)
    return _strip_meta(inlined)


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name=PROPOSE_TOOL,
            description="Propose a mission plan as structured actions.",
            parameters=inline_schema(MissionPlan),
        ),
        ToolSpec(
            name=DECLINE_TOOL,
            description="Decline a mission request that cannot be fulfilled safely.",
            parameters=inline_schema(DeclineRequest),
        ),
    ]


class SiteSummary(BaseModel):
    site_name: str
    places: list[dict[str, Any]]
    keep_outs: list[str]
    limits: dict[str, float]


def build_site_summary(site: Site, vehicle: DroneProfile | RoverProfile) -> SiteSummary:
    places = [
        {
            "name": p.name,
            "aliases": list(p.aliases),
            "kind": p.kind,
            "point_count": len(p.points),
        }
        for p in site.places
    ]
    limits: dict[str, float] = {
        "max_actions": float(vehicle.max_actions),
        "max_distance_m": vehicle.max_distance_m,
        "max_duration_s": vehicle.max_duration_s,
        "max_hover_s": vehicle.max_hover_s,
        "max_speed_mps": vehicle.max_speed_mps,
    }
    if isinstance(vehicle, DroneProfile):
        limits.update(
            {
                "min_altitude_m": vehicle.min_altitude_m,
                "max_altitude_m": vehicle.max_altitude_m,
                "default_altitude_m": vehicle.default_altitude_m,
            }
        )
    return SiteSummary(
        site_name=site.name,
        places=places,
        keep_outs=[k.name for k in site.keep_out],
        limits=limits,
    )


def build_system_prompt(summary: SiteSummary, vehicle: VehicleKind) -> str:
    place_lines = ", ".join(p["name"] for p in summary.places)
    return (
        f"You are a mission planning assistant for a {vehicle} at site {summary.site_name}. "
        f"Use metres and only these places: {place_lines}. "
        "For any mission-like request call exactly one tool. "
        "Never claim to execute anything. "
        "Answer greetings and general questions in plain text without tools."
    )
