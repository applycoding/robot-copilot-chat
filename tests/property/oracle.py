"""Analytic oracle for property tests (no shapely)."""

from __future__ import annotations

import math


def segment_in_inset_rect(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
) -> bool:
    """Axis-aligned rectangle containment for a segment (inclusive)."""

    def inside(x: float, y: float) -> bool:
        return xmin <= x <= xmax and ymin <= y <= ymax

    return inside(x1, y1) and inside(x2, y2)


def segment_rect_distance(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    rxmin: float,
    rymin: float,
    rxmax: float,
    rymax: float,
) -> float:
    """Minimum distance from segment to axis-aligned rectangle (0 if intersects)."""

    def dist_point_rect(px: float, py: float) -> float:
        dx = max(rxmin - px, 0, px - rxmax)
        dy = max(rymin - py, 0, py - rymax)
        return math.hypot(dx, dy)

    d = min(dist_point_rect(x1, y1), dist_point_rect(x2, y2))
    return d


def straight_mission_energy_wh(
    *,
    distance_m: float,
    cruise_speed_mps: float,
    cruise_power_w: float,
    climb_m: float,
    climb_wh_per_m: float,
    hover_s: float,
    hover_power_w: float,
    photo_wh: float,
    photos: int,
) -> float:
    move = (distance_m / cruise_speed_mps) * cruise_power_w / 3600
    climb = climb_wh_per_m * climb_m
    hover = hover_power_w * hover_s / 3600
    return move + climb + hover + photo_wh * photos
