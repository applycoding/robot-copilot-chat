from __future__ import annotations

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from robot_copilot.geometry import SiteGeometry
from robot_copilot.validator.issues import XYZ


def segment_outside_fence(geometry: SiteGeometry, start: XYZ, end: XYZ) -> bool:
    if start.x_m == end.x_m and start.y_m == end.y_m and start.alt_m == end.alt_m:
        pt = Point(start.x_m, start.y_m)
        return not geometry.fence_inset.covers(pt)
    line = LineString([(start.x_m, start.y_m), (end.x_m, end.y_m)])
    return not geometry.fence_inset.covers(line)


def _segment_geom(start: XYZ, end: XYZ) -> BaseGeometry:
    if start.x_m == end.x_m and start.y_m == end.y_m and start.alt_m == end.alt_m:
        return Point(start.x_m, start.y_m)
    return LineString([(start.x_m, start.y_m), (end.x_m, end.y_m)])


def segment_keepouts_hit(geometry: SiteGeometry, start: XYZ, end: XYZ) -> list[str]:
    """Return every keep-out name whose buffered polygon intersects the segment.

    Keep-out margins from site TOML are applied when SiteGeometry is built.
    """
    geom = _segment_geom(start, end)
    hits: list[str] = []
    for name, poly in geometry.keep_outs:
        if not poly.intersects(geom):
            continue
        hits.append(name)
    return hits


def segment_hits_keepout(geometry: SiteGeometry, start: XYZ, end: XYZ) -> str | None:
    hits = segment_keepouts_hit(geometry, start, end)
    return hits[0] if hits else None


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
