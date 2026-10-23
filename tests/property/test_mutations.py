from __future__ import annotations

import copy

import pytest

from robot_copilot.validator import validate
from robot_copilot.validator.issues import IssueCode
from tests.helpers import load_ctx, plan_from_json
from tests.property.generators import constructive_valid_mission


@pytest.fixture
def base_plan():
    return constructive_valid_mission(__import__("random").Random(1))


def test_mutate_altitude_high(base_plan):
    data = copy.deepcopy(base_plan)
    data["actions"][0]["altitude_m"] = 200
    rep = validate(plan_from_json(data), load_ctx())
    assert any(i.code == IssueCode.ALTITUDE_HIGH for i in rep.issues)


def test_mutate_unknown_place(base_plan):
    data = copy.deepcopy(base_plan)
    data["actions"][1]["place"] = "Nowhere"
    rep = validate(plan_from_json(data), load_ctx())
    assert any(i.code == IssueCode.UNKNOWN_PLACE for i in rep.issues)


def test_mutate_remove_return_home(base_plan):
    data = copy.deepcopy(base_plan)
    data["actions"] = [a for a in data["actions"] if a["type"] != "return_home"]
    rep = validate(plan_from_json(data), load_ctx())
    assert not rep.ok
