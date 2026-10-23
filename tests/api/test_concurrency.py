from __future__ import annotations

import asyncio
import sqlite3
import threading

import pytest

from robot_copilot.llm.mock import MockProvider
from tests.conftest import make_client
from tests.fakes.providers import GatedProvider


@pytest.mark.asyncio
async def test_repair_repair_single_provider(tmp_path, fake_clock, counter_ids):
    inner = MockProvider("mock-1")
    gated = GatedProvider(inner)
    client = make_client(tmp_path, fake_clock, counter_ids, provider=gated)
    with client:
        r = client.post("/api/chat", json={"message": "survey the pond at 150 m"})
        mid = r.json()["mission"]["id"]
        gated.release.clear()

        async def do_repair():
            return client.post(f"/api/missions/{mid}/repair", json={})

        t1 = asyncio.create_task(do_repair())
        t2 = asyncio.create_task(do_repair())
        await asyncio.wait_for(gated.enter.wait(), timeout=2)
        gated.release.set()
        res = await asyncio.gather(t1, t2)
    codes = [x.status_code for x in res]
    assert 200 in codes
    assert 409 in codes


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
    probe_ok: list[bool] = []

    def probe():
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.rollback()
            probe_ok.append(True)
        except sqlite3.OperationalError:
            probe_ok.append(False)
        finally:
            conn.close()

    with client:
        gated.release.clear()
        r = client.post("/api/chat", json={"message": "inspect the north fence"})
        assert r.status_code == 200
        threading.Thread(target=probe).start()
        gated.release.set()
    assert probe_ok and probe_ok[0]
