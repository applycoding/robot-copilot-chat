from __future__ import annotations


def test_no_valid_plan(client):
    r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
    mid = r.json()["mission"]["id"]
    r2 = client.get(f"/api/missions/{mid}/commands")
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "no_valid_plan"


def test_valid_commands_match_legs(client):
    r = client.post("/api/chat", json={"message": "inspect the north fence"})
    mid = r.json()["mission"]["id"]
    cmds = client.get(f"/api/missions/{mid}/commands").json()
    assert isinstance(cmds, list)
    assert len(cmds) > 0
