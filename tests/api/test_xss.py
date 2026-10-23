from __future__ import annotations


def test_template_autoescapes(client):
    r = client.get("/")
    assert r.status_code == 200
    text = r.text
    assert "onerror=" not in text


def test_chat_payload_roundtrip(client):
    payload = "<img src=x onerror=alert(1)>"
    r = client.post("/api/chat", json={"message": payload})
    assert r.status_code == 200
    body = r.json()
    assert payload in (body.get("assistant_message") or "") or body.get("kind") == "help"


def test_confirm_summary_from_validator(client):
    r = client.post("/api/chat", json={"message": "inspect the north fence"})
    data = r.json()
    assert data["mission"]["status"] == "valid"
    summary = data["mission"]["explanation"]
    assert "North Fence" in summary or "north fence" in summary.lower()
    assert data["mission"]["plan"]["summary"] != summary
