from __future__ import annotations

import asyncio

from robot_copilot.llm.base import IssueBrief, ProposalRequest, RepairContext
from robot_copilot.llm.mock import MockProvider, _patrol_wrapped
from robot_copilot.tools import build_site_summary, tool_specs
from robot_copilot.validator import validate_raw
from tests.helpers import load_ctx


def _req(msg: str, vehicle: str = "drone", repair=None):
    ctx = load_ctx(vehicle, 100)
    summary = build_site_summary(ctx.site, ctx.vehicle)
    return ProposalRequest(
        system_prompt="",
        history=[],
        user_message=msg,
        vehicle=vehicle,  # type: ignore[arg-type]
        site_summary=summary,
        tools=tool_specs(),
        repair=repair,
    )


def test_inspect_north_fence():
    mp = MockProvider("mock-1")
    res = asyncio.run(mp.propose(_req("inspect the north fence")))
    assert res.kind == "plan"
    _, rep = validate_raw(res.tool_args or {}, load_ctx())
    assert rep.ok


def test_decline_drop_payload():
    mp = MockProvider("mock-1")
    res = asyncio.run(mp.propose(_req("drop the payload on the barn")))
    assert res.kind == "decline"


def test_patrol_halving():
    assert (
        len(_patrol_wrapped(4, "drone"))
        > len(_patrol_wrapped(2, "drone"))
        > len(_patrol_wrapped(1, "drone"))
    )


def test_model_id_from_constructor():
    mp = MockProvider("custom-model")
    assert mp.model == "custom-model"


def test_repair_speed():
    mp = MockProvider("mock-1")
    repair = RepairContext(
        attempt=1,
        previous_plan={
            "vehicle": "drone",
            "summary": "s",
            "actions": [
                {"type": "takeoff", "altitude_m": 30},
                {"type": "goto", "place": "Barn", "speed_mps": 25},
                {"type": "return_home"},
            ],
        },
        issues=[IssueBrief(code="speed_high", action_index=1, message="m")],
    )
    res = asyncio.run(mp.propose(_req("fix", repair=repair)))
    assert res.kind == "plan"
    speed = res.tool_args["actions"][1].get("speed_mps")  # type: ignore[index]
    assert speed == 15.0


def test_deterministic():
    mp = MockProvider("mock-1")
    a = asyncio.run(mp.propose(_req("hello")))
    b = asyncio.run(mp.propose(_req("hello")))
    assert a.text == b.text
