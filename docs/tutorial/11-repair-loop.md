# 11 Repair loop

## Goal

You are reading tutorial chapter 11 about provider rework and attempt limits in robot-copilot-chat. Chapter 11 links provider rework and attempt limits to validators, confirmation hashes, and local simulation gates. Learning note 11-1: Repair reuses provider propose with structured issue briefs instead of raw validator JSON dumps. Learning note 11-2: Orchestrator.repair checks mission status, repair_attempts, and max_repairs before reserving attempts. Learning note 11-3: reserve_repair uses optimistic concurrency so parallel repair clicks do not double consume budget. Learning note 11-4: Provider failures during repair still increment attempts via commit_repair_failure paths. Learning note 11-5: repair_exhausted status tells the UI to stop offering repair buttons for that mission. Learning note 11-6: Mock repair can fix energy issues by adjusting plans when prompts include sufficient guidance. Learning note 11-7: Issue briefs carry codes, action indexes, and messages aligned with explain_issue templates. Learning note 11-8: Repair responses use kind plan when a new valid revision is committed successfully. Learning note 11-9: Stale repair requests return conflict codes so clients reload mission state before retrying. Learning note 11-10: max_repairs defaults come from settings and should be covered by API tests, not fictional guard suites. Learning note 11-11: Provider concurrency semaphores apply equally to repair and initial chat provider calls. Learning note 11-12: tests/unit/test_settings.py asserts provider_concurrency equals four from config/app.toml defaults. Learning note 11-13: Conversation locks serialize repair commits per thread while allowing global semaphore throttling. Learning note 11-14: Repair does not bypass confirmation; operators must still hash-confirm valid revisions. Learning note 11-15: Audit events note repair attempts for later review in teaching scenarios about autonomy governance. Learning note 11-16: Structured briefs keep token usage stable compared to embedding entire previous plans. Learning note 11-17: Invalid missions retain previous plan JSON in revisions table for diff-friendly audits. Learning note 11-18: Understanding repair aids debugging when classroom chats produce almost-correct mock missions.

## Files

- `src/robot_copilot/orchestrator.py`
- `src/robot_copilot/store.py`
- `tests/api/test_repair_flow.py`

## Walkthrough

1. Orchestrator.repair loads latest revision issues, builds RepairContext, and calls the provider under the shared semaphore.

<!-- segment: src/robot_copilot/orchestrator.py Orchestrator.repair -->

```python
    async def repair(self, mission_id: str) -> ChatResponse:
        m = self._store.get_mission(mission_id)
        if m is None:
            raise KeyError(mission_id)
        if m.status == "repair_exhausted" or (
            m.status == "invalid" and m.repair_attempts >= m.max_repairs
        ):
            raise ConflictError(ConflictCode.REPAIR_LIMIT, "Repair limit reached.")
        if m.status != "invalid":
            raise ConflictError(ConflictCode.NOT_REPAIRABLE, "Mission is not repairable.")

        if not self._store.reserve_repair(mission_id, m.revision, m.repair_attempts):
            raise ConflictError(ConflictCode.STALE, "Mission changed; retry.")

        m = self._store.get_mission(mission_id)
        assert m is not None
        rev_row = self._store.get_latest_revision(mission_id)
        prev_plan = json.loads(rev_row.plan_json) if rev_row and rev_row.plan_json else None
        report = json.loads(rev_row.report_json) if rev_row and rev_row.report_json else {}
        issues = [
            IssueBrief(code=i["code"], action_index=i.get("action_index"), message=i["message"])
            for i in report.get("issues", [])
        ]
        repair_ctx = RepairContext(
            attempt=m.repair_attempts,
            previous_plan=prev_plan,
            issues=issues,
        )
        chat_req = ChatRequest(
            conversation_id=m.conversation_id,
            message=m.user_message,
            vehicle=m.vehicle,  # type: ignore[arg-type]
            battery_pct=m.battery_pct,
        )
        try:
            result = await self._call_provider(chat_req, repair_ctx)
        except ProviderError as exc:
            async with self._lock(m.conversation_id):
                self._finish_repair_error(mission_id, exc)
            return ChatResponse(
                conversation_id=m.conversation_id,
                kind="error",
                assistant_message="The AI provider is unavailable; no plan was created.",
                mission=self.get_mission(mission_id),
            )

        async with self._lock(m.conversation_id):
            return self._commit_repair(m, result)
```

ProviderError paths finish via commit_repair_failure so attempts are not silently lost.

2. Store.commit_repair_failure updates mission status to invalid or repair_exhausted while persisting audit metadata.

<!-- segment: src/robot_copilot/store.py Store.commit_repair_failure -->

```python
    def commit_repair_failure(
        self,
        mission_id: str,
        rev: int,
        attempts: int,
        generation: int,
        status: str,
        detail: dict[str, Any],
    ) -> bool:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            conv = session.get(Conversation, m.conversation_id if m else "")
            if (
                m is None
                or conv is None
                or conv.generation != generation
                or m.status != "repairing"
                or m.revision != rev
                or m.repair_attempts != attempts
            ):
                return False
            m.status = status
            session.add(m)
            self._audit(session, mission_id, "provider_error", detail)
            session.commit()
            return True
```

Generation counters ensure repairs do not resurrect missions from superseded conversations.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync pytest tests/unit/test_settings.py::test_mock_default -q --no-header
```

### Expected

```
1 passed
```

## Exercise

Read provider_concurrency in config/app.toml and confirm tests/unit/test_settings.py pins it to four.

## Checkpoint

- `tests/api/test_repair_provider_error.py::test_repair_provider_error_unsticks_mission`
