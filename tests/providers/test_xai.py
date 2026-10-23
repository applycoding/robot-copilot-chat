from __future__ import annotations

import asyncio
import json

import httpx2
from pydantic import SecretStr

from robot_copilot.llm.base import ProposalRequest
from robot_copilot.llm.xai_provider import XAIProvider
from robot_copilot.settings import load_settings
from robot_copilot.tools import build_site_summary, tool_specs
from tests.fakes.sentinel import SENTINEL_XAI
from tests.fakes.transport import recording_transport
from tests.helpers import default_settings_env, load_ctx


def test_xai_responses_url():
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.host == "api.x.ai"
        assert request.headers["authorization"] == f"Bearer {SENTINEL_XAI}"
        return httpx2.Response(
            200,
            json={
                "id": "r",
                "output": [
                    {
                        "type": "function_call",
                        "name": "propose_mission_plan",
                        "arguments": json.dumps(
                            {
                                "vehicle": "drone",
                                "summary": "s",
                                "actions": [{"type": "takeoff", "altitude_m": 30}],
                            }
                        ),
                    }
                ],
                "status": "completed",
            },
        )

    transport = recording_transport({("POST", "/v1/responses"): handler})
    client = httpx2.AsyncClient(transport=transport, base_url="https://api.x.ai")
    import openai

    s = load_settings(env=default_settings_env(), dotenv_enabled=False)
    prov = XAIProvider(
        s.model if s.provider.value == "xai" else "grok-4.7",
        SecretStr(SENTINEL_XAI),
        base_url="https://api.x.ai/v1",
        timeout_s=30,
        max_retries=0,
        max_output_tokens=1024,
        client=openai.AsyncOpenAI(
            api_key=SENTINEL_XAI,
            base_url="https://api.x.ai/v1",
            http_client=client,
            max_retries=0,
        ),
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
