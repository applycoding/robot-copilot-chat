from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pydantic import SecretStr

from robot_copilot.llm.base import ProposalRequest
from robot_copilot.llm.gemini_provider import GeminiProvider
from robot_copilot.tools import build_site_summary, tool_specs
from tests.helpers import load_ctx


def test_gemini_function_call_plan():
    fc = SimpleNamespace(
        name="propose_mission_plan",
        args={
            "vehicle": "drone",
            "summary": "s",
            "actions": [{"type": "takeoff", "altitude_m": 30}, {"type": "return_home"}],
        },
    )
    part = SimpleNamespace(function_call=fc, text=None)
    cand = SimpleNamespace(
        finish_reason="STOP",
        content=SimpleNamespace(parts=[part]),
    )
    resp = SimpleNamespace(candidates=[cand], text=None)

    aio = MagicMock()
    aio.models.generate_content = AsyncMock(return_value=resp)
    aio.aclose = AsyncMock()
    client = MagicMock()
    client.aio = aio

    prov = GeminiProvider(
        "gemini-3.8-flash",
        SecretStr("k"),
        timeout_s=30,
        max_retries=0,
        max_output_tokens=1024,
        client=client,
    )
    ctx = load_ctx()
    req = ProposalRequest(
        system_prompt="s",
        history=[
            __import__("robot_copilot.llm.base", fromlist=["ChatTurn"]).ChatTurn(
                role="assistant", content="hi"
            )
        ],
        user_message="u",
        vehicle="drone",
        site_summary=build_site_summary(ctx.site, ctx.vehicle),
        tools=tool_specs(),
    )
    res = asyncio.run(prov.propose(req))
    assert res.kind == "plan"
    asyncio.run(prov.aclose())
    aio.aclose.assert_awaited()
