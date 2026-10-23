from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.conftest import scrub_env

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def e2e_server():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    nonce = "e2e-test-nonce"
    db = ROOT / "test-results" / "e2e.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    env = scrub_env(
        {
            **dict(os.environ),
            "RCC_PROVIDER": "mock",
            "RCC_DOTENV": "off",
            "RCC_ROOT": str(ROOT),
            "RCC_DB_URL": f"sqlite:///{db}",
            "RCC_INSTANCE_NONCE": nonce,
        }
    )
    log_path = ROOT / "test-results" / "server.log"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "robot_copilot.main:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    import urllib.request

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/healthz", timeout=1) as resp:
                data = resp.read().decode()
                if nonce in data:
                    break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("server failed to start")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    out = proc.stdout.read() if proc.stdout else ""
    log_path.write_text(out)


@pytest.fixture(scope="session")
def base_url(e2e_server):
    return e2e_server
