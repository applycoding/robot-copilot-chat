# Validator: structure and sequencing

## Goal

Work through **validator: structure and sequencing** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: validator: structure.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


Validation runs in stages: JSON schema, vehicle capabilities, action sequencing, spatial checks, and energy. Structure rules ensure drones take off before climbing, rovers never carry altitude, and unsupported action types are rejected per vehicle profile.

Rover takeoff attempts surface `UNSUPPORTED_ACTION_FOR_VEHICLE` alongside altitude-on-ground errors, which is what the farm-day rover step asserts. Sequencing also governs hover placement, photo actions without a prior goto, and the maximum action count enforced before spatial work begins. When reading failures, start with structure issues: they are cheap to compute and usually point to the first action index that must change before energy or keep-out messages become meaningful.

## Exercise

Open `validator/structure.py` and find where `return_home` must appear. Explain why a plan that ends mid-field fails.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_structure.py -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
