from __future__ import annotations

import json

from robot_copilot.validator import validate
from robot_copilot.validator.issues import IssueCode, ValidationIssue, issue_sort_key
from tests.conftest import run_validator_subprocess
from tests.helpers import load_ctx, north_fence_plan_json, plan_from_json


def test_issue_sort_key_order():
    a = ValidationIssue(
        code=IssueCode.ALTITUDE_HIGH,
        severity="error",
        action_index=1,
        params=(),
        message="m",
        hint="h",
    )
    b = ValidationIssue(
        code=IssueCode.ALTITUDE_HIGH,
        severity="error",
        action_index=None,
        params=(),
        message="m",
        hint="h",
    )
    c = ValidationIssue(
        code=IssueCode.ALTITUDE_HIGH,
        severity="error",
        action_index=0,
        params=(),
        message="m",
        hint="h",
    )
    ordered = sorted([a, b, c], key=issue_sort_key)
    assert ordered[0].action_index is None
    assert ordered[1].action_index == 0
    assert ordered[2].action_index == 1


def test_byte_identical_json():
    ctx = load_ctx()
    plan = plan_from_json(north_fence_plan_json())
    j1 = validate(plan, ctx).model_dump_json()
    j2 = validate(plan, ctx).model_dump_json()
    assert j1 == j2


def test_subprocess_identical():
    ctx = load_ctx()
    plan = plan_from_json(north_fence_plan_json())
    j1 = validate(plan, ctx).model_dump_json()
    j2 = run_validator_subprocess(json.dumps(north_fence_plan_json()))
    assert j1 == j2


def test_hash_changes_with_battery():
    plan = plan_from_json(north_fence_plan_json())
    h1 = validate(plan, load_ctx(battery_pct=100)).plan_hash
    h2 = validate(plan, load_ctx(battery_pct=50)).plan_hash
    assert h1 != h2
