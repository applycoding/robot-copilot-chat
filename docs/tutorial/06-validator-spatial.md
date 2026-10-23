# 06 Spatial validator and RTH paths

## Goal

You will see how resolved legs are tested against the inset geofence and buffered keep-outs. Segment helpers treat zero-length moves as point checks and longer moves as line strings. Return-to-home simulation adds a straight segment to home and rejects plans when that path leaves the fence or crosses a keep-out.

Resolution expands named places to coordinates before spatial checks run, so unknown places fail in structure or resolve stages before Shapely sees segments. Concave geofences rely on polygon coverage rather than bounding boxes, which matches irregular farm shapes in the demo TOML. Map previews use the same geometry objects, so a keep-out highlighted in the UI is exactly what blocked validation.

## Files

- `src/robot_copilot/validator/spatial.py`
- `src/robot_copilot/validator/resolve.py`
- `src/robot_copilot/geometry.py`

## Walkthrough

1. `segment_outside_fence` compares both endpoints and the segment against the inset polygon. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
```

Using Shapely `covers` matches the portfolio spec for concave fences. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. `segment_hits_keepout` returns the first keep-out name intersecting a move. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
```

Naming the hazard helps the mock decline path and the UI map highlight the same region. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. `rth_segment_blocked` mirrors the energy stage direct flight home check. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
```

Label this heuristic in reviews: it is demo-grade, not aviation certification. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
r = c.post('/api/chat', json={'message':'hover over beehives','vehicle':'drone','battery_pct':80})
print(r.json()['kind'], r.json().get('mission',{}).get('status'))
"
```

Expected:

```
decline None
```

## Exercise

Chat `fly to the substation` and record which spatial issue code appears in the validation report JSON. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/unit/test_spatial.py::test_substation_keepout`
