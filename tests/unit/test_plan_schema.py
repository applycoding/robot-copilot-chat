from __future__ import annotations

import json

import pytest

from robot_copilot.plan import MissionPlan
from robot_copilot.tools import inline_schema
from robot_copilot.validator import validate_raw
from tests.helpers import load_ctx


def test_inline_schema_no_meta():
    schema = inline_schema(MissionPlan)
    blob = json.dumps(schema)
    assert "$ref" not in blob
    assert "discriminator" not in blob
    assert '"title"' not in blob


@pytest.mark.parametrize(
    "patch,expect_schema",
    [
        ({"vehicle": True}, True),
        ({"actions": [{"type": "goto", "place": "Barn", "point_index": 1.5}]}, True),
        ({"actions": [{"type": "goto", "place": "Barn", "speed_mps": "8"}]}, True),
        (
            {"actions": [{"type": "goto", "place": "Barn", "xy": {"x_m": float("nan"), "y_m": 0}}]},
            True,
        ),
        ({"actions": [{"type": "goto", "place": "Barn", "extra": 1}]}, True),
        ({"actions": [{"type": "goto"}]}, True),
    ],
)
def test_raw_json_schema_errors(patch, expect_schema):
    base = {
        "vehicle": "drone",
        "summary": "s",
        "actions": [{"type": "takeoff", "altitude_m": 30}, {"type": "return_home"}],
    }
    base.update(patch)
    if "actions" in patch:
        base["actions"] = patch["actions"]
    _, rep = validate_raw(base, load_ctx())
    assert (not rep.ok) == expect_schema
    if expect_schema:
        assert any(i.code.value == "schema" for i in rep.issues)


def test_int_accepted_for_float_field():
    raw = {
        "vehicle": "drone",
        "summary": "s",
        "actions": [{"type": "takeoff", "altitude_m": 30}, {"type": "return_home"}],
    }
    plan, _rep = validate_raw(raw, load_ctx())
    assert plan is not None
