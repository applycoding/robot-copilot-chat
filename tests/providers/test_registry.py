from pydantic import SecretStr

from robot_copilot.llm.anthropic_provider import AnthropicProvider
from robot_copilot.llm.gemini_provider import GeminiProvider
from robot_copilot.llm.mock import MockProvider
from robot_copilot.llm.openai_provider import OpenAIProvider
from robot_copilot.llm.registry import build_provider
from robot_copilot.llm.xai_provider import XAIProvider
from robot_copilot.settings import ProviderName, load_settings
from tests.helpers import default_settings_env


def test_build_provider_mock():
    s = load_settings(env=default_settings_env(), dotenv_enabled=False)
    p = build_provider(s)
    assert isinstance(p, MockProvider)
    assert p.model == "mock-1"


def test_build_provider_classes():
    base = load_settings(env=default_settings_env(), dotenv_enabled=False)
    for name, cls in [
        (ProviderName.ANTHROPIC, AnthropicProvider),
        (ProviderName.OPENAI, OpenAIProvider),
        (ProviderName.GEMINI, GeminiProvider),
        (ProviderName.XAI, XAIProvider),
    ]:
        s = base.model_copy(update={"provider": name, "api_key": SecretStr("k"), "model": "m"})
        assert isinstance(build_provider(s), cls)
