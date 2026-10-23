# 14 Gemini and xAI adapters

Gemini uses the Google GenAI client with injectable HTTP options in tests. xAI follows the OpenAI-compatible chat completions surface with a distinct model id from settings. Both adapters map tool calls into the same normalized `ProviderResult` structure as Anthropic and OpenAI.

Registry selection keeps construction in one place so `create_app` only calls `build_provider(settings)`.

Lazy imports inside `build_provider` keep optional SDK dependencies from loading when running mock-only deployments. xAI uses the same tool schema as OpenAI-compatible clients. Settings validation rejects unknown provider enums at startup rather than failing on first chat.

## Files

- `src/robot_copilot/llm/gemini_provider.py`
- `src/robot_copilot/llm/xai_provider.py`
- `src/robot_copilot/llm/registry.py`
- `tests/providers/test_gemini.py`
- `tests/providers/test_xai.py`

```python
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
```

Gemini contract tests inspect a real serialized request object from the fake client; xAI tests assert the configured model id on the wire.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how gemini-xai behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Switch `RCC_PROVIDER` to mock in your shell and confirm `healthz` still reports the mock model without loading Gemini or xAI SDK clients.

## Checkpoint

- `tests/providers/test_gemini.py`
