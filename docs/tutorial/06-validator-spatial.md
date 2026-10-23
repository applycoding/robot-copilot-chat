# 06 Spatial validation

## Goal

Spatial checks expand named places into segments, then test geofence margins and keep-out volumes along each leg and along return-home shortcuts. The substation flyover chat phrase exists to produce enters_keep_out together with rth_path_blocked in one invalid mission. Understanding segment helpers clarifies why map previews can look fine while validation still fails.

## Files

- `src/robot_copilot/validator/spatial.py`
- `src/robot_copilot/geometry.py`
- `tests/unit/test_spatial.py`

## Walkthrough

1. segment_hits_keepout wraps shapely intersections, returning true when a movement segment intersects buffered keep-out polygons.

<!-- segment: src/robot_copilot/validator/spatial.py segment_hits_keepout -->

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
```

Validators call this helper for each leg after places resolve to concrete coordinates.

2. rth_segment_blocked models return-home straight lines, catching plans that would exit through forbidden airspace during RTH.

<!-- segment: src/robot_copilot/validator/spatial.py rth_segment_blocked -->

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

Energy and spatial modules both reason about return paths, but only spatial emits rth_path_blocked issues.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
r = c.post('/api/chat', json={'message':'fly over the substation','vehicle':'drone','battery_pct':80}).json()
codes = [i['code'] for i in r['mission']['issues']]
print(r['mission']['status'], codes[0], codes[1])
"
```

### Expected

```
invalid enters_keep_out rth_path_blocked
```

## Exercise

Record spatial issue codes from a fly to substation chat and compare with flyover phrasing.

## Checkpoint

- `tests/unit/test_spatial.py::test_substation_keepout`
