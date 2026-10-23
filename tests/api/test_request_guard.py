from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from robot_copilot.llm.mock import MockProvider
from tests.conftest import make_client
from tests.fakes.providers import SpyProvider


@pytest.fixture
def guarded_client(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    spy = SpyProvider(inner)
    with make_client(tmp_path, fake_clock, counter_ids, provider=spy) as c:
        c.spy = spy  # type: ignore[attr-defined]
        yield c


def test_bad_host(guarded_client: TestClient):
    r = guarded_client.get("/healthz", headers={"Host": "evil.example"})
    assert r.status_code == 400
    assert guarded_client.spy.calls == 0  # type: ignore[attr-defined]


def test_bad_origin(guarded_client: TestClient):
    r = guarded_client.post(
        "/api/chat",
        json={"message": "hi"},
        headers={"Origin": "http://evil.example", "Content-Type": "application/json"},
    )
    assert r.status_code == 403
    assert guarded_client.spy.calls == 0  # type: ignore[attr-defined]


def test_non_json_content_type(guarded_client: TestClient):
    r = guarded_client.post(
        "/api/chat",
        data="x",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 415
    assert guarded_client.spy.calls == 0  # type: ignore[attr-defined]


def test_body_too_large(guarded_client: TestClient):
    big = "x" * (16 * 1024 + 1)
    r = guarded_client.post(
        "/api/chat",
        content=big,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code in (413, 422)
    assert guarded_client.spy.calls == 0  # type: ignore[attr-defined]


def test_unknown_field(guarded_client: TestClient):
    r = guarded_client.post("/api/chat", json={"message": "hi", "evil": True})
    assert r.status_code == 422
    assert guarded_client.spy.calls == 0  # type: ignore[attr-defined]


def test_security_headers_on_index(guarded_client: TestClient):
    r = guarded_client.get("/")
    assert "default-src 'self'" in r.headers.get("content-security-policy", "")
