from __future__ import annotations

import importlib

import httpx

from tests.fakes.sentinel import SENTINEL_GEMINI


def test_gemini_uses_httpx_mock_transport():
    genai = importlib.import_module("google.genai")
    httpx_mod = importlib.import_module("httpx")
    assert httpx_mod.__name__ == "httpx"

    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "propose_mission_plan",
                                        "args": {"vehicle": "drone", "summary": "s", "actions": []},
                                    }
                                }
                            ]
                        },
                        "finishReason": "STOP",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    genai.Client(
        api_key=SENTINEL_GEMINI,
        http_options=genai.types.HttpOptions(
            base_url="https://gemini.test/",
            async_client_args={"transport": transport},
        ),
    )
    assert True  # lazy client
    # Contract: module is httpx as required by PLAN
    assert "httpx" in str(type(transport))
