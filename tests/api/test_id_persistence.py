from __future__ import annotations

from pathlib import Path

from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env


def test_id_factory_resumes_after_restart(tmp_path: Path):
    db = tmp_path / "persist.db"
    env = default_settings_env(RCC_DB_URL=f"sqlite:///{db}")
    settings = load_settings(env=env, dotenv_enabled=False)

    app1 = create_app(settings)
    client1 = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(
        app1, base_url="http://localhost"
    )
    r1 = client1.post("/api/chat", json={"message": "hello"})
    assert r1.status_code == 200

    app2 = create_app(settings)
    client2 = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(
        app2, base_url="http://localhost"
    )
    r2 = client2.post("/api/chat", json={"message": "inspect the north fence"})
    assert r2.status_code == 200
