from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Literal

from robot_copilot.llm.base import ProviderResult, Usage
from robot_copilot.plan import DeclineRequest, MissionPlan
from robot_copilot.tools import DECLINE_TOOL, PROPOSE_TOOL


def normalize(
    calls: Sequence[tuple[str, str | Mapping[str, object]]],
    text: str | None,
    stop: Literal["complete", "max_tokens", "refused", "blocked"],
    *,
    provider: str,
    model: str,
    max_args_bytes: int,
    max_text_chars: int = 4000,
    adjustment_notice: str | None = None,
) -> ProviderResult:
    usage = Usage()
    truncated = (text or "")[:max_text_chars] if text else None

    if stop in ("max_tokens",) and calls:
        return ProviderResult(
            kind="malformed",
            malformed_reason="incomplete",
            provider=provider,
            model=model,
            usage=usage,
        )
    if stop == "refused":
        return ProviderResult(
            kind="malformed",
            malformed_reason="refused",
            provider=provider,
            model=model,
            usage=usage,
        )
    if stop == "blocked":
        return ProviderResult(
            kind="malformed",
            malformed_reason="blocked",
            provider=provider,
            model=model,
            usage=usage,
        )
    if not calls and not text:
        return ProviderResult(
            kind="malformed",
            malformed_reason="empty",
            provider=provider,
            model=model,
            usage=usage,
        )
    if len(calls) >= 2:
        return ProviderResult(
            kind="malformed",
            malformed_reason="multiple_tool_calls",
            provider=provider,
            model=model,
            usage=usage,
        )
    if len(calls) == 1:
        name, args = calls[0]
        if name not in (PROPOSE_TOOL, DECLINE_TOOL):
            return ProviderResult(
                kind="malformed",
                malformed_reason="unknown_tool",
                provider=provider,
                model=model,
                usage=usage,
            )
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
            except json.JSONDecodeError:
                return ProviderResult(
                    kind="malformed",
                    malformed_reason="bad_arguments",
                    provider=provider,
                    model=model,
                    usage=usage,
                )
        else:
            parsed = dict(args)
        raw_bytes = json.dumps(parsed, allow_nan=False).encode()
        if len(raw_bytes) > max_args_bytes:
            return ProviderResult(
                kind="malformed",
                malformed_reason="too_large",
                provider=provider,
                model=model,
                usage=usage,
            )
        if not isinstance(parsed, dict):
            return ProviderResult(
                kind="malformed",
                malformed_reason="bad_arguments",
                provider=provider,
                model=model,
                usage=usage,
            )
        try:
            if name == PROPOSE_TOOL:
                MissionPlan.model_validate_json(json.dumps(parsed, allow_nan=False))
                return ProviderResult(
                    kind="plan",
                    tool_args=parsed,
                    provider=provider,
                    model=model,
                    usage=usage,
                    adjustment_notice=adjustment_notice,
                )
            DeclineRequest.model_validate_json(json.dumps(parsed, allow_nan=False))
            return ProviderResult(
                kind="decline",
                tool_args=parsed,
                provider=provider,
                model=model,
                usage=usage,
            )
        except Exception:
            return ProviderResult(
                kind="malformed",
                malformed_reason="bad_arguments",
                provider=provider,
                model=model,
                usage=usage,
            )
    return ProviderResult(
        kind="text",
        text=truncated or "",
        provider=provider,
        model=model,
        usage=usage,
    )
