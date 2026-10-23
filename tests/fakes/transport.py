from __future__ import annotations

from collections.abc import Callable

import httpx2


def recording_transport(
    routes: dict[tuple[str, str], Callable[[httpx2.Request], httpx2.Response]],
) -> httpx2.MockTransport:
    recorded: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        recorded.append(request)
        key = (request.method.upper(), request.url.path)
        for (method, path), fn in routes.items():
            if method == key[0] and request.url.path.endswith(path):
                return fn(request)
        raise AssertionError(f"Unmatched request: {request.method} {request.url}")

    transport = httpx2.MockTransport(handler)
    transport.recorded = recorded  # type: ignore[attr-defined]
    return transport
