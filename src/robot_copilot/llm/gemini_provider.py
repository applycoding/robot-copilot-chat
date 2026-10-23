from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from robot_copilot.llm.base import ProposalRequest, ProviderError, ProviderResult
from robot_copilot.llm.normalize import normalize
from robot_copilot.redact import redact_text
from robot_copilot.tools import tool_specs


class GeminiProvider:
    name = "gemini"

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

    async def aclose(self) -> None:
        await self._client.aio.aclose()

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
