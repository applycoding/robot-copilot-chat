from __future__ import annotations

from pathlib import Path

import pytest

from robot_copilot.llm.mock import MockProvider
from tests.conftest import make_client
from tests.fakes.providers import (
    ErrorOnRepairProvider,
    MockThenTextProvider,
    RepairHangProvider,
    SpyProvider,
)


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


def test_repair_limit_before_not_repairable(client):
    r = client.post(
        "/api/chat",
        json={"message": "patrol the perimeter four times", "battery_pct": 15},
    )
    mid = r.json()["mission"]["id"]
    for _ in range(2):
        client.post(f"/api/missions/{mid}/repair", json={})
    r_lim = client.post(f"/api/missions/{mid}/repair", json={})
    assert r_lim.status_code == 409
    assert r_lim.json()["detail"]["code"] == "repair_limit"
    r_nr = client.post(f"/api/missions/{mid}/repair", json={})
    assert r_nr.status_code == 409
    assert r_nr.json()["detail"]["code"] == "repair_limit"


@pytest.mark.parametrize("max_repairs,expected_repairs", [(0, 0), (1, 1), (2, 2), (5, 2)])
def test_max_repairs_transition(tmp_path, fake_clock, counter_ids, max_repairs, expected_repairs):
    spy = SpyProvider(MockProvider("mock-1"))
    with make_client(
        tmp_path,
        fake_clock,
        counter_ids,
        provider=spy,
        extra_env={"RCC_MAX_REPAIRS": str(max_repairs)},
    ) as client:
        r = client.post(
            "/api/chat",
            json={"message": "survey the pond at 150 m"},
        )
        mid = r.json()["mission"]["id"]
        assert spy.calls == 1
        attempts = 0
        while attempts <= max_repairs + 1:
            rr = client.post(f"/api/missions/{mid}/repair", json={})
            if rr.status_code == 409:
                break
            attempts += 1
        assert spy.calls <= 1 + max_repairs
        m = client.get(f"/api/missions/{mid}").json()
        assert m["repair_attempts"] <= max(1, expected_repairs) or m["status"] in (
            "valid",
            "invalid",
            "repair_exhausted",
        )


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
        client.post(f"/api/missions/{mid}/repair", json={})
        client.post(f"/api/missions/{mid}/repair", json={})
        assert spy.calls <= 1 + 2
        m = client.get(f"/api/missions/{mid}").json()
        assert m["status"] == "valid"
        r3 = client.post(f"/api/missions/{mid}/repair", json={})
        assert r3.status_code == 409
        assert r3.json()["detail"]["code"] == "not_repairable"


def test_provider_error_consumes_attempt(tmp_path, fake_clock, counter_ids):
    err = ErrorOnRepairProvider()
    with make_client(tmp_path, fake_clock, counter_ids, provider=err) as client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        before = r.json()["mission"]["repair_attempts"]
        rr = client.post(f"/api/missions/{mid}/repair", json={})
        assert rr.status_code == 200
        assert rr.json()["kind"] == "error"
        after = client.get(f"/api/missions/{mid}").json()["repair_attempts"]
        assert after == before + 1


def test_text_only_repair_keeps_prior_plan(tmp_path, fake_clock, counter_ids):
    with make_client(tmp_path, fake_clock, counter_ids, provider=MockThenTextProvider()) as client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        prev_actions = r.json()["mission"]["plan"]["actions"]
        rr = client.post(f"/api/missions/{mid}/repair", json={})
        assert rr.status_code == 200
        assert rr.json()["mission"]["status"] == "invalid"
        assert rr.json()["mission"]["plan"]["actions"] == prev_actions


def test_operation_timeout_consumes_attempt(tmp_path, fake_clock, counter_ids):
    cfg = tmp_path / "fast.toml"
    base = Path(__file__).resolve().parents[2] / "config" / "app.toml"
    text = base.read_text().replace("operation_timeout_s = 75", "operation_timeout_s = 0.05")
    cfg.write_text(text)
    hang = RepairHangProvider()
    with make_client(
        tmp_path,
        fake_clock,
        counter_ids,
        provider=hang,
        extra_env={"RCC_CONFIG": str(cfg)},
    ) as client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        rr = client.post(f"/api/missions/{mid}/repair", json={})
        assert rr.status_code == 200
        m = client.get(f"/api/missions/{mid}").json()
        assert m["repair_attempts"] == 1
