from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from robot_copilot.store import Mission, Run, Store
from tests.conftest import CounterIds, FakeClock


def _store(tmp_path) -> Store:
    db = tmp_path / "s.db"
    return Store.from_url(f"sqlite:///{db}", FakeClock(), CounterIds())


def test_cas_commit_chat_stale(tmp_path):
    st = _store(tmp_path)
    conv = st.create_conversation()
    st.add_message_and_bump_generation(conv.id, "user", "hi")
    ok = st.commit_chat_result(
        conversation_id=conv.id,
        generation=0,
        assistant_message="hi",
        mission=None,
        revision=None,
        events=[],
    )
    assert ok is False


def test_unique_run_per_mission(tmp_path):
    st = _store(tmp_path)
    conv = st.create_conversation()
    m = Mission(
        id="m1",
        conversation_id=conv.id,
        generation=1,
        vehicle="drone",
        battery_pct=100,
        user_message="x",
        status="valid",
        repair_attempts=0,
        max_repairs=2,
        revision=1,
        plan_hash="abc",
        validated_at=datetime.now(tz=UTC).isoformat(),
    )
    with Session(st._engine) as session:
        session.add(m)
        session.commit()
    run1 = Run(
        id="r1",
        mission_id="m1",
        plan_hash="abc",
        status="executed",
        frames_json="[]",
        photos_json="[]",
        final_state_json='{"x_m":0,"y_m":0,"alt_m":0,"battery_wh":1,"landed":true,"at_home":true}',
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    run2 = Run(
        id="r2",
        mission_id="m1",
        plan_hash="abc",
        status="executed",
        frames_json="[]",
        photos_json="[]",
        final_state_json='{"x_m":0,"y_m":0,"alt_m":0,"battery_wh":1,"landed":true,"at_home":true}',
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    with Session(st._engine) as session:
        session.add(run1)
        session.commit()
    with pytest.raises(IntegrityError), Session(st._engine) as session:
        session.add(run2)
        session.commit()


def test_naive_datetime_rejected(tmp_path):
    from robot_copilot.store import _require_aware

    with pytest.raises(ValueError, match="naive"):
        _require_aware(datetime(2020, 1, 1))


def test_busy_timeout_pragma(tmp_path):
    st = _store(tmp_path)
    with Session(st._engine) as session:
        row = session.connection().exec_driver_sql("PRAGMA busy_timeout").fetchone()
    assert row is not None and int(row[0]) >= 5000


def test_store_roundtrip(tmp_path):
    st = _store(tmp_path)
    conv = st.create_conversation()
    assert conv.id.startswith("id")
