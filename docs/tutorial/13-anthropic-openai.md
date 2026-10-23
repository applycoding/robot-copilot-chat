# 13 Anthropic and OpenAI providers

## Goal

You are reading tutorial chapter 13 about tool-use adapters in robot-copilot-chat. Chapter 13 links tool-use adapters to validators, confirmation hashes, and local simulation gates. Learning note 13-1: AnthropicProvider wraps Messages API calls with tool definitions matching mock propose and decline shapes. Learning note 13-2: propose maps SDK responses into ProviderResult objects consumed uniformly by orchestrator. Learning note 13-3: _map_error translates transport failures, rate limits, and auth problems into ProviderError codes. Learning note 13-4: OpenAIProvider shares parsing helpers where stop reasons and tool calls align with Anthropic flows. Learning note 13-5: Tests inject mock HTTP transports so CI never opens outbound sockets during provider unit tests. Learning note 13-6: API keys load from settings SecretStr fields redacted in repr output for safer logs. Learning note 13-7: Tool schemas originate from tools.tool_specs to prevent drift across providers. Learning note 13-8: Timeouts and retries read from config/app.toml, not hardcoded constants in provider classes. Learning note 13-9: Malformed tool JSON triggers MALFORMED_OUTPUT issues after normalization fails validation. Learning note 13-10: Provider concurrency semaphores still gate Anthropic calls even when keys are present. Learning note 13-11: Operation timeouts cancel hung SDK calls with ProviderError timeout messages. Learning note 13-12: Usage metadata captures token counts for future cost dashboards without affecting validation. Learning note 13-13: Repair prompts reuse render_repair_message to build consistent textual context alongside tools. Learning note 13-14: Anthropic tests lock request shapes when SDK upgrades change keyword arguments. Learning note 13-15: OpenAI tests cover stop reasons that must not yield confirmable missions without tools. Learning note 13-16: Registry construction selects Anthropic when RCC_PROVIDER environment variables request it. Learning note 13-17: Missing keys raise SettingsError at startup rather than failing mysteriously on first chat. Learning note 13-18: Students should compare mock regex routing with real tool-call payloads to see structural parity.

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
