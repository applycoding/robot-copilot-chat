# 13 Anthropic and OpenAI providers

## Goal

You will compare how two cloud SDKs call the same tool schema while tests stay offline via injected transports. Anthropic uses Messages tool use without sampling knobs, while OpenAI uses Responses function calling. Both funnel through `normalize` and redact secrets before logging.

Tests inject mock HTTP transports so CI never opens outbound sockets, matching the offline guarantee in README. Redaction runs on provider error strings so keys copied from misconfigured `.env` files do not land in logs. Registry construction reads timeouts, retry counts, and token caps from `config/app.toml` so tuning does not require code changes. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter.

## Files

- `src/robot_copilot/llm/anthropic_provider.py`
- `src/robot_copilot/llm/openai_provider.py`
- `src/robot_copilot/llm/registry.py`

## Walkthrough

1. `AnthropicProvider.propose` builds tool definitions from `tool_specs()`. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    async def propose(self, request: ProposalRequest) -> ProviderResult:
        tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tool_specs()
        ]
        messages = [{"role": m.role, "content": m.content} for m in request.history]
        messages.append({"role": "user", "content": request.user_message})
        try:
            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=self._max_output_tokens,
                system=request.system_prompt,
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            )
        except Exception as exc:
            raise _map_error(exc) from exc

        stop = "complete"
        if resp.stop_reason == "max_tokens":
            stop = "max_tokens"
        elif resp.stop_reason == "refusal":
            stop = "refused"

        calls: list[tuple[str, dict[str, object]]] = []
        text_parts: list[str] = []
        for block in resp.content:
            if block.type == "tool_use":
                calls.append((block.name, block.input))
            elif block.type == "text":
                text_parts.append(block.text)
        text = "\n".join(text_parts) if text_parts else None
        return normalize(
            calls,
            text,
            stop,  # type: ignore[arg-type]
            provider=self.name,
            model=self.model,
            max_args_bytes=self._max_args,
        )


def _map_error(exc: Exception) -> ProviderError:
    from anthropic import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError

    msg = redact_text(str(exc))
    if isinstance(exc, AuthenticationError):
        return ProviderError("auth", msg)
    if isinstance(exc, RateLimitError):
        return ProviderError("rate_limit", msg)
    if isinstance(exc, APITimeoutError):
        return ProviderError("timeout", msg)
    if isinstance(exc, APIConnectionError):
        return ProviderError("unavailable", msg)
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return ProviderError("auth", msg)
    if status == 429:
        return ProviderError("rate_limit", msg)
    if status and int(status) >= 500:
        return ProviderError("unavailable", msg)
    return ProviderError("protocol", msg)
```

Sharing schemas with the mock provider keeps validator inputs identical across backends. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. `OpenAIProvider` mirrors the same propose contract with its SDK client. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    async def propose(self, request: ProposalRequest) -> ProviderResult:
        tools = [
            {
                "type": "function",
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "strict": False,
            }
            for t in tool_specs()
        ]
        input_msgs = [{"role": m.role, "content": m.content} for m in request.history]
        input_msgs.append({"role": "user", "content": request.user_message})
        try:
            resp = await self._client.responses.create(
                model=self.model,
                instructions=request.system_prompt,
                input=input_msgs,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
                store=False,
                max_output_tokens=self._max_output_tokens,
            )
        except Exception as exc:
            raise _map_error(exc) from exc

        stop = "complete"
        if getattr(resp, "status", None) == "incomplete":
            stop = "max_tokens"

        calls: list[tuple[str, str | dict[str, object]]] = []
        text_parts: list[str] = []
        for item in resp.output:
            if item.type == "function_call":
                calls.append((item.name, item.arguments))
            elif item.type == "message":
                for c in item.content:
                    if c.type == "output_text":
                        text_parts.append(c.text)
                    elif c.type == "refusal":
                        return normalize(
                            [],
                            None,
                            "refused",
                            provider=self.name,
                            model=self.model,
                            max_args_bytes=self._max_args,
                        )
        text = "\n".join(text_parts) if text_parts else None
        parsed_calls: list[tuple[str, str | dict[str, object]]] = []
        for name, args in calls:
            if isinstance(args, str):
                parsed_calls.append((name, args))
            else:
                parsed_calls.append((name, args))
        return normalize(
            parsed_calls,
            text,
            stop,  # type: ignore[arg-type]
            provider=self.name,
            model=self.model,
            max_args_bytes=self._max_args,
        )


def _map_error(exc: Exception) -> ProviderError:
    msg = redact_text(str(exc))
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return ProviderError("auth", msg)
    if status == 429:
        return ProviderError("rate_limit", msg)
    if status and int(status) >= 500:
        return ProviderError("unavailable", msg)
    if "timeout" in msg.lower():
        return ProviderError("timeout", msg)
    return ProviderError("protocol", msg)
```

Provider tests assert serialized HTTP bodies using `httpx2.MockTransport`. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. `build_provider` selects the implementation from `AppSettings.provider`. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

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

Switching providers is an environment change, not a code fork. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -m pytest tests/providers/test_anthropic.py -q --no-header -k request
```

Expected tail line:

```
1 passed
```

## Exercise

Read `tests/providers/test_openai.py` and list which malformed stop reason must not create a confirmable mission. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/providers/test_anthropic.py::test_tool_use_plan`
