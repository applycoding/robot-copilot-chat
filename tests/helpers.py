from __future__ import annotations

import json
from pathlib import Path

from robot_copilot.geometry import SiteGeometry
from robot_copilot.settings import load_settings
from robot_copilot.site import load_site
from robot_copilot.validator.context import ValidationContext
from robot_copilot.vehicles import load_vehicles

ROOT = Path(__file__).resolve().parents[1]


def default_settings_env(**extra: str) -> dict[str, str]:
    env = {"RCC_DOTENV": "off", "RCC_ROOT": str(ROOT), **extra}
    return env


def load_ctx(vehicle: str = "drone", battery_pct: int = 100) -> ValidationContext:
    s = load_settings(env=default_settings_env(), dotenv_enabled=False)
    site = load_site(s.site_path)
    geom = SiteGeometry.build(site)
    veh = load_vehicles(s.vehicles_path)[vehicle]  # type: ignore[index]
    return ValidationContext(site=site, geometry=geom, vehicle=veh, battery_pct=battery_pct)


def north_fence_plan_json() -> dict:
    return {
        "vehicle": "drone",
        "summary": "inspect north fence",
        "actions": [
            {"type": "takeoff", "altitude_m": 30},
            {"type": "goto", "place": "North Fence", "point_index": 0},
            {"type": "hover", "seconds": 3},
            {"type": "photo"},
            {"type": "goto", "place": "North Fence", "point_index": 1},
            {"type": "hover", "seconds": 3},
            {"type": "photo"},
            {"type": "goto", "place": "North Fence", "point_index": 2},
            {"type": "hover", "seconds": 3},
            {"type": "photo"},
            {"type": "return_home"},
        ],
    }


def plan_from_json(data: dict):
    from robot_copilot.plan import MissionPlan

    return MissionPlan.model_validate_json(json.dumps(data))
