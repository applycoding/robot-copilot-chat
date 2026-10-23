# 13 Anthropic and OpenAI adapters

Cloud providers implement the shared `LLMProvider` protocol. `AnthropicProvider` and `OpenAIProvider` serialize tool definitions from `tools.py`, honor timeout and retry settings from `config/app.toml`, and normalize responses through `llm/normalize.py` so downstream validation always sees the same shapes.

Tests inject SDK clients backed by `httpx2.MockTransport` to assert outbound URLs, models, tool schemas, and parsing of text, decline, malformed, and HTTP error responses without live network I/O.

OpenAI tests assert `max_output_tokens` and handle malformed, incomplete, and refusal responses distinctly. Both providers map tool arguments through the same normalizer so validator code never branches on vendor JSON quirks. API keys never appear in exception messages thanks to shared redaction helpers.

## Files

- `src/robot_copilot/llm/anthropic_provider.py`
- `src/robot_copilot/llm/openai_provider.py`
- `tests/providers/test_anthropic.py`
- `tests/providers/test_openai.py`

```python
class AnthropicProvider:
    name = "anthropic"

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
            import anthropic

            self._client = anthropic.AsyncAnthropic(
                api_key=api_key.get_secret_value(),
                timeout=timeout_s,
                max_retries=max_retries,
            )
```

Provider tests also cover 401, 429, 500, and timeout paths with `max_retries=2` where configured.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how anthropic-openai behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Open `tests/providers/test_anthropic.py` and list every HTTP header or body field the mock transport asserts on the outbound request.

## Checkpoint

- `tests/providers/test_anthropic.py`
