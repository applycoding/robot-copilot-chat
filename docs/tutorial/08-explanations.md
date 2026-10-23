# 08 Human-readable explanations

`explain.py` turns `ValidationIssue` records into operator-facing sentences and hints. Every `IssueCode` has a template; step-specific codes prepend `Step N:` via `_step()`. Successful plans become a single summary line with display-case place names, photo counts, distance, duration, and energy statistics.

Rover summaries capitalize visit clauses and end with dock wording instead of drone landing language:

`describe_report` collapses multiple issues into a single assistant string for invalid missions, respecting `max_issues` to keep responses readable. Hints are stable, short imperatives suitable for repair prompts. Unknown-place suggestions append a question when fuzzy alias matches exist in site metadata.

## Files

- `src/robot_copilot/validator/explain.py`
- `tests/unit/test_explain.py`

```python
    for display, pts, photos in visits:
        verb = "Visit" if plan.vehicle == "rover" else "visit"
        seg = f"{verb} {display}"
        if pts > 1:
            seg = f"{verb} {display} ({pts} points)"
        if photos:
            word = "photo" if photos == 1 else "photos"
            seg = f"{seg} taking {photos} {word}"
        parts.append(seg)
    if any(a.type == "return_home" for a in plan.actions):
        if plan.vehicle == "rover":
            parts.append("then return to the dock and park")
        else:
            parts.append("then return home and land")
```

The North Fence golden sentence in `test_explain.py` must match exactly; criterion 3 in the plan spec depends on it.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how explanations behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Compare `describe_plan` output for the North Fence reference plan against `NORTH_FENCE_GOLDEN` in the unit test file.

## Checkpoint

- `tests/unit/test_explain.py::test_describe_plan_north_fence`
