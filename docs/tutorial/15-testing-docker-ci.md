# Testing, Docker, and CI

## Goal

Work through **testing, docker, and ci** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: testing, docker,.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


The test pyramid spans pure validator units, API integration with guarded HTTP, property fuzzing against `oracle.py`, a 32-step farm-day scenario with golden audit hashes, provider contract tests, and Playwright e2e. `conftest.py` installs a socket guard and fail-closed httpx transport so accidental outbound calls fail tests immediately.

CI runs ruff, mypy on `src`, pytest (excluding e2e by default), Playwright, and a Docker smoke build. Golden files are updated only with `UPDATE_GOLDEN=1` locally.

## Exercise

Run `uv run --no-sync pytest tests/scenario/test_farm_day.py -q` and inspect how many executed runs the golden file records.

## Checkpoint

```bash
uv run --no-sync pytest tests/scenario/test_farm_day.py::test_farm_day_scenario -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
