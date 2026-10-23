# Confirmation and execution

## Goal

Work through **confirmation and execution** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: confirmation.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


Confirmation compares the client-supplied plan hash with the stored hash, re-validates against current site and vehicle context, enforces TTL, and only then runs the simulator. Audit events record rejections (`confirm_rejected`) with reasons for tampering, expiry, or revalidation failure.

Runs are unique per mission; a second confirm returns `NOT_CONFIRMABLE`.

## Exercise

Walk through `orchestrator.confirm_and_execute` and list each guard in order.

## Checkpoint

```bash
uv run --no-sync pytest tests/api/test_confirm_guard.py -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
