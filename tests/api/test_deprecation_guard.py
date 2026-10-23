from __future__ import annotations

import warnings

import pytest
from fastapi.testclient import TestClient

from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env


@pytest.fixture
def bare_client() -> TestClient:
    settings = load_settings(env=default_settings_env(), dotenv_enabled=False)
    return TestClient(create_app(settings), base_url="http://localhost")


def test_httpx_data_body_emits_deprecation_warning(bare_client: TestClient) -> None:
    with pytest.raises(DeprecationWarning, match="content="):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            bare_client.post(
                "/api/chat",
                data="x",
                headers={"Content-Type": "text/plain"},
            )
