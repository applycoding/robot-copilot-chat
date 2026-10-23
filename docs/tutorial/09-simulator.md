# Telemetry simulator

## Goal

Work through **telemetry simulator** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: telemetry simulator.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


`simulate` requires a validated report whose hash matches the resolved plan. It integrates piecewise-linear motion per leg, emits frames at a configurable `dt_s`, doubles `dt` if frame caps are exceeded, and aborts if safety invariants break mid-flight.

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

Photos are recorded on photo legs; final state must show `landed` and `at_home` for successful drone missions.

## Exercise

Confirm every leg endpoint appears exactly once as a frame position for the North Fence plan (see simulator tests).

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_simulator.py -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
