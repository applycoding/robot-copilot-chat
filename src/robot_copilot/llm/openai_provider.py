from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from robot_copilot.llm.base import ProposalRequest, ProviderError, ProviderResult
from robot_copilot.llm.normalize import normalize
from robot_copilot.redact import redact_text
from robot_copilot.tools import tool_specs


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        model: str,
        api_key: SecretStr,
        *,
        base_url: str | None = None,
        timeout_s: float = 30.0,
        max_retries: int = 1,
        max_output_tokens: int = 2048,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._max_output_tokens = max_output_tokens
        self._max_args = 32768
        if client is not None:
            self._client = client
        else:
            import openai

            self._client = openai.AsyncOpenAI(
                api_key=api_key.get_secret_value(),
                base_url=base_url,
                timeout=timeout_s,
                max_retries=max_retries,
            )

    async def aclose(self) -> None:
        await self._client.close()

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
