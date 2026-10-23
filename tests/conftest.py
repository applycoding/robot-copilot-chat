from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from robot_copilot.llm.base import LLMProvider
from robot_copilot.llm.mock import MockProvider
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.fakes.providers import GatedProvider, SpyProvider

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _socket_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(self, address):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) else address
        if (
            isinstance(host, str)
            and host not in ("127.0.0.1", "localhost", "::1")
            and not str(host).startswith("/")
        ):
            raise AssertionError(f"Outbound network blocked: {host}")
        return real_connect(self, address)

    def guarded_connect_ex(self, address):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) else address
        if (
            isinstance(host, str)
            and host not in ("127.0.0.1", "localhost", "::1")
            and not str(host).startswith("/")
        ):
            return 1
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


_KEEP_RCC = frozenset(
    {
        "RCC_DOTENV",
        "RCC_ROOT",
        "RCC_DB_URL",
        "RCC_PROVIDER",
        "RCC_MODEL",
        "RCC_MAX_REPAIRS",
        "RCC_INSTANCE_NONCE",
        "RCC_SITE",
        "RCC_VEHICLES",
        "RCC_CONFIG",
    }
)


def scrub_env(env: dict[str, str]) -> dict[str, str]:
    out = dict(env)
    for key in list(out):
        if key.endswith("_API_KEY"):
            out.pop(key, None)
        if key.startswith("RCC_") and key not in _KEEP_RCC:
            out.pop(key, None)
        if re.match(r"^(ANTHROPIC|OPENAI|GEMINI|GOOGLE|XAI)_", key):
            out.pop(key, None)
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
            out.pop(key, None)
    out["RCC_DOTENV"] = "off"
    return out


@pytest.fixture(autouse=True)
def _env_scrub(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.endswith("_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        if key.startswith("RCC_") and key not in _KEEP_RCC:
            monkeypatch.delenv(key, raising=False)
        if re.match(r"^(ANTHROPIC|OPENAI|GEMINI|GOOGLE|XAI)_", key):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RCC_DOTENV", "off")


@pytest.fixture
def scrubbed_env() -> dict[str, str]:
    return scrub_env(dict(os.environ))


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)

    def set(self, dt: datetime) -> None:
        self._now = dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    def advance(self, seconds: float) -> None:
        from datetime import timedelta

        self._now = self._now + timedelta(seconds=seconds)

    def __call__(self) -> datetime:
        return self._now


class CounterIds:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"id{self.n:04d}"


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def counter_ids() -> CounterIds:
    return CounterIds()


@pytest.fixture
def ctx_drone() -> Any:
    from tests.helpers import load_ctx

    return load_ctx("drone", 100)


@pytest.fixture
def ctx(ctx_drone) -> Any:
    return ctx_drone


@pytest.fixture
def ctx_rover() -> Any:
    from tests.helpers import load_ctx

    return load_ctx("rover", 100)


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider("mock-1")


@pytest.fixture
def spy_provider(mock_provider: MockProvider) -> SpyProvider:
    return SpyProvider(mock_provider)


def make_client(
    tmp_path: Path,
    fake_clock: FakeClock,
    counter_ids: CounterIds,
    *,
    provider: LLMProvider | None = None,
    extra_env: dict[str, str] | None = None,
) -> TestClient:
    db = tmp_path / "test.db"
    env = scrub_env(
        {
            "RCC_DOTENV": "off",
            "RCC_ROOT": str(ROOT),
            "RCC_DB_URL": f"sqlite:///{db}",
            "RCC_PROVIDER": "mock",
            **(extra_env or {}),
        }
    )
    settings = load_settings(env=env, dotenv_enabled=False)
    app = create_app(
        settings,
        provider=provider or MockProvider(settings.model),
        clock=fake_clock,
        id_factory=counter_ids,
    )
    return TestClient(app, base_url="http://localhost")


@pytest.fixture
def client(tmp_path: Path, fake_clock: FakeClock, counter_ids: CounterIds) -> Iterator[TestClient]:
    with make_client(tmp_path, fake_clock, counter_ids) as c:
        yield c


@pytest.fixture
def app_factory(
    tmp_path: Path, fake_clock: FakeClock, counter_ids: CounterIds
) -> Callable[..., TestClient]:
    def _factory(**kwargs: Any) -> TestClient:
        return make_client(tmp_path, fake_clock, counter_ids, **kwargs)

    return _factory


@pytest.fixture
def gated_provider(mock_provider: MockProvider) -> GatedProvider:
    return GatedProvider(mock_provider)


@pytest.fixture
def subprocess_env() -> dict[str, str]:
    return scrub_env(dict(os.environ))


def run_validator_subprocess(plan_json: str, battery: int = 100) -> str:
    code = """
import json, sys
from tests.helpers import load_ctx, plan_from_json
from robot_copilot.validator import validate
ctx = load_ctx("drone", int(sys.argv[2]))
plan = plan_from_json(json.loads(sys.argv[1]))
print(validate(plan, ctx).model_dump_json())
"""
    env = scrub_env(dict(os.environ))
    proc = subprocess.run(
        [sys.executable, "-c", code, plan_json, str(battery)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()
