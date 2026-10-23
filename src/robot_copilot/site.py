from __future__ import annotations

import difflib
import hashlib
import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from robot_copilot.json_util import canonical_json

Coord = tuple[float, float]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Place(_Frozen):
    name: str = Field(min_length=1, max_length=64)
    aliases: tuple[str, ...] = ()
    kind: Literal["point", "path"]
    points: tuple[Coord, ...] = Field(min_length=1)


class KeepOut(_Frozen):
    name: str
    polygon: tuple[Coord, ...] = Field(min_length=3)
    margin_m: float = Field(ge=0)


class Site(_Frozen):
    id: str
    name: str
    home: Coord
    geofence: tuple[Coord, ...] = Field(min_length=3)
    geofence_margin_m: float = Field(ge=0)
    keep_out: tuple[KeepOut, ...] = ()
    places: tuple[Place, ...]

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        return digest


class SiteConfigError(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_name(text: str) -> str:
    t = text.casefold()
    t = _PUNCT_RE.sub(" ", t)
    t = " ".join(t.split())
    if t.startswith("the "):
        t = t[4:]
    return t.strip()


def load_site(path: Path) -> Site:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    site_raw = raw.get("site", {})
    keep_outs_raw = raw.get("keep_out", [])
    places_raw = raw.get("places", [])

    def coord(c: list[float]) -> Coord:
        return (float(c[0]), float(c[1]))

    site = Site(
        id=str(site_raw["id"]),
        name=str(site_raw["name"]),
        home=coord(site_raw["home"]),
        geofence=tuple(coord(p) for p in site_raw["geofence"]),
        geofence_margin_m=float(site_raw.get("geofence_margin_m", 0)),
        keep_out=tuple(
            KeepOut(
                name=str(k["name"]),
                polygon=tuple(coord(p) for p in k["polygon"]),
                margin_m=float(k.get("margin_m", 0)),
            )
            for k in keep_outs_raw
        ),
        places=tuple(
            Place(
                name=str(p["name"]),
                aliases=tuple(str(a) for a in p.get("aliases", [])),
                kind=p["kind"],
                points=tuple(coord(pt) for pt in p["points"]),
            )
            for p in places_raw
        ),
    )
    _validate_site(site)
    return site


def _validate_site(site: Site) -> None:
    from shapely.geometry import LineString, Point, Polygon
    from shapely.validation import explain_validity

    problems: list[str] = []

    fence = Polygon(site.geofence)
    if not fence.is_valid:
        problems.append(f"geofence invalid: {explain_validity(fence)}")

    try:
        inset = fence.buffer(-site.geofence_margin_m)
    except Exception as exc:
        problems.append(f"geofence inset failed: {exc}")
        raise SiteConfigError(problems) from exc

    if inset.is_empty:
        problems.append("geofence inset is empty")
    elif inset.geom_type == "MultiPolygon":
        problems.append("geofence inset splits into multiple parts")
    elif inset.geom_type != "Polygon":
        problems.append(f"geofence inset has unexpected type {inset.geom_type}")

    if problems:
        raise SiteConfigError(problems)

    assert isinstance(inset, Polygon)
    buffered_keepouts: list[tuple[str, Polygon]] = []
    for ko in site.keep_out:
        if ko.margin_m < 0:
            problems.append(f"keep-out {ko.name} has negative margin")
        poly = Polygon(ko.polygon)
        if not poly.is_valid:
            problems.append(f"keep-out {ko.name} invalid: {explain_validity(poly)}")
        buffered_keepouts.append((ko.name, poly.buffer(ko.margin_m)))

    names_seen: set[str] = set()
    for place in site.places:
        if place.kind == "point" and len(place.points) != 1:
            problems.append(f"place {place.name} kind=point must have exactly 1 point")
        if place.kind == "path" and len(place.points) < 2:
            problems.append(f"place {place.name} kind=path needs at least 2 points")
        for label in (place.name, *place.aliases):
            norm = normalize_name(label)
            if norm in names_seen:
                problems.append(f"duplicate normalized name: {label}")
            names_seen.add(norm)

    home_pt = Point(site.home)
    if not inset.covers(home_pt):
        problems.append("home is outside the geofence inset")
    for name, buf in buffered_keepouts:
        if buf.intersects(home_pt):
            problems.append(f"home intersects buffered keep-out {name}")

    for place in site.places:
        pts = list(place.points)
        segments: list[LineString] = []
        if place.kind == "path":
            segments = [LineString(pts)]
        for pt in pts:
            p = Point(pt)
            if not inset.covers(p):
                problems.append(f"place {place.name} point {pt} outside geofence inset")
            for kn, buf in buffered_keepouts:
                if buf.intersects(p):
                    problems.append(f"place {place.name} point {pt} intersects keep-out {kn}")
        for seg in segments:
            if not inset.covers(seg):
                problems.append(f"place {place.name} path segment outside geofence inset")
            for kn, buf in buffered_keepouts:
                if buf.intersects(seg):
                    problems.append(f"place {place.name} path intersects keep-out {kn}")

    if problems:
        raise SiteConfigError(problems)


def resolve_place(site: Site, name: str) -> Place | None:
    target = normalize_name(name)
    for place in site.places:
        if normalize_name(place.name) == target:
            return place
        for alias in place.aliases:
            if normalize_name(alias) == target:
                return place
    return None


def suggest_places(site: Site, name: str, n: int = 3) -> list[str]:
    choices = [p.name for p in site.places]
    target = normalize_name(name)
    matches = difflib.get_close_matches(
        target, [normalize_name(c) for c in choices], n=n, cutoff=0.6
    )
    result: list[str] = []
    for m in matches:
        for p in site.places:
            if normalize_name(p.name) == m:
                result.append(p.name)
                break
    return result[:n]
