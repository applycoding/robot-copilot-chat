from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from robot_copilot.llm.openai_provider import OpenAIProvider


class XAIProvider(OpenAIProvider):
    name = "xai"

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
