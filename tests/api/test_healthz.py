def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "mock"
    assert data["instance"]
