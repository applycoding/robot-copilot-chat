from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'none'"
)


class RequestGuardMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        allowed_hosts: tuple[str, ...],
        max_body_bytes: int,
    ) -> None:
        self.app = app
        self.allowed_hosts = allowed_hosts
        self.max_body_bytes = max_body_bytes

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


class BodyTooLarge(Exception):
    """Kept for unit tests that exercise legacy raise paths."""


async def _json_error(send: Send, status: int, code: str, msg: str) -> None:
    body = json.dumps({"detail": {"code": code, "message": msg}}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})
