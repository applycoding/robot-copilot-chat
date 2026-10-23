# Repair loop and provider errors

## Goal

Work through **repair loop and provider errors** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: repair loop.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


Invalid missions can enter `repairing` status with a bounded number of attempts. Repairs bump revision, call the provider with structured issues, and append audit kinds such as `repair_requested`, `validated`, `declined`, or `repair_failed`. Provider transport errors roll back through `commit_repair_failure` so missions never stick in `repairing`.

Declined repairs now emit a `declined` audit event matching chat declines.

## Exercise

Replay farm-day steps 5-7 in the UI: invalid pond altitude, repair, second repair blocked.

## Checkpoint

```bash
uv run --no-sync pytest tests/api/test_repair_flow.py tests/api/test_repair_provider_error.py -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
