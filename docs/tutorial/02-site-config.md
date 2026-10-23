# 02 Site configuration and geometry

## Goal

You will load the demo farm from TOML and understand how names, polygons, and margins become validator-ready geometry. Sites are frozen Pydantic models so aliases and coordinates cannot mutate at runtime. Shapely builds an inset geofence and expanded keep-outs before any mission segment is tested, which catches bad polygons at import time instead of mid-chat.

Places may be points or paths; path vertices become multiple goto legs during resolution, which is why inspect missions over North Fence look longer than a single hop to Barn. Keep-out margins are intentionally larger than the geofence inset so hover missions cannot skim hazard borders. Loading errors aggregate every problem in `SiteConfigError` so misconfigured TOML fails fast at startup rather than mid-mission.

## Files

- `config/sites/demo_farm.toml`
- `src/robot_copilot/site.py`
- `src/robot_copilot/geometry.py`

## Walkthrough

1. Name normalization in `site.py` is shared by the mock provider and fuzzy suggestions for unknown places. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
```

Stripping punctuation and a leading article lets `BARN.` and `the barn` resolve to the same configured place. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. `SiteGeometry.build` turns the raw fence and keep-out list into buffered polygons used by spatial checks. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    def build(cls, site: Site) -> SiteGeometry:
        fence = Polygon(site.geofence)
        inset = fence.buffer(-site.geofence_margin_m)
        if inset.is_empty or inset.geom_type != "Polygon":
            raise ValueError("invalid fence inset")
        keep_outs = tuple(
            (ko.name, Polygon(ko.polygon).buffer(ko.margin_m)) for ko in site.keep_out
        )
        return cls(fence_inset=inset, keep_outs=keep_outs)
```

Negative buffering on the geofence shrinks the flyable area, while positive buffering on keep-outs adds safety margin around hazards. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. Each `Site` exposes a fingerprint used when hashing validated plans. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        return digest
```

Changing coordinates or margins in TOML invalidates stored confirmation hashes, which is intentional. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -c "
from robot_copilot.site import load_site, resolve_place
from pathlib import Path
site = load_site(Path('config/sites/demo_farm.toml'))
print(resolve_place(site, 'the barn').name)
"
```

Expected:

```
Barn
```

## Exercise

Add a temporary alias on `Pond` in `demo_farm.toml`, restart the app, chat using that alias, then remove the alias. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/unit/test_site.py::test_normalize_and_resolve`
