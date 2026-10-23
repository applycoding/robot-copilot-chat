# Web UI and hardening

## Goal

Work through **web ui and hardening** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: web ui.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


The UI is vanilla ES modules: `app.js` renders plans as list items (not JSON), `map.js` draws site layers and fits the SVG viewBox to geofence plus plan preview, and `playback.js` animates frames. A visible mock banner reminds operators that default mode uses the local provider only.

Request guarding buffers POST bodies in middleware so oversized chunked uploads return HTTP 413 before FastAPI parses JSON:

```python
                return
            cl = headers.get("content-length")
            if cl and int(cl) > self.max_body_bytes:
                await _json_error(send, 413, "payload_too_large", "Body too large.")
                return

            body, receive_for_app = await _read_post_body(receive, self.max_body_bytes)
            if body is None:
                await _json_error(send, 413, "payload_too_large", "Body too large.")
```

## Exercise

Open the map after `"inspect the north fence"` and verify the North Fence polyline and geofence are both visible without clipping.

## Checkpoint

```bash
uv run --no-sync pytest -m e2e tests/e2e/test_smoke.py --browser chromium -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
