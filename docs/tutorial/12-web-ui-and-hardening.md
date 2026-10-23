# 12 Web UI and request hardening

## Goal

You will connect the Jinja shell, static JavaScript map, and API JSON to the safety middleware that runs before routes. Host and Origin checks, JSON-only POST bodies, and byte limits block casual abuse on loopback deployments. Content-Security-Policy headers complement template autoescape rules tested against XSS payloads.

Templates use autoescape and pass JSON via `tojson` filters in the few places scripts need structured data. Static JavaScript never uses `innerHTML` with untrusted strings; hygiene tests grep for dangerous patterns. Request guards run outside routing so even malformed clients never reach provider semaphores or SQLite writes. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter.

## Files

- `src/robot_copilot/security.py`
- `src/robot_copilot/main.py`
- `src/robot_copilot/templates/index.html`

## Walkthrough

1. `RequestGuardMiddleware` enforces host allowlists and POST content rules. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

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


def _origin_ok(origin: str, allowed: tuple[str, ...]) -> bool:
    return any(origin == f"http://{h}" or origin.startswith(f"http://{h}:") for h in allowed)


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

Rejecting non-JSON POSTs early avoids surprising 422 bodies from Starlette parsers. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. CSP constants are appended on every HTTP response start. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'none'"
)
```

Disallowing inline script means all behavior lives in `/static` files audited by hygiene tests. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. `create_app` mounts static assets and serves `index.html` without inline script. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"version": __version__},
        )
```

Passing only `version` into the template keeps the attack surface small. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -c "
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

Expected:

```
400 bad_host
```

## Exercise

Open devtools on `/` and verify every script tag points at `/static` rather than inline handlers. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/api/test_chunked_body.py::test_chunked_body_without_content_length_returns_413`
