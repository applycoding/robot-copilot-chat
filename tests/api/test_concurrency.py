from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, wait

from sqlmodel import Session, select

from robot_copilot.llm.mock import MockProvider
from robot_copilot.store import Run
from tests.conftest import make_client
from tests.fakes.providers import GatedOnRepairProvider, GatedProvider, PairedGatedProvider


def _wait_enter(event: threading.Event, timeout: float = 3.0) -> None:
    assert event.wait(timeout), "provider did not start in time"


def test_repair_repair_single_provider(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        gated.release.clear()
        gated.enter.clear()

        def do_repair():
            return client.post(f"/api/missions/{mid}/repair", json={})

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(do_repair)
            f2 = pool.submit(do_repair)
            _wait_enter(gated.enter)
            gated.release.set()
            res = [f1.result(), f2.result()]
    codes = sorted(x.status_code for x in res)
    assert codes == [200, 409]


def test_repair_chat_discards_repair(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedOnRepairProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        conv = r.json()["conversation_id"]
        gated.release.clear()
        gated.enter.clear()
        repair_done: list = []

        def repair():
            repair_done.append(client.post(f"/api/missions/{mid}/repair", json={}))

        t = threading.Thread(target=repair)
        t.start()
        _wait_enter(gated.enter)
        chat_res = client.post(
            "/api/chat",
            json={"conversation_id": conv, "message": "take a photo of the barn"},
        )
        gated.release.set()
        t.join(timeout=5)
        assert t.is_alive() is False
        repair_res = repair_done[0]
    assert chat_res.status_code == 200
    assert repair_res.status_code == 409
    assert repair_res.json()["detail"]["code"] == "stale"
    assert client.get(f"/api/missions/{mid}").json()["status"] == "superseded"


def test_chat_chat_one_wins(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = PairedGatedProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r0 = client.post("/api/chat", json={"message": "inspect the north fence"})
        conv = r0.json()["conversation_id"]
        gated._release.clear()
        gated.enter.clear()
        gated._barrier = threading.Barrier(2)

        def chat(msg: str):
            return client.post(
                "/api/chat",
                json={"conversation_id": conv, "message": msg},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(chat, "take a photo of the barn")
            f2 = pool.submit(chat, "survey the pond at 150 m")
            _wait_enter(gated.enter)
            gated._release.set()
            res = [f1.result(), f2.result()]
    assert any(x.status_code == 409 for x in res)
    assert sum(1 for x in res if x.status_code == 200) == 1


def test_repair_confirm_not_confirmable_then_hash_mismatch(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        old_hash = r.json()["mission"]["plan_hash"]
        gated.release.clear()
        gated.enter.clear()
        repair_result: list = []

        def repair():
            repair_result.append(client.post(f"/api/missions/{mid}/repair", json={}))

        t = threading.Thread(target=repair)
        t.start()
        _wait_enter(gated.enter)
        during = client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": old_hash})
        assert during.status_code == 409
        assert during.json()["detail"]["code"] == "not_confirmable"
        gated.release.set()
        t.join(timeout=5)
        repair_res = repair_result[0]
        assert repair_res.status_code == 200
        assert repair_res.json()["mission"]["plan_hash"] != old_hash
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
            wait([f1, f2])
            results = [f1.result(), f2.result()]
        ok = [x for x in results if x.status_code == 200]
        assert len(ok) == 1
        store = client.app.state.orchestrator._store
        with Session(store._engine) as session:
            runs = list(session.exec(select(Run)).all())
        assert len(runs) == 1


def test_begin_immediate_during_provider(tmp_path, fake_clock, counter_ids):
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
        chat_result: list = []

        def chat():
            chat_result.append(
                client.post("/api/chat", json={"message": "inspect the north fence"})
            )

        t = threading.Thread(target=chat)
        t.start()
        _wait_enter(gated.enter)
        probe_ok = probe()
        gated.release.set()
        t.join(timeout=5)
        assert chat_result and chat_result[0].status_code == 200
    assert probe_ok
