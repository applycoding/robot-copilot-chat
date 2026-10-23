# 14 Gemini and xAI providers

## Goal

You will wire Google Gemini with millisecond HTTP timeouts, automatic function calling disabled, and JSON schema parameters. xAI reuses the OpenAI client with a different base URL. Contract tests ensure HttpOptions and schema fields match what production code expects.

Gemini contract tests assert HttpOptions fields without calling Google, which catches SDK upgrades early. xAI reuses OpenAI parsing because the API shape matches; only base URL and model id differ. Both providers still emit the same propose and decline tools, which keeps orchestrator branching minimal. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter.

## Files

- `src/robot_copilot/llm/gemini_provider.py`
- `src/robot_copilot/llm/xai_provider.py`
- `src/robot_copilot/llm/registry.py`

## Walkthrough

1. Gemini constructs `HttpOptions` with timeout derived from settings seconds. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
            from google import genai

            self._client = genai.Client(
                api_key=api_key.get_secret_value(),
                http_options=genai.types.HttpOptions(
                    timeout=int(timeout_s * 1000),
                    retry_options=genai.types.HttpRetryOptions(attempts=1 + max_retries),
                ),
            )
```

Closing the async client in lifespan prevents leaked sockets in long-running demos. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. `GeminiProvider.propose` declares function tools with `parameters_json_schema`. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    async def propose(self, request: ProposalRequest) -> ProviderResult:
        from google.genai import types

        decls = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters_json_schema=t.parameters,
            )
            for t in tool_specs()
        ]
        contents = []
        for m in request.history:
            role = "model" if m.role == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=m.content)]))
        contents.append(types.Content(role="user", parts=[types.Part(text=request.user_message)]))
        try:
            resp = await self._client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=request.system_prompt,
                    max_output_tokens=self._max_output_tokens,
                    tools=[types.Tool(function_declarations=decls)],
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode=types.FunctionCallingConfigMode.AUTO
                        )
                    ),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        except Exception as exc:
            raise ProviderError("protocol", redact_text(str(exc))) from exc

        stop = "complete"
        fr = resp.candidates[0].finish_reason if resp.candidates else None
        if fr and "MAX_TOKENS" in str(fr):
            stop = "max_tokens"
        if fr and any(x in str(fr) for x in ("SAFETY", "BLOCK", "PROHIBITED")):
            stop = "blocked"

        calls: list[tuple[str, dict[str, object]]] = []
        text = resp.text or None
        if resp.candidates:
            for part in resp.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    args = dict(fc.args) if fc.args else {}
                    calls.append((fc.name, args))
        return normalize(
            calls,
            text,
            stop,  # type: ignore[arg-type]
            provider=self.name,
            model=self.model,
            max_args_bytes=self._max_args,
        )
```

Disabling AFC ensures the model cannot silently add extra tool rounds outside normalization. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. `XAIProvider` subclasses OpenAI wiring with a configurable base URL. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    def __init__(
        self,
        model: str,
        api_key: SecretStr,
        *,
        base_url: str,
        timeout_s: float,
        max_retries: int,
        max_output_tokens: int,
        client: Any | None = None,
    ) -> None:
        super().__init__(
            model,
            api_key,
            base_url=base_url,
            timeout_s=timeout_s,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
            client=client,
        )
```

Reusing normalization means xAI inherits the same single-call semantics as OpenAI tests. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -m pytest tests/providers/test_gemini_contract.py -q --no-header
```

Expected:

```
1 passed
```

## Exercise

Find where Gemini retry attempts are configured and relate that value to `max_retries` in settings. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/providers/test_gemini.py::test_gemini_function_call_plan`
