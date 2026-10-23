# 06 Spatial validation

## Goal

You are reading tutorial chapter 06 about geofence and keep-out checks in robot-copilot-chat. Chapter 06 links geofence and keep-out checks to validators, confirmation hashes, and local simulation gates. Learning note 06-1: Spatial validation expands places into coordinates, then tests each leg against fences and keep-outs. Learning note 06-2: segment_hits_keepout samples segment geometry with margins inherited from site configuration. Learning note 06-3: rth_segment_blocked verifies return-home paths do not pierce forbidden volumes after mission legs. Learning note 06-4: Altitude ceilings compare action altitudes against drone profile limits with clear issue params. Learning note 06-5: Geofence violations use polygon inclusion tests with margin buffers similar to keep-out handling. Learning note 06-6: Unknown places fail before spatial math when resolution cannot map a label to coordinates. Learning note 06-7: Fly over substation mock plans intentionally enter keep-outs to produce teaching-friendly invalid missions. Learning note 06-8: Spatial codes include enters_keep_out and rth_path_blocked often appearing together for flyover prompts. Learning note 06-9: Path places generate multiple legs; each segment is tested independently for cumulative violations. Learning note 06-10: Rover plans use zero altitude throughout spatial checks, reflecting ground navigation assumptions. Learning note 06-11: Spatial results feed path_preview polylines displayed in the browser map for valid missions. Learning note 06-12: Issue messages include distances and thresholds formatted later by explain_issue templates. Learning note 06-13: Spatial validation never mutates plans; resolved plans come from earlier resolution passes. Learning note 06-14: Keep-out names normalize identically to place names, keeping mock and validator behavior aligned. Learning note 06-15: Tutorial chat phrase fly over the substation should yield invalid status with spatial codes listed. Learning note 06-16: Regression tests lock substation scenarios so README warnings stay truthful after edits. Learning note 06-17: Spatial failures block confirmation because hashes would otherwise authorize unsafe motion. Learning note 06-18: Understanding segment tests helps you interpret map overlays versus actual forbidden regions.

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
