from __future__ import annotations

import asyncio
import json

import httpx2
from pydantic import SecretStr

from robot_copilot.llm.anthropic_provider import AnthropicProvider
from robot_copilot.llm.base import ProposalRequest
from robot_copilot.tools import build_site_summary, tool_specs
from tests.fakes.sentinel import SENTINEL_ANTHROPIC
from tests.fakes.transport import recording_transport
from tests.helpers import load_ctx


def _req():
    ctx = load_ctx()
    summary = build_site_summary(ctx.site, ctx.vehicle)
    return ProposalRequest(
        system_prompt="system",
        history=[],
        user_message="inspect north fence",
        vehicle="drone",
        site_summary=summary,
        tools=tool_specs(),
    )


def test_tool_use_plan():
    plan = {"vehicle": "drone", "summary": "s", "actions": [{"type": "takeoff", "altitude_m": 30}]}

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["authorization"] == f"Bearer {SENTINEL_ANTHROPIC}"
        assert request.headers["anthropic-version"] == "2026-10-21"
        body = json.loads(request.content)
        assert "temperature" not in body and "top_p" not in body
        assert body["max_tokens"]
        return httpx2.Response(
            200,
            json={
                "id": "msg",
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t", "name": "propose_mission_plan", "input": plan}
                ],
                "model": "claude",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    transport = recording_transport({("POST", "/v1/messages"): handler})
    client = httpx2.AsyncClient(transport=transport, base_url="https://anthropic.test")
    prov = AnthropicProvider(
        "claude-sonnet-5-5",
        SecretStr(SENTINEL_ANTHROPIC),
        timeout_s=30,
        max_retries=0,
        max_output_tokens=1024,
        client=__import__("anthropic").AsyncAnthropic(
            api_key=SENTINEL_ANTHROPIC,
            http_client=client,
            max_retries=0,
        ),
    )
    res = asyncio.run(prov.propose(_req()))
    assert res.kind == "plan"


def test_two_tool_blocks_malformed():
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "id": "msg",
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "1", "name": "propose_mission_plan", "input": {}},
                    {"type": "tool_use", "id": "2", "name": "decline_request", "input": {}},
                ],
                "model": "claude",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    transport = recording_transport({("POST", "/v1/messages"): handler})
    client = httpx2.AsyncClient(transport=transport, base_url="https://anthropic.test")
    prov = AnthropicProvider(
        "m",
        SecretStr(SENTINEL_ANTHROPIC),
        timeout_s=30,
        max_retries=0,
        max_output_tokens=1024,
        client=__import__("anthropic").AsyncAnthropic(
            api_key=SENTINEL_ANTHROPIC,
            http_client=client,
            max_retries=0,
        ),
    )
    res = asyncio.run(prov.propose(_req()))
    assert res.kind == "malformed"
