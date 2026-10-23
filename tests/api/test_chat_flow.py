def test_inspect_north_fence(client):
    r = client.post("/api/chat", json={"message": "inspect the north fence"})
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "plan"
    assert data["mission"]["status"] == "valid"
    assert len(data["mission"]["plan"]["actions"]) == 11
