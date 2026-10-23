from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env


@pytest.mark.asyncio
async def test_chunked_body_without_content_length_returns_413(tmp_path: Path):
    db = tmp_path / "chunk.db"
    env = default_settings_env(RCC_DB_URL=f"sqlite:///{db}")
    settings = load_settings(env=env, dotenv_enabled=False)
    app = create_app(settings)

    big = b"x" * (16 * 1024 + 1)

    async def body_chunks():
        yield big[:8192]
        yield big[8192:16384]
        yield big[16384:]

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.post(
            "/api/chat",
            content=body_chunks(),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "payload_too_large"
