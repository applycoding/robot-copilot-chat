from __future__ import annotations

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlmodel import Session, select

from robot_copilot.llm.mock import MockProvider
from robot_copilot.store import Run
from tests.conftest import make_client
from tests.fakes.providers import GatedOnRepairProvider, GatedProvider


@pytest.mark.asyncio
async def test_repair_repair_single_provider(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        conv = r.json()["conversation_id"]
        gated.release.clear()
        gated.enter.clear()

        async def do_repair():
            return client.post(f"/api/missions/{mid}/repair", json={})

        t1 = asyncio.create_task(do_repair())
        t2 = asyncio.create_task(do_repair())
        await asyncio.wait_for(gated.enter.wait(), timeout=2)
        assert inner  # provider entered once
        gated.release.set()
        res = await asyncio.gather(t1, t2)
    codes = sorted(x.status_code for x in res)
    assert codes == [200, 409]
    loser = next(x for x in res if x.status_code == 409)
    assert loser.json()["detail"]["code"] in ("not_repairable", "stale")


@pytest.mark.asyncio
async def test_repair_chat_discards_repair(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedOnRepairProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        conv = r.json()["conversation_id"]
        gated.release.clear()
        gated.enter.clear()

        repair_task = asyncio.create_task(
            asyncio.to_thread(lambda: client.post(f"/api/missions/{mid}/repair", json={}))
        )
        await asyncio.wait_for(gated.enter.wait(), timeout=2)
        chat_res = await asyncio.to_thread(
            lambda: client.post(
                "/api/chat",
                json={"conversation_id": conv, "message": "take a photo of the barn"},
            )
        )
        gated.release.set()
        repair_res = await repair_task
    assert chat_res.status_code == 200
    assert chat_res.json().get("mission")
    assert repair_res.status_code == 409
    assert repair_res.json()["detail"]["code"] == "stale"
    m = client.get(f"/api/missions/{mid}").json()
    assert m["status"] == "superseded"


@pytest.mark.asyncio
async def test_chat_chat_one_wins(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r0 = client.post("/api/chat", json={"message": "inspect the north fence"})
        conv = r0.json()["conversation_id"]
        gated.release.clear()
        gated.enter.clear()

        async def chat(msg: str):
            return await asyncio.to_thread(
                lambda: client.post(
                    "/api/chat",
                    json={"conversation_id": conv, "message": msg},
                )
            )

        t1 = asyncio.create_task(chat("take a photo of the barn"))
        t2 = asyncio.create_task(chat("survey the pond at 150 m"))
        await asyncio.wait_for(gated.enter.wait(), timeout=2)
        gated.release.set()
        res = await asyncio.gather(t1, t2)
    assert any(x.status_code == 409 for x in res)
    assert sum(1 for x in res if x.status_code == 200) == 1


@pytest.mark.asyncio
async def test_repair_confirm_not_confirmable_then_hash_mismatch(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        old_hash = r.json()["mission"]["plan_hash"]
        gated.release.clear()
        gated.enter.clear()

        repair_task = asyncio.create_task(
            asyncio.to_thread(lambda: client.post(f"/api/missions/{mid}/repair", json={}))
        )
        await asyncio.wait_for(gated.enter.wait(), timeout=2)
        during = client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": old_hash})
        assert during.status_code == 409
        assert during.json()["detail"]["code"] == "not_confirmable"
        gated.release.set()
        repair_res = await repair_task
        assert repair_res.status_code == 200
        new_hash = repair_res.json()["mission"]["plan_hash"]
        assert new_hash != old_hash
        bad = client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": old_hash})
        assert bad.status_code == 409
        assert bad.json()["detail"]["code"] == "plan_hash_mismatch"


def test_confirm_confirm_single_run(tmp_path, fake_clock, counter_ids):
    client = make_client(tmp_path, fake_clock, counter_ids)
    with client:
        r = client.post("/api/chat", json={"message": "take a photo of the barn"})
        mid = r.json()["mission"]["id"]
        ph = r.json()["mission"]["plan_hash"]

        def confirm():
            return client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": ph})

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(confirm)
            f2 = pool.submit(confirm)
            results = [f1.result(), f2.result()]
        ok = [x for x in results if x.status_code == 200]
        conflict = [x for x in results if x.status_code == 409]
        assert len(ok) == 1
        assert len(conflict) == 1
        store = client.app.state.orchestrator._store
        with Session(store._engine) as session:
            runs = list(session.exec(select(Run)).all())
        assert len(runs) == 1


@pytest.mark.asyncio
async def test_begin_immediate_during_provider(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedProvider(inner)
    db = tmp_path / "c.db"
    client = make_client(
        tmp_path,
        fake_clock,
        counter_ids,
        provider=gated,
        extra_env={"RCC_DB_URL": f"sqlite:///{db}"},
    )

    def probe() -> bool:
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.rollback()
            return True
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()

    with client:
        gated.release.clear()
        gated.enter.clear()
        chat_task = asyncio.create_task(
            asyncio.to_thread(
                lambda: client.post("/api/chat", json={"message": "inspect the north fence"})
            )
        )
        await asyncio.wait_for(gated.enter.wait(), timeout=2)
        probe_ok = await asyncio.to_thread(probe)
        gated.release.set()
        r = await chat_task
        assert r.status_code == 200
    assert probe_ok
