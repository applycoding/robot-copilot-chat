from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_patrol_repair_shows_adjustment_notice(page, base_url):
    page.goto(base_url)
    page.locator('[data-testid="battery-input"]').fill("40")
    page.locator('[data-testid="chat-input"]').fill("patrol the perimeter four times")
    page.locator('[data-testid="send-btn"]').click()
    status = page.locator('[data-testid="mission-status"]')
    expect(status).to_have_text("invalid", timeout=15_000)

    page.locator('[data-testid="repair-btn"]').click()
    expect(status).to_have_text("invalid", timeout=15_000)
    notice = page.locator('[data-testid="adjustment-notice"]')
    expect(notice).to_be_visible()
    expect(notice).to_contain_text("shortened", ignore_case=True)

    page.locator('[data-testid="repair-btn"]').click()
    expect(status).to_have_text("valid", timeout=15_000)
    expect(page.locator('[data-testid="plan-summary"]')).to_contain_text("1 of 4 loops")

    page.locator('[data-testid="confirm-btn"]').click()
    summary = page.locator('[data-testid="confirm-summary"]')
    expect(summary).to_contain_text("shortened", ignore_case=True)
    expect(summary).to_contain_text("Wh", timeout=5_000)
