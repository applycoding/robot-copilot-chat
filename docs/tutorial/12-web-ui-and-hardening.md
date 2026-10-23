# 12 Web UI and hardening

## Goal

The browser client is plain modules served from FastAPI, while RequestGuardMiddleware rejects bad hosts, bad origins, oversize bodies, and unexpected content types before route code runs. Chunked uploads return 413 without draining the socket, which matters for slowloris-style abuse in classroom deployments. Chat JavaScript clears map overlays when responses are help text or lack a mission so stale paths never linger.

## Files

- `src/robot_copilot/security.py`
- `src/robot_copilot/static/app.js`
- `tests/api/test_request_guard.py`

## Walkthrough

1. _read_post_body accumulates POST payloads with strict byte caps, aborting reads once limits exceed settings.

<!-- segment: src/robot_copilot/security.py _read_post_body -->

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

This function runs inside middleware before FastAPI instantiates request.form or json parsers.

2. RequestGuardMiddleware.__call__ inspects scope type, host headers, methods, and content lengths for every request.

<!-- segment: src/robot_copilot/security.py RequestGuardMiddleware.__call__ -->

```python
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        host = headers.get("host", "").split(":")[0]
        if host not in self.allowed_hosts:
            await _json_error(send, 400, "bad_host", "Host not allowed.")
            return

        method = scope.get("method", "GET")
        receive_for_app = receive
        if method == "POST":
            origin = headers.get("origin")
            if origin is not None and not _origin_ok(origin, self.allowed_hosts):
                await _json_error(send, 403, "bad_origin", "Origin not allowed.")
                return
            ct = headers.get("content-type", "").split(";")[0].strip().lower()
            if ct != "application/json":
                await _json_error(send, 415, "unsupported_media", "JSON required.")
                return
            cl = headers.get("content-length")
            if cl and int(cl) > self.max_body_bytes:
                await _json_error(send, 413, "payload_too_large", "Body too large.")
                return

            body, receive_for_app = await _read_post_body(receive, self.max_body_bytes)
            if body is None:
                await _json_error(send, 413, "payload_too_large", "Body too large.")
                return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                hdrs.extend(
                    [
                        (b"content-security-policy", CSP.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                    ]
                )
                message = {**message, "headers": hdrs}
            await send(message)

        if method == "POST":
            assert receive_for_app is not None
            await self.app(scope, receive_for_app, send_wrapper)
        else:
            await self.app(scope, receive, send_wrapper)
```

Rejected requests never acquire database connections, preserving SQLite under abusive traffic.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://evil')
r = c.post('/api/chat', json={'message':'hi','vehicle':'drone','battery_pct':80})
print(r.status_code, r.json()['detail']['code'])
"
```

### Expected

```
400 bad_host
```

## Exercise

Verify script tags on / load modules from /static without inline onclick handlers.

## Checkpoint

- `tests/api/test_chunked_body.py::test_chunked_body_without_content_length_returns_413`
