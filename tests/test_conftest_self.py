from __future__ import annotations

import socket

import pytest

from tests.conftest import ROOT, run_validator_subprocess, scrub_env


def test_scrub_env_strips_secrets_and_proxy():
    env = scrub_env(
        {
            "ANTHROPIC_API_KEY": "secret",
            "OPENAI_API_KEY": "secret",
            "HTTP_PROXY": "http://proxy",
            "RCC_PROVIDER": "mock",
            "RCC_ROOT": str(ROOT),
            "RCC_EXTRA_SHOULD_GO": "x",
        }
    )
    assert env["RCC_DOTENV"] == "off"
    assert env["RCC_PROVIDER"] == "mock"
    assert env["RCC_ROOT"] == str(ROOT)
    assert "ANTHROPIC_API_KEY" not in env
    assert "HTTP_PROXY" not in env
    assert "RCC_EXTRA_SHOULD_GO" not in env


def test_scrub_env_keeps_whitelisted_rcc():
    env = scrub_env({"RCC_DB_URL": "sqlite:///x.db", "RCC_MAX_REPAIRS": "3"})
    assert env["RCC_DB_URL"] == "sqlite:///x.db"
    assert env["RCC_MAX_REPAIRS"] == "3"


def test_socket_guard_blocks_outbound(monkeypatch: pytest.MonkeyPatch):
    sock = socket.socket()
    with pytest.raises(AssertionError, match="Outbound network blocked"):
        sock.connect(("8.8.8.8", 53))
    sock.close()


def test_validator_subprocess_env_scrubbed():
    plan = (
        '{"vehicle":"drone","summary":"s","actions":'
        '[{"type":"takeoff","altitude_m":30},{"type":"return_home"}]}'
    )
    out = run_validator_subprocess(plan, battery=100)
    assert '"ok"' in out
