from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from pydantic import ValidationError

from robot_copilot.json_util import canonical_json
from robot_copilot.plan import MissionPlan
from robot_copilot.validator.context import ValidationContext

__all__ = [
    "ValidationContext",
    "plan_hash",
    "validate",
    "validate_raw",
]
from robot_copilot.validator.explain import explain_issue
from robot_copilot.validator.issues import (
    VALIDATOR_VERSION,
    IssueCode,
    ValidationIssue,
    ValidationReport,
    issue_sort_key,
)
from robot_copilot.validator.resolve import (
    build_resolved,
    check_spatial_and_energy,
    final_state_after_plan,
)
from robot_copilot.validator.structure import validate_structure


def plan_hash(plan: MissionPlan, ctx: ValidationContext) -> str:
    payload = "|".join(
        [
            canonical_json(plan.model_dump(mode="json")),
            ctx.site.fingerprint(),
            canonical_json(ctx.vehicle.model_dump(mode="json")),
            str(ctx.battery_pct),
            VALIDATOR_VERSION,
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _schema_issues(exc: ValidationError) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"])
        params = {"location": loc, "detail": err["msg"]}
        msg, hint = explain_issue(IssueCode.SCHEMA, _action_index_from_loc(loc), params)
        issues.append(
            ValidationIssue(
                code=IssueCode.SCHEMA,
                severity="error",
                action_index=_action_index_from_loc(loc),
                params=(("location", loc), ("detail", err["msg"])),
                message=msg,
                hint=hint,
            )
        )
    return issues


def _action_index_from_loc(loc: str) -> int | None:
    parts = loc.split(".")
    for i, p in enumerate(parts):
        if p == "actions" and i + 1 < len(parts) and parts[i + 1].isdigit():
            return int(parts[i + 1])
    return None


def validate(plan: MissionPlan, ctx: ValidationContext) -> ValidationReport:
    issues = validate_structure(plan, ctx)
    if issues:
        issues_sorted = tuple(sorted(issues, key=issue_sort_key))
        return ValidationReport(
            ok=False,
            issues=issues_sorted,
            resolved=None,
            plan_hash=plan_hash(plan, ctx),
            validator_version=VALIDATOR_VERSION,
        )

    resolved = build_resolved(plan, ctx)
    end_state = final_state_after_plan(plan, ctx)
    issues.extend(check_spatial_and_energy(resolved, ctx, end_state))
    issues_sorted = tuple(sorted(issues, key=issue_sort_key))
    ok = not any(i.severity == "error" for i in issues_sorted)
    return ValidationReport(
        ok=ok,
        issues=issues_sorted,
        resolved=resolved if ok else None,
        plan_hash=plan_hash(plan, ctx),
        validator_version=VALIDATOR_VERSION,
    )


def validate_raw(
    tool_args: Mapping[str, object],
    ctx: ValidationContext,
) -> tuple[MissionPlan | None, ValidationReport]:
    try:
        raw = json.dumps(tool_args, allow_nan=False)
        plan = MissionPlan.model_validate_json(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            issues = _schema_issues(exc)
        else:
            msg, hint = explain_issue(IssueCode.SCHEMA, None, {"location": "", "detail": str(exc)})
            issues = [
                ValidationIssue(
                    code=IssueCode.SCHEMA,
                    severity="error",
                    action_index=None,
                    params=(("detail", str(exc)),),
                    message=msg,
                    hint=hint,
                )
            ]
        report = ValidationReport(
            ok=False,
            issues=tuple(sorted(issues, key=issue_sort_key)),
            resolved=None,
            plan_hash=None,
            validator_version=VALIDATOR_VERSION,
        )
        return None, report
    report = validate(plan, ctx)
    return plan, report
