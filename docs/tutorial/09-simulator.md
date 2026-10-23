# 09 Telemetry simulator

`simulate` accepts only validated reports whose hash matches the resolved plan. It integrates motion per leg at timestep `dt_s`, doubles `dt` if frame count would exceed `max_frames`, and aborts with `SafetyInvariantError` if geofence or keep-out constraints are violated mid-flight.

Frames include position, altitude, battery, and optional events (`photo`, `land`, etc.). Photos are collected on photo legs; final state must show `landed` and `at_home` for successful drone missions.

Rover simulations force zero altitude on every frame. Photo events capture label, place, and timestamp for executed runs. Aborted simulations still return partial frames with `abort_reason` when invariants break mid-flight, though confirmed missions in the demo stack should always execute cleanly when validation passed.

## Files

- `src/robot_copilot/sim/simulator.py`
- `src/robot_copilot/sim/telemetry.py`
- `tests/unit/test_simulator.py`

```python
def simulate(
    report: ValidationReport,
    ctx: ValidationContext,
    *,
    dt_s: float = 0.5,
    max_frames: int = 4000,
) -> SimResult:
    if not report.ok or report.resolved is None or report.plan_hash is None:
        raise NotValidatedError("report not validated")
    resolved = report.resolved
    if report.plan_hash != plan_hash(resolved.plan, ctx):
        raise NotValidatedError("plan hash mismatch")

    dt = dt_s
    while True:
        frames, photos = _build_frames(resolved.legs, dt, ctx)
        if len(frames) <= max_frames:
            break
        dt *= 2
```

Simulator tests assert exact per-leg frame counts and that each leg endpoint appears in the stream.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how simulator behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Run the North Fence simulation and note how many photo events are emitted versus photos claimed in plan stats.

## Checkpoint

- `tests/unit/test_simulator.py::test_frame_count_and_endpoints`
