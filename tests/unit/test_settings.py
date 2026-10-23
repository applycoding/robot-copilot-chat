import pytest

from robot_copilot.settings import ProviderName, SettingsError, load_settings


def test_mock_default(scrubbed_env):
    s = load_settings(env={**scrubbed_env, "RCC_ROOT": "/workspace"}, dotenv_enabled=False)
    assert s.provider == ProviderName.MOCK
    assert s.model == "mock-1"


def test_missing_key(scrubbed_env):
    env = {**scrubbed_env, "RCC_ROOT": "/workspace", "RCC_PROVIDER": "anthropic"}
    with pytest.raises(SettingsError) as ei:
        load_settings(env=env, dotenv_enabled=False)
    assert "ANTHROPIC_API_KEY" in str(ei.value)


def test_repr_hides_key(scrubbed_env):
    s = load_settings(env={**scrubbed_env, "RCC_ROOT": "/workspace"}, dotenv_enabled=False)
    assert "api_key" in repr(s)
    assert "sk-" not in repr(s)
