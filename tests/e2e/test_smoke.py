from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_smoke_flow(page, base_url):
    page.goto(base_url)
    page.locator('[data-testid="chat-input"]').fill("inspect the north fence")
    page.locator('[data-testid="send-btn"]').click()
    status = page.locator('[data-testid="mission-status"]')
    expect(status).to_have_text("valid", timeout=15_000)
    plan_path = page.locator('[data-testid="plan-path"]')
    d_attr = plan_path.get_attribute("d") or ""
    assert len(d_attr.strip()) > 5

    page.locator('[data-testid="confirm-btn"]').click()
    dialog = page.locator('[data-testid="confirm-dialog"]')
    expect(dialog).to_be_visible()
    summary = page.locator('[data-testid="confirm-summary"]')
    expect(summary).to_contain_text("north fence", ignore_case=True)

    page.locator('[data-testid="execute-btn"]').click()
    expect(status).to_contain_text("executed", timeout=15_000)
    playback = page.locator('[data-testid="playback-status"]')
    expect(playback).to_have_attribute("data-status", "idle")
    exec_path = page.locator('[data-testid="exec-path"]')
    expect(exec_path).to_have_attribute("d", "")
    telemetry = page.locator('[data-testid="telemetry"]')
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
