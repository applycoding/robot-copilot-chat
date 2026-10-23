from __future__ import annotations

import pytest

from robot_copilot.llm.normalize import normalize
from robot_copilot.tools import DECLINE_TOOL, PROPOSE_TOOL

PLAN = {
    "vehicle": "drone",
    "summary": "x",
    "actions": [{"type": "takeoff", "altitude_m": 30}, {"type": "return_home"}],
}


@pytest.mark.parametrize(
    "calls,text,stop,kind,reason",
    [
        ([(PROPOSE_TOOL, PLAN)], None, "max_tokens", "malformed", "incomplete"),
        ([], None, "refused", "malformed", "refused"),
        ([], None, "blocked", "malformed", "blocked"),
        ([], None, "complete", "malformed", "empty"),
        (
            [(PROPOSE_TOOL, PLAN), (DECLINE_TOOL, {"reason": "x", "category": "unsafe"})],
            None,
            "complete",
            "malformed",
            "multiple_tool_calls",
        ),
        ([("other", {})], None, "complete", "malformed", "unknown_tool"),
        ([(PROPOSE_TOOL, "not-json")], None, "complete", "malformed", "bad_arguments"),
        ([(PROPOSE_TOOL, PLAN)], None, "complete", "plan", None),
        (
            [(DECLINE_TOOL, {"reason": "nope", "category": "unsafe"})],
            None,
            "complete",
            "decline",
            None,
        ),
        ([], "hello", "complete", "text", None),
    ],
)
def test_normalize_table(calls, text, stop, kind, reason):
    res = normalize(calls, text, stop, provider="mock", model="mock-1", max_args_bytes=32768)
    assert res.kind == kind
    if reason:
        assert res.malformed_reason == reason
