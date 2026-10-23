from __future__ import annotations


def test_patrol_battery_repair_shortens_loops_and_notifies(client):
    r = client.post(
        "/api/chat",
        json={
            "message": "patrol the perimeter four times",
            "vehicle": "drone",
            "battery_pct": 40,
        },
    )
    assert r.status_code == 200
    mid = r.json()["mission"]["id"]
    assert r.json()["mission"]["status"] == "invalid"

    r1 = client.post(f"/api/missions/{mid}/repair", json={})
    assert r1.status_code == 200
    m1 = r1.json()["mission"]
    assert m1["status"] == "invalid"
    assert m1["plan"]["summary"] == "Patrol perimeter (2 of 4 loops)"
    assert "shortened" in r1.json()["assistant_message"].lower()
    assert m1.get("adjustment_notice")

    r2 = client.post(f"/api/missions/{mid}/repair", json={})
    assert r2.status_code == 200
    m2 = r2.json()["mission"]
    assert m2["status"] == "valid"
    assert m2["plan"]["summary"] == "Patrol perimeter (1 of 4 loops)"
    assert m2.get("adjustment_notice")


def test_substation_keepout_issue_reported_once(client):
    r = client.post(
        "/api/chat",
        json={"message": "fly over the substation", "vehicle": "drone", "battery_pct": 80},
    )
    codes = [i["code"] for i in r.json()["mission"]["issues"]]
    assert codes.count("enters_keep_out") == 1
    assert "rth_path_blocked" in codes
