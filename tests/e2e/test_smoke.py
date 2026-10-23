from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_smoke_flow(page, base_url):
    page.goto(base_url)
    page.fill("#chat-input", "inspect the north fence")
    page.click("#send-btn")
    page.wait_for_selector('[data-testid="mission-status"]')
    assert "valid" in page.locator('[data-testid="mission-status"]').inner_text()
    page.click("#confirm-btn")
    page.wait_for_selector("#confirm-dialog")
    assert "north fence" in page.locator("#confirm-summary").inner_text().lower()
    page.click("#execute-btn")
    page.wait_for_selector('[data-testid="mission-status"]')
    page.click("#step-btn")
    page.wait_for_function("() => document.querySelector('[data-frame-index=\"1\"]')")
    page.click("#end-btn")
    page.wait_for_selector('[data-testid="playback-status"]')
    page.screenshot(path="test-results/smoke.png")
