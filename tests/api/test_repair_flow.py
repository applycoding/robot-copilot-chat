from __future__ import annotations

from robot_copilot.llm.mock import MockProvider
from tests.conftest import make_client
from tests.fakes.providers import SpyProvider


def test_repair_limit_order(client):
    r = client.post(
        "/api/chat",
        json={"message": "patrol the perimeter four times", "battery_pct": 15},
    )
    mid = r.json()["mission"]["id"]
    client.post(f"/api/missions/{mid}/repair", json={})
    client.post(f"/api/missions/{mid}/repair", json={})
    r3 = client.post(f"/api/missions/{mid}/repair", json={})
    assert r3.status_code == 409
    assert r3.json()["detail"]["code"] == "repair_limit"


def test_max_logical_calls(tmp_path, fake_clock, counter_ids):
    spy = SpyProvider(MockProvider("mock-1"))
    with make_client(
        tmp_path,
        fake_clock,
        counter_ids,
        provider=spy,
        extra_env={"RCC_MAX_REPAIRS": "2"},
    ) as client:
        r = client.post(
            "/api/chat",
            json={"message": "survey the pond at 150 m"},
        )
        mid = r.json()["mission"]["id"]
        assert spy.calls == 1
        client.post(f"/api/missions/{mid}/repair")
        client.post(f"/api/missions/{mid}/repair")
        assert spy.calls <= 1 + 2
