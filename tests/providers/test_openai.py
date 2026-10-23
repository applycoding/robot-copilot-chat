from __future__ import annotations

import asyncio
import json

import httpx2
from pydantic import SecretStr

from robot_copilot.llm.base import ProposalRequest
from robot_copilot.llm.openai_provider import OpenAIProvider
from robot_copilot.tools import build_site_summary, tool_specs
from tests.fakes.sentinel import SENTINEL_OPENAI
from tests.fakes.transport import recording_transport
from tests.helpers import load_ctx


def test_responses_function_call():
    plan = {"vehicle": "drone", "summary": "s", "actions": [{"type": "takeoff", "altitude_m": 30}]}

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        assert body.get("parallel_tool_calls") is False
        assert body.get("store") is False
        assert "temperature" not in body
        return httpx2.Response(
            200,
            json={
                "id": "resp",
                "output": [
                    {
                        "type": "function_call",
                        "name": "propose_mission_plan",
                        "arguments": json.dumps(plan),
                    }
                ],
                "status": "completed",
            },
        )

    transport = recording_transport({("POST", "/v1/responses"): handler})
    client = httpx2.AsyncClient(transport=transport, base_url="https://openai.test")
    import openai

    prov = OpenAIProvider(
        "gpt-6.1-sol",
        SecretStr(SENTINEL_OPENAI),
        timeout_s=30,
        max_retries=0,
        max_output_tokens=1024,
        client=openai.AsyncOpenAI(api_key=SENTINEL_OPENAI, http_client=client, max_retries=0),
    )
    ctx = load_ctx()
    req = ProposalRequest(
        system_prompt="s",
        history=[],
        user_message="hi",
        vehicle="drone",
        site_summary=build_site_summary(ctx.site, ctx.vehicle),
        tools=tool_specs(),
    )
    res = asyncio.run(prov.propose(req))
    assert res.kind == "plan"
