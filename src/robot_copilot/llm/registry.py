from __future__ import annotations

from robot_copilot.llm.base import LLMProvider
from robot_copilot.llm.mock import MockProvider
from robot_copilot.settings import AppSettings, ProviderName


def build_provider(settings: AppSettings) -> LLMProvider:
    if settings.provider == ProviderName.MOCK:
        return MockProvider(settings.model)
    if settings.provider == ProviderName.ANTHROPIC:
        from robot_copilot.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            settings.model,
            settings.api_key,  # type: ignore[arg-type]
            timeout_s=settings.request_timeout_s,
            max_retries=settings.sdk_max_retries,
            max_output_tokens=settings.max_output_tokens,
        )
    if settings.provider == ProviderName.OPENAI:
        from robot_copilot.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(
            settings.model,
            settings.api_key,  # type: ignore[arg-type]
            timeout_s=settings.request_timeout_s,
            max_retries=settings.sdk_max_retries,
            max_output_tokens=settings.max_output_tokens,
        )
    if settings.provider == ProviderName.XAI:
        from robot_copilot.llm.xai_provider import XAIProvider

        return XAIProvider(
            settings.model,
            settings.api_key,  # type: ignore[arg-type]
            base_url=settings.xai_base_url,
            timeout_s=settings.request_timeout_s,
            max_retries=settings.sdk_max_retries,
            max_output_tokens=settings.max_output_tokens,
        )
    if settings.provider == ProviderName.GEMINI:
        from robot_copilot.llm.gemini_provider import GeminiProvider

        return GeminiProvider(
            settings.model,
            settings.api_key,  # type: ignore[arg-type]
            timeout_s=settings.request_timeout_s,
            max_retries=settings.sdk_max_retries,
            max_output_tokens=settings.max_output_tokens,
        )
    raise ValueError(f"unknown provider {settings.provider}")
