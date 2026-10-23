from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env

_WORKER = """
import json
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env

db = sys.argv[1]
message = sys.argv[2]
env = default_settings_env(RCC_DB_URL=f"sqlite:///{db}")
settings = load_settings(env=env, dotenv_enabled=False)
app = create_app(settings)
client = TestClient(app, base_url="http://localhost")
r = client.post("/api/chat", json={"message": message})
payload = {"status": r.status_code, "mission_id": (r.json().get("mission") or {}).get("id")}
print(json.dumps(payload))
"""


def _chat_in_fresh_process(db: Path, message: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", _WORKER, str(db), message],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip())


def test_id_factory_resumes_after_restart(tmp_path: Path):
    db = tmp_path / "persist.db"
    first = _chat_in_fresh_process(db, "inspect the north fence")
    assert first["status"] == 200
    assert first["mission_id"]
    seq1 = int(first["mission_id"][2:])

    second = _chat_in_fresh_process(db, "take a photo of the barn")
    assert second["status"] == 200
    assert second["mission_id"]
    seq2 = int(second["mission_id"][2:])
    assert seq2 > seq1


def test_id_factory_same_process_still_monotonic(tmp_path: Path):
    """In-process create_app also bootstraps from DB (secondary guard)."""
    db = tmp_path / "persist2.db"
    env = default_settings_env(RCC_DB_URL=f"sqlite:///{db}")
    settings = load_settings(env=env, dotenv_enabled=False)
    app1 = create_app(settings)
    client1 = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(
        app1, base_url="http://localhost"
    )
    r1 = client1.post("/api/chat", json={"message": "inspect the north fence"})
    mid1 = r1.json()["mission"]["id"]
    app2 = create_app(settings)
    client2 = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(
        app2, base_url="http://localhost"
    )
    r2 = client2.post("/api/chat", json={"message": "take a photo of the barn"})
    mid2 = r2.json()["mission"]["id"]
    assert int(mid2[2:]) > int(mid1[2:])
