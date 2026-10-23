# 06 Validator spatial rules

After structure passes, the resolver builds legs between waypoints. Spatial validation tests each leg against the shrunken geofence and expanded keep-outs using Shapely primitives in `geometry.py`. Hits name the keep-out zone and the action index so repairs can target a specific step.

Segment tests use full floating-point coordinates; quantization happens only when serializing golden scenario output. A path that clips a corner of the geofence or crosses the Substation keep-out fails even if the mock provider drew a straight line.

Keep-out hits use expanded polygons from `SiteGeometry`, not raw TOML coordinates shown to operators. Return-home checks cast a segment from the current XY to home at cruise altitude for drones. Property tests generate random plans and assert oracle agreement on fence and keep-out invariants across thousands of mutations.

## Files

- `src/robot_copilot/validator/resolve.py`
- `src/robot_copilot/validator/spatial.py`
- `src/robot_copilot/geometry.py`

```python
def segment_outside_fence(geometry: SiteGeometry, start: XYZ, end: XYZ) -> bool:
    if start.x_m == end.x_m and start.y_m == end.y_m and start.alt_m == end.alt_m:
        pt = Point(start.x_m, start.y_m)
        return not geometry.fence_inset.covers(pt)
    line = LineString([(start.x_m, start.y_m), (end.x_m, end.y_m)])
    return not geometry.fence_inset.covers(line)
```

`RTH_PATH_BLOCKED` and `ENTERS_KEEP_OUT` can appear together when a mission ends inside a zone whose direct return-home chord crosses a keep-out.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how validator-spatial behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Mutate a valid North Fence plan so one `goto` targets coordinates inside the Substation polygon and confirm both keep-out and return-home issues appear.

## Checkpoint

- `tests/unit/test_spatial.py`
