import asyncio

from robot_copilot.llm.base import ProposalRequest
from robot_copilot.llm.mock import MockProvider
from robot_copilot.tools import build_site_summary, tool_specs
from robot_copilot.validator import validate_raw

PHRASES = [
    ("inspect the north fence", "drone"),
    ("take a photo of the barn", "drone"),
    ("drive to the pond", "rover"),
]


def test_happy_phrases(ctx):
    summary = build_site_summary(ctx.site, ctx.vehicle)

    async def run(msg, veh):
        mp = MockProvider("mock-1")
        req = ProposalRequest(
            system_prompt="",
            history=[],
            user_message=msg,
            vehicle=veh,
            site_summary=summary,
            tools=tool_specs(),
        )
        res = await mp.propose(req)
        _, rep = validate_raw(
            res.tool_args or {},
            ctx
            if veh == "drone"
            else type(ctx)(
                ctx.site,
                ctx.geometry,
                __import__("robot_copilot.vehicles", fromlist=["load_vehicles"]).load_vehicles(
                    __import__("robot_copilot.settings", fromlist=["load_settings"])
                    .load_settings(env={"RCC_DOTENV": "off"}, dotenv_enabled=False)
                    .vehicles_path
                )["rover"],
                ctx.battery_pct,
            ),
        )
        return rep.ok

    for msg, veh in PHRASES:
        ok = asyncio.run(run(msg, veh))
        assert ok, msg


def test_patrol_calibration(ctx):
    from robot_copilot.llm.mock import _patrol_wrapped
    from robot_copilot.plan import MissionPlan
    from robot_copilot.validator import validate

    for loops, expect in [(4, False), (2, False), (1, True)]:
        actions = _patrol_wrapped(loops, "drone")
        plan = MissionPlan.model_validate_json(
            __import__("json").dumps({"vehicle": "drone", "summary": "p", "actions": actions})
        )
        c = type(ctx)(ctx.site, ctx.geometry, ctx.vehicle, 40)
        rep = validate(plan, c)
        assert rep.ok == expect, loops
