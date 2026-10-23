from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from robot_copilot.llm.base import ProposalRequest, ProviderError, ProviderResult
from robot_copilot.llm.normalize import normalize
from robot_copilot.redact import redact_text
from robot_copilot.tools import tool_specs


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

    async def aclose(self) -> None:
        await self._client.close()

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
