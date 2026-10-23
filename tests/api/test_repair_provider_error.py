from __future__ import annotations

from tests.conftest import make_client
from tests.fakes.providers import ErrorOnRepairProvider


def test_repair_provider_error_unsticks_mission(tmp_path, fake_clock, counter_ids):
    provider = ErrorOnRepairProvider()
    with make_client(tmp_path, fake_clock, counter_ids, provider=provider) as client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        client.post(f"/api/missions/{mid}/repair", json={})
        m = client.get(f"/api/missions/{mid}").json()
        assert m["status"] == "invalid"
        r2 = client.post(f"/api/missions/{mid}/repair", json={})
        assert r2.status_code in (200, 409)
