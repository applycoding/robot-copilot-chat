# 12 Web UI and hardening

The browser UI is plain ES modules: `app.js` renders plan steps as list text (not JSON), `map.js` draws geofence and plan previews with a fitted SVG viewBox, and `playback.js` animates simulator frames. A mock banner states that default mode does not call external providers.

Oversized POST bodies are rejected in middleware before FastAPI parses JSON. When the cap is exceeded, the guard returns 413 immediately without draining the remainder of a chunked stream:

Chat messages scroll into view as they append. Plan steps render inside an ordered list without embedding numeric prefixes in text nodes, which keeps styling accessible and e2e checks meaningful. Map Y coordinates flip sign for SVG screen space while preserving geofence fidelity after `fitMapViewport`.

## Files

- `src/robot_copilot/security.py`
- `src/robot_copilot/static/app.js`
- `src/robot_copilot/static/map.js`
- `src/robot_copilot/static/playback.js`

```python
async def _read_post_body(receive: Receive, max_bytes: int) -> tuple[bytes | None, Receive]:
    """Read the full POST body (chunked or not). Returns (None, receive) when over max_bytes."""
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            return None, receive
        chunk = message.get("body", b"")
        total += len(chunk)
        if total > max_bytes:
            return None, receive
        chunks.append(chunk)
        if not message.get("more_body"):
            break

    body = b"".join(chunks)
    sent = False

    async def replay_receive() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return body, replay_receive
```

New chat plans call `resetPlayback()` so prior trails and "landed at home" telemetry do not linger.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how web-ui-and-hardening behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Execute a mission, scrub to End, then send a new chat and confirm playback status returns to idle with an empty exec path.

## Checkpoint

- `tests/api/test_chunked_body.py::test_chunked_body_without_content_length_returns_413`
