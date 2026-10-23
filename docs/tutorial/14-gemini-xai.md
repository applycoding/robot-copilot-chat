# 14 Gemini and xAI providers

## Goal

build_provider selects Gemini or xAI implementations from settings while reusing shared tool specs and normalize helpers. Gemini contract tests validate client configuration fields without calling live Google APIs. xAI reuses OpenAI client patterns with a different base URL and model identifiers, keeping registry growth explicit and testable.

build_provider inspects settings.provider enum values and constructs the matching LLMProvider implementation. GeminiProvider configures Google GenAI clients with timeouts and retry policies from settings. Gemini function calling uses the same tool specs as Anthropic and OpenAI adapters.

xAIProvider subclasses OpenAIProvider with a different base URL and model identifiers. Contract tests validate HttpOptions fields without calling live Google APIs during CI. Registry module stays tiny so adding providers requires explicit enumeration and tests.

Gemini __init__ reads API keys and model names from AppSettings SecretStr fields. Provider names flow into audit logs and health endpoint output for operator clarity. Fail-closed HTTP transports in tests complement socket guards used elsewhere in the suite.

Gemini retries relate to max_retries settings documented in config/app.toml comments. xAI shares OpenAI parsing because chat completion shapes align for tool calls. Provider construction occurs once per process inside create_app for connection reuse.

Missing Gemini keys raise SettingsError messages naming required environment variables. Tool normalization enforces max arg bytes protecting SQLite from huge JSON blobs. Gemini tests include function call planning fixtures with deterministic fake responses.

Students should trace registry branches when switching RCC_PROVIDER between gemini and xai. Cloud provider chapters assume mock-first understanding from earlier tutorial sections. Keep registry errors loud; silent fallbacks to mock would hide misconfiguration in demos.

## Files

- `src/robot_copilot/llm/registry.py`
- `src/robot_copilot/llm/gemini_provider.py`
- `src/robot_copilot/llm/xai_provider.py`

## Walkthrough

1. build_provider is the only supported switch statement for instantiating providers from AppSettings.

<!-- segment: src/robot_copilot/llm/registry.py build_provider -->

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
```

New providers must register here and include tests/providers coverage before documentation claims support.

2. GeminiProvider.__init__ stores model id, API key, and HTTP options used on each propose call.

<!-- segment: src/robot_copilot/llm/gemini_provider.py GeminiProvider.__init__ -->

```python
    def __init__(
        self,
        model: str,
        api_key: SecretStr,
        *,
        timeout_s: float,
        max_retries: int,
        max_output_tokens: int,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._max_output_tokens = max_output_tokens
        self._max_args = 32768
        if client is not None:
            self._client = client
        else:
            from google import genai

            self._client = genai.Client(
                api_key=api_key.get_secret_value(),
                http_options=genai.types.HttpOptions(
                    timeout=int(timeout_s * 1000),
                    retry_options=genai.types.HttpRetryOptions(attempts=1 + max_retries),
                ),
            )
```

Initialization does not ping the network; health checks remain separate from client construction.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync pytest tests/providers/test_gemini_contract.py -q --no-header
```

### Expected

```
1 passed
```

## Exercise

Relate Gemini retry settings in config/app.toml to max_retries loaded in settings.

## Checkpoint

- `tests/providers/test_gemini.py::test_gemini_function_call_plan`
