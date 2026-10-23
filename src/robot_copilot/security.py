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
            receive = _limit_body(receive, self.max_body_bytes)

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

        try:
            await self.app(scope, receive, send_wrapper)
        except BodyTooLarge:
            await _json_error(send, 413, "payload_too_large", "Body too large.")


def _origin_ok(origin: str, allowed: tuple[str, ...]) -> bool:
    return any(origin == f"http://{h}" or origin.startswith(f"http://{h}:") for h in allowed)


def _limit_body(receive: Receive, max_bytes: int) -> Receive:
    seen = 0

    async def inner() -> Message:
        nonlocal seen
        message = await receive()
        if message["type"] == "http.request":
            body = message.get("body", b"")
            seen += len(body)
            if seen > max_bytes:
                raise BodyTooLarge()
        return message

    return inner


class BodyTooLarge(Exception):
    pass


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
