from __future__ import annotations

from dataclasses import dataclass

from robot_copilot.geometry import SiteGeometry
from robot_copilot.site import Site
from robot_copilot.vehicles import DroneProfile, RoverProfile


@dataclass(frozen=True)
class ValidationContext:
    site: Site
    geometry: SiteGeometry
    vehicle: DroneProfile | RoverProfile
    battery_pct: int
