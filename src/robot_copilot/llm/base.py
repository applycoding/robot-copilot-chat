from __future__ import annotations

import json
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from robot_copilot.tools import SiteSummary, ToolSpec
from robot_copilot.vehicles import VehicleKind


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class IssueBrief(BaseModel):
    code: str
    action_index: int | None
    message: str


class RepairContext(BaseModel):
    attempt: int = Field(ge=1)
    previous_plan: dict[str, object] | None
    issues: list[IssueBrief]


class ProposalRequest(BaseModel):
    system_prompt: str
    history: list[ChatTurn]
    user_message: str
    vehicle: VehicleKind
    site_summary: SiteSummary
    tools: list[ToolSpec]
    repair: RepairContext | None = None


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


MalformedReason = Literal[
    "multiple_tool_calls",
    "unknown_tool",
    "bad_arguments",
    "too_large",
    "incomplete",
    "refused",
    "blocked",
    "empty",
]


class ProviderResult(BaseModel):
    kind: Literal["plan", "decline", "text", "malformed"]
    tool_args: dict[str, object] | None = None
    text: str | None = None
    malformed_reason: MalformedReason | None = None
    provider: str
    model: str
    usage: Usage | None = None


class ProviderError(Exception):
    def __init__(
        self,
        kind: Literal["auth", "rate_limit", "timeout", "unavailable", "protocol"],
        message: str,
    ) -> None:
        self.kind = kind
        super().__init__(message)


class LLMProvider(Protocol):
    name: str
    model: str

    async def propose(self, request: ProposalRequest) -> ProviderResult: ...
    async def aclose(self) -> None: ...


def render_repair_message(repair: RepairContext) -> str:
    lines = [f"Repair attempt {repair.attempt}."]
    if repair.previous_plan:
        lines.append("Previous plan JSON:")
        lines.append(json.dumps(repair.previous_plan, sort_keys=True))
    for issue in repair.issues:
        idx = issue.action_index
        step = f"step {idx + 1}" if idx is not None else "mission"
        lines.append(f"{step}: [{issue.code}] {issue.message}")
    return "\n".join(lines)
