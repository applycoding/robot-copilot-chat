# Validator: energy and reserves

## Goal

Work through **validator: energy and reserves** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: validator: energy.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


Energy integration walks resolved legs, subtracting watt-hours per segment and simulating return-home reserve requirements. When projected end state drops below reserve, the validator emits `BATTERY_INSUFFICIENT` with explicit `end_wh` in the issue params so explanations can mention projected end energy, not just starting capacity.

## Exercise

Run a chat at 40% battery with `"patrol the perimeter four times"` and read the battery issue message. Compare `start_wh`, `end_wh`, and `reserve_wh` against `config/vehicles.toml`.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_energy.py tests/unit/test_regression_guards.py::test_battery_insufficient_includes_end_wh_param -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
