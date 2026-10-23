from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _assert_svgs_in_viewport(page) -> None:
    ok = page.evaluate(
        """() => {
        const svg = document.getElementById('map-svg');
        if (!svg) return false;
        const vb = svg.viewBox.baseVal;
        const ids = ['plan-path', 'site-layer'];
        for (const id of ids) {
          const el = document.getElementById(id);
          if (!el) return false;
          const bb = el.getBBox();
          if (bb.width === 0 && bb.height === 0) return false;
          if (bb.x < vb.x - 1 || bb.y < vb.y - 1) return false;
          if (bb.x + bb.width > vb.x + vb.width + 1) return false;
          if (bb.y + bb.height > vb.y + vb.height + 1) return false;
        }
        return true;
      }"""
    )
    assert ok


def test_smoke_flow(page, base_url):
    page.goto(base_url)
    expect(page.locator('[data-testid="site-layer"] path').first).to_be_attached(timeout=10_000)
    page.locator('[data-testid="chat-input"]').fill("inspect the north fence")
    page.locator('[data-testid="send-btn"]').click()
    status = page.locator('[data-testid="mission-status"]')
    expect(status).to_have_text("valid", timeout=15_000)
    plan_path = page.locator('[data-testid="plan-path"]')
    d_attr = plan_path.get_attribute("d") or ""
    assert len(d_attr.strip()) > 5
    _assert_svgs_in_viewport(page)

    first_step = page.locator('[data-testid="plan-steps"] li').first.inner_text()
    assert "Take off" in first_step
    assert not re.match(r"^\d+\.", first_step)

    page.locator('[data-testid="confirm-btn"]').click()
    dialog = page.locator('[data-testid="confirm-dialog"]')
    expect(dialog).to_be_visible()
    summary = page.locator('[data-testid="confirm-summary"]')
    expect(summary).to_contain_text("North Fence")

    page.locator('[data-testid="execute-btn"]').click()
    expect(status).to_have_text("executed", timeout=15_000)
    playback = page.locator('[data-testid="playback-status"]')
    expect(playback).to_have_attribute("data-status", "idle")
    exec_path = page.locator('[data-testid="exec-path"]')
    expect(exec_path).to_have_attribute("d", "")
    telemetry = page.locator('[data-testid="telemetry"]')
    expect(telemetry).to_have_attribute("data-frame-index", "0")

    page.locator('[data-testid="play-btn"]').click()
    page.wait_for_function(
        "() => Number(document.getElementById('telemetry')?.dataset.frameIndex || '0') > 0",
        timeout=15_000,
    )
    page.locator('[data-testid="pause-btn"]').click()
    page.locator('[data-testid="reset-btn"]').click()
    expect(telemetry).to_have_attribute("data-frame-index", "0")

    page.locator('[data-testid="step-btn"]').click()
    expect(telemetry).to_have_attribute("data-frame-index", "1")
    exec_d = exec_path.get_attribute("d") or ""
    assert len(exec_d.strip()) > 3
    assert page.locator('[data-testid="vehicle-marker"] circle').count() == 1

    page.locator('[data-testid="end-btn"]').click()
    expect(playback).to_have_attribute("data-status", "completed")
    expect(telemetry).to_contain_text("landed at home")
    page.screenshot(path="test-results/smoke.png")
