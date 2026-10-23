# 09 Local simulator

## Goal

You are reading tutorial chapter 09 about frames and playback in robot-copilot-chat. Chapter 09 links frames and playback to validators, confirmation hashes, and local simulation gates. Learning note 09-1: simulate consumes ok ValidationReport objects and refuses tampered or unresolved inputs. Learning note 09-2: Frame generation uses ceil(duration/dt) semantics so motion does not undershoot leg endpoints. Learning note 09-3: _final_from_frames aggregates terminal pose, battery, and landed flags for playback summaries. Learning note 09-4: Photo events emit once per photo action even when multiple frames overlap the pose. Learning note 09-5: SafetyInvariantError paths mark runs aborted while retaining frames for debugging. Learning note 09-6: North Fence inspect plans produce hundreds of frames; pytest locks counts against dt choices. Learning note 09-7: Simulator revalidates keep-out and geofence along piecewise linear frame paths as a belt-and-suspenders check. Learning note 09-8: Runs stored in SQLite include frame arrays consumed by browser playback.js. Learning note 09-9: Executed status means simulation finished without invariant violations during frame checks. Learning note 09-10: plan_hash must match report hash before simulate proceeds, tying execution to confirmation. Learning note 09-11: Drone frames include altitude; rover frames pin altitude to zero throughout trajectories. Learning note 09-12: Final battery watt-hours should match resolved stats within tight floating tolerances. Learning note 09-13: Orchestrator confirm triggers simulation after successful hash validation and CAS commit. Learning note 09-14: Playback UI steps frames sequentially using timestamps derived from dt. Learning note 09-15: Tutorial operators can run simulate directly without HTTP when exploring north_fence_plan_json. Learning note 09-16: Aborted runs still return telemetry so instructors can show students what went wrong visually. Learning note 09-17: Simulation never calls providers; it only deterministically replays validated geometry. Learning note 09-18: Frame count tests guard against accidental changes to dt or speed defaults.

## Files

- `src/robot_copilot/sim/simulator.py`
- `src/robot_copilot/sim/telemetry.py`
- `tests/unit/test_simulator.py`

## Walkthrough

1. simulate builds frames, photos, and final state, returning SimResult with executed or aborted status.

<!-- segment: src/robot_copilot/sim/simulator.py simulate -->

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

    try:
        _check_frames(frames, ctx)
    except SafetyInvariantError as exc:
        fs = _final_from_frames(frames, ctx)
        return SimResult(
            status="aborted",
            frames=tuple(frames),
            photos=tuple(photos),
            final_state=fs,
            abort_reason=str(exc),
        )

    fs = _final_from_frames(frames, ctx)
    return SimResult(
        status="executed",
        frames=tuple(frames),
        photos=tuple(photos),
        final_state=fs,
    )
```

NotValidatedError raises when reports are not ok or hashes diverge, protecting teaching invariants.

2. _final_from_frames inspects the last frame, combining landed detection with battery bookkeeping fields.

<!-- segment: src/robot_copilot/sim/simulator.py _final_from_frames -->

```python
def _final_from_frames(frames: list[Frame], ctx: ValidationContext) -> FinalState:
    if not frames:
        hx, hy = ctx.site.home
        return FinalState(x_m=hx, y_m=hy, alt_m=0.0, battery_wh=0.0, landed=True, at_home=True)
    last = frames[-1]
    hx, hy = ctx.site.home
    at_home = math.hypot(last.x_m - hx, last.y_m - hy) <= 2.0
    landed = last.alt_m <= 0.01
    return FinalState(
        x_m=last.x_m,
        y_m=last.y_m,
        alt_m=last.alt_m,
        battery_wh=last.battery_wh,
        landed=landed,
        at_home=at_home,
    )
```

Playback markers rely on this summary to show operators where missions ended geographically.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from robot_copilot.sim.simulator import simulate
from robot_copilot.validator import validate
from tests.helpers import load_ctx, north_fence_plan_json, plan_from_json
ctx = load_ctx()
rep = validate(plan_from_json(north_fence_plan_json()), ctx)
sim = simulate(rep, ctx)
print(len(sim.frames), sim.status == 'executed')
"
```

### Expected

```
364 True
```

## Exercise

Compare final_frame coordinates with final_state in run JSON after confirm in the UI.

## Checkpoint

- `tests/unit/test_simulator.py::test_frame_count_and_endpoints`
