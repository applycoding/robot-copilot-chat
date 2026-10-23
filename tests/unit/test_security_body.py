from __future__ import annotations

import json

import pytest

from robot_copilot.security import RequestGuardMiddleware


@pytest.mark.asyncio
async def test_chunked_body_returns_413():
    big = b"x" * (16 * 1024 + 1)
    parts = [big[:8192], big[8192:16384], big[16384:]]
    state = {"i": 0}

    async def receive():
        i = state["i"]
        if i >= len(parts):
            return {"type": "http.request", "body": b"", "more_body": False}
        chunk = parts[i]
        state["i"] = i + 1
        return {"type": "http.request", "body": chunk, "more_body": i < len(parts) - 1}

    async def app(scope, receive, send):
        while True:
            msg = await receive()
            if msg["type"] == "http.request" and not msg.get("more_body", False):
                break

    guard = RequestGuardMiddleware(app, allowed_hosts=("localhost",), max_body_bytes=16384)
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"host", b"localhost"), (b"content-type", b"application/json")],
    }
    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    await guard(scope, receive, send)
    assert sent[0]["status"] == 413
    body = sent[1]["body"]
    detail = json.loads(body.decode())
    assert detail["detail"]["code"] == "payload_too_large"
