from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from robot_copilot.redact import redact_obj


def _require_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime rejected")
    return dt.astimezone(UTC)


def _iso(dt: datetime) -> str:
    return _require_aware(dt).isoformat()


class Conversation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    created_at: str
    generation: int = 0


class Message(SQLModel, table=True):
    id: str = Field(primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id")
    role: str
    content: str
    created_at: str


class Mission(SQLModel, table=True):
    id: str = Field(primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id")
    generation: int
    vehicle: str
    battery_pct: int
    user_message: str
    status: str
    repair_attempts: int = 0
    max_repairs: int = 2
    revision: int = 1
    plan_hash: str | None = None
    validated_at: str | None = None


class MissionRevision(SQLModel, table=True):
    id: str = Field(primary_key=True)
    mission_id: str = Field(foreign_key="mission.id")
    revision: int
    attempt: int
    provider: str
    model: str
    result_kind: str
    plan_json: str | None = None
    decline_json: str | None = None
    report_json: str | None = None
    created_at: str


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    mission_id: str = Field(foreign_key="mission.id", unique=True)
    plan_hash: str
    status: str
    frames_json: str
    photos_json: str
    final_state_json: str
    created_at: str


class AuditEvent(SQLModel, table=True):
    id: str = Field(primary_key=True)
    mission_id: str | None = Field(default=None, foreign_key="mission.id")
    kind: str
    detail_json: str
    at: str


def _connect(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


class Store:
    def __init__(
        self,
        engine: Engine,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._id = id_factory
        _connect(engine)

    @classmethod
    def from_url(
        cls, url: str, clock: Callable[[], datetime], id_factory: Callable[[], str]
    ) -> Store:
        engine = create_engine(url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(engine)
        return cls(engine, clock, id_factory)

    def create_conversation(self) -> Conversation:
        with Session(self._engine) as session:
            conv = Conversation(id=self._id(), created_at=_iso(self._clock()), generation=0)
            session.add(conv)
            session.commit()
            session.refresh(conv)
            return conv

    def add_message_and_bump_generation(self, conversation_id: str, role: str, content: str) -> int:
        with Session(self._engine) as session:
            conv = session.get(Conversation, conversation_id)
            if conv is None:
                raise KeyError(conversation_id)
            conv.generation += 1
            g = conv.generation
            session.add(conv)
            session.add(
                Message(
                    id=self._id(),
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    created_at=_iso(self._clock()),
                )
            )
            session.commit()
            return g

    def recent_turns(self, conversation_id: str, limit: int) -> list[tuple[str, str]]:
        with Session(self._engine) as session:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())  # type: ignore[attr-defined]
                .limit(limit)
            )
            msgs = list(session.exec(stmt).all())
            msgs.reverse()
            return [(m.role, m.content) for m in msgs]

    def supersede_open_missions(self, conversation_id: str, generation: int) -> None:
        open_status = {"valid", "invalid", "repairing"}
        with Session(self._engine) as session:
            missions = session.exec(
                select(Mission).where(Mission.conversation_id == conversation_id)
            ).all()
            for m in missions:
                if m.status in open_status:
                    m.status = "superseded"
                    session.add(m)
                    self._audit(session, m.id, "superseded", {})
            session.commit()

    def create_mission_if_generation(
        self,
        *,
        conversation_id: str,
        generation: int,
        mission: Mission,
        revision: MissionRevision,
        events: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        with Session(self._engine) as session:
            conv = session.get(Conversation, conversation_id)
            if conv is None or conv.generation != generation:
                return False
            session.add(mission)
            session.add(revision)
            for kind, detail in events:
                self._audit(session, mission.id, kind, detail)
            session.commit()
            return True

    def reserve_repair(self, mission_id: str, rev: int, attempts: int) -> bool:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            if m is None:
                return False
            if m.status != "invalid" or m.revision != rev or m.repair_attempts != attempts:
                return False
            m.status = "repairing"
            m.revision = rev + 1
            m.repair_attempts = attempts + 1
            session.add(m)
            session.commit()
            return True

    def commit_repair(
        self,
        *,
        mission_id: str,
        generation: int,
        rev: int,
        attempts: int,
        status: str,
        plan_hash: str | None,
        validated_at: datetime | None,
        revision: MissionRevision,
        events: list[tuple[str, dict[str, Any]]],
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
            m.plan_hash = plan_hash
            m.validated_at = _iso(validated_at) if validated_at else None
            session.add(m)
            session.add(revision)
            for kind, detail in events:
                self._audit(session, mission_id, kind, detail)
            session.commit()
            return True

    def commit_chat_result(
        self,
        *,
        conversation_id: str,
        generation: int,
        assistant_message: str | None,
        mission: Mission | None,
        revision: MissionRevision | None,
        events: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        with Session(self._engine) as session:
            conv = session.get(Conversation, conversation_id)
            if conv is None or conv.generation != generation:
                self._audit_stale(session, mission.id if mission else None)
                return False
            if assistant_message:
                session.add(
                    Message(
                        id=self._id(),
                        conversation_id=conversation_id,
                        role="assistant",
                        content=assistant_message,
                        created_at=_iso(self._clock()),
                    )
                )
            if mission and revision:
                session.add(mission)
                session.add(revision)
                for kind, detail in events:
                    self._audit(session, mission.id, kind, detail)
            session.commit()
            return True

    def commit_confirmation(
        self,
        mission_id: str,
        rev: int,
        plan_hash: str,
        validated_not_before: datetime,
        run: Run,
        events: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            if m is None or m.status != "valid" or m.revision != rev or m.plan_hash != plan_hash:
                return False
            if m.validated_at is None:
                return False
            val_at = _require_aware(datetime.fromisoformat(m.validated_at))
            if val_at < _require_aware(validated_not_before):
                return False
            m.status = "executed" if run.status == "executed" else "aborted"
            session.add(m)
            session.add(run)
            for kind, detail in events:
                self._audit(session, mission_id, kind, detail)
            try:
                session.commit()
            except Exception:
                session.rollback()
                return False
            return True

    def audit(self, mission_id: str | None, kind: str, detail: dict[str, Any]) -> None:
        with Session(self._engine) as session:
            self._audit(session, mission_id, kind, detail)
            session.commit()

    def _audit(
        self, session: Session, mission_id: str | None, kind: str, detail: dict[str, Any]
    ) -> None:
        session.add(
            AuditEvent(
                id=self._id(),
                mission_id=mission_id,
                kind=kind,
                detail_json=json.dumps(redact_obj(detail)),
                at=_iso(self._clock()),
            )
        )

    def _audit_stale(self, session: Session, mission_id: str | None) -> None:
        self._audit(session, mission_id, "stale_discarded", {})

    def get_mission(self, mission_id: str) -> Mission | None:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            if m is not None:
                session.expunge(m)
            return m

    def get_latest_revision(self, mission_id: str) -> MissionRevision | None:
        with Session(self._engine) as session:
            revs = session.exec(
                select(MissionRevision)
                .where(MissionRevision.mission_id == mission_id)
                .order_by(MissionRevision.revision.desc())  # type: ignore[attr-defined]
            ).all()
            if not revs:
                return None
            rev = revs[0]
            session.expunge(rev)
            return rev

    def get_run(self, run_id: str) -> Run | None:
        with Session(self._engine) as session:
            return session.get(Run, run_id)

    def get_run_for_mission(self, mission_id: str) -> Run | None:
        with Session(self._engine) as session:
            runs = session.exec(select(Run).where(Run.mission_id == mission_id)).all()
            return runs[0] if runs else None

    def list_audit_events(self) -> list[AuditEvent]:
        with Session(self._engine) as session:
            return list(session.exec(select(AuditEvent).order_by(AuditEvent.at)).all())
