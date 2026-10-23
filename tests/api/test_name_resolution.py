from __future__ import annotations


def test_barn_aliases_resolve_in_mock_plans(client):
    for message in (
        "take a photo of BARN",
        "take a photo of barn.",
        "fly to BARN.",
    ):
        r = client.post("/api/chat", json={"message": message})
        assert r.status_code == 200
        mission = r.json().get("mission")
        assert mission and mission.get("plan")
        places = [
            a.get("place")
            for a in mission["plan"]["actions"]
            if a.get("type") == "goto" and a.get("place")
        ]
        assert places
        assert all(p == "Barn" for p in places)
