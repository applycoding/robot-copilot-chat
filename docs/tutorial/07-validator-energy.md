# 07 Energy validation

## Goal

Energy validation estimates watt-hours for mission legs plus conservative return-home legs using speeds and hover draws from vehicle profiles. Patrol loops multiply perimeter distance, so four laps at forty percent battery should fail with battery_insufficient before an operator confirms. Reserve watt-hours stay unavailable for outbound travel, mirroring real pack margins.

## Files

- `src/robot_copilot/validator/energy.py`
- `config/vehicles.toml`
- `tests/unit/test_energy.py`

## Walkthrough

1. rth_legs mirrors outbound geometry to estimate the path home, including altitude changes where applicable.

<!-- segment: src/robot_copilot/validator/energy.py rth_legs -->

```python
def rth_legs(
    pos: XYZ,
    state: str,
    veh: DroneProfile | RoverProfile,
    home: tuple[float, float],
) -> list[tuple[str, XYZ, XYZ, float, float, float]]:
    """Returns list of (kind, start, end, speed, distance, duration)."""
    if state in ("ground_home", "at_home"):
        return []
    legs: list[tuple[str, XYZ, XYZ, float, float, float]] = []
    x, y, alt = pos.x_m, pos.y_m, pos.alt_m
    hx, hy = home
    if isinstance(veh, DroneProfile):
        rth_alt = max(alt, veh.rth_altitude_m)
        if state == "ground_away" or alt < rth_alt:
            target = XYZ(x_m=x, y_m=y, alt_m=rth_alt)
            dz = abs(rth_alt - alt)
            dur = dz / veh.vertical_speed_mps if dz > 0 else 0.0
            legs.append(("climb", pos, target, veh.vertical_speed_mps, dz, dur))
            pos = target
            alt = rth_alt
        dist = math.hypot(hx - x, hy - y)
        end = XYZ(x_m=hx, y_m=hy, alt_m=alt)
        dur = dist / veh.cruise_speed_mps if dist > 0 else 0.0
        legs.append(("move", pos, end, veh.cruise_speed_mps, dist, dur))
        pos = end
        if alt > 0:
            target = XYZ(x_m=hx, y_m=hy, alt_m=0.0)
            dz = alt
            dur = dz / veh.vertical_speed_mps
            legs.append(("descend", pos, target, veh.vertical_speed_mps, dz, dur))
    else:
        dist = math.hypot(hx - x, hy - y)
        end = XYZ(x_m=hx, y_m=hy, alt_m=0.0)
        dur = dist / veh.cruise_speed_mps if dist > 0 else 0.0
        legs.append(("move", pos, end, veh.cruise_speed_mps, dist, dur))
    return legs
```

Leg tuples feed both energy summations and spatial return checks in separate modules.

2. rth_wh integrates power across return segments using profile cruise and hover watt draws.

<!-- segment: src/robot_copilot/validator/energy.py rth_wh -->

```python
def rth_wh(
    pos: XYZ, state: str, veh: DroneProfile | RoverProfile, home: tuple[float, float]
) -> float:
    if state in ("ground_home", "at_home"):
        return 0.0
    total = 0.0
    for kind, start, end, speed, dist, _dur in rth_legs(pos, state, veh, home):
        if kind == "move":
            total += move_wh(dist, speed, veh)
        elif kind == "climb" and isinstance(veh, DroneProfile):
            total += climb_wh(end.alt_m - start.alt_m, veh)
        elif kind == "descend" and isinstance(veh, DroneProfile):
            total += descend_wh(start.alt_m - end.alt_m, veh)
    return total
```

Adding return energy after mission legs prevents optimistic battery readings during long patrols.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
r = c.post('/api/chat', json={'message':'patrol the perimeter four times','vehicle':'drone','battery_pct':40}).json()
print(r['kind'], r['mission']['status'], r['mission']['issues'][0]['code'])
"
```

### Expected

```
plan invalid battery_insufficient
```

## Exercise

Open a valid North Fence inspect report and copy distance, duration, and energy fields.

## Checkpoint

- `tests/unit/test_regression_guards.py::test_battery_insufficient_includes_end_wh_param`
