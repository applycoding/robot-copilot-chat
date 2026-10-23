# 13 Anthropic and OpenAI providers

## Goal

Cloud providers wrap vendor SDKs but return the same ProviderResult shapes as the mock. Anthropic and OpenAI adapters map tool calls into propose and decline flows validated by orchestrator commits. Unit tests inject fake HTTP transports so CI never opens outbound sockets while still asserting tool-use plans parse correctly.

## Files

- `src/robot_copilot/llm/anthropic_provider.py`
- `src/robot_copilot/llm/openai_provider.py`
- `tests/providers/test_anthropic.py`

## Walkthrough

1. AnthropicProvider.propose assembles tools, messages, and repair context into a single SDK request.

<!-- segment: src/robot_copilot/llm/anthropic_provider.py AnthropicProvider.propose -->

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
```

Responses pass through normalize before orchestrator sees ProviderResult instances.

2. _map_error centralizes failure classification so orchestrator can decide whether to surface chat errors or repair failures.

<!-- segment: src/robot_copilot/llm/anthropic_provider.py _map_error -->

```python
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

Redaction runs on error strings before they reach logs or HTTP responses.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync pytest tests/providers/test_anthropic.py::test_tool_use_plan -q --no-header
```

### Expected

```
1 passed
```

## Exercise

Read tests/providers/test_openai.py for stop reasons that must not create confirmable missions.

## Checkpoint

- `tests/providers/test_anthropic.py::test_tool_use_plan`
