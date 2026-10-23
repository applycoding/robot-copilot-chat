from __future__ import annotations

from shapely.geometry import LineString, Point

from robot_copilot.geometry import SiteGeometry
from robot_copilot.validator.issues import XYZ


def segment_outside_fence(geometry: SiteGeometry, start: XYZ, end: XYZ) -> bool:
    if start.x_m == end.x_m and start.y_m == end.y_m and start.alt_m == end.alt_m:
        pt = Point(start.x_m, start.y_m)
        return not geometry.fence_inset.covers(pt)
    line = LineString([(start.x_m, start.y_m), (end.x_m, end.y_m)])
    return not geometry.fence_inset.covers(line)


def segment_hits_keepout(geometry: SiteGeometry, start: XYZ, end: XYZ) -> str | None:
    if start.x_m == end.x_m and start.y_m == end.y_m:
        pt = Point(start.x_m, start.y_m)
        geom = pt
    else:
        geom = LineString([(start.x_m, start.y_m), (end.x_m, end.y_m)])
    for name, poly in geometry.keep_outs:
        if poly.intersects(geom):
            return name
    return None


def rth_segment_blocked(
    geometry: SiteGeometry, x: float, y: float, home: tuple[float, float]
) -> bool:
    hx, hy = home
    if x == hx and y == hy:
        return False
    line = LineString([(x, y), (hx, hy)])
    if not geometry.fence_inset.covers(line):
        return True
    return any(poly.intersects(line) for _, poly in geometry.keep_outs)
