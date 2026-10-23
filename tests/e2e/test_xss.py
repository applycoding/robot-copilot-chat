from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_xss_inert(page, base_url):
    page.goto(base_url)
    for payload in (
        '<img src=x onerror="window.__xss=1">',
        '</script><svg onload="window.__xss=1">',
    ):
        page.locator('[data-testid="chat-input"]').fill(payload)
        page.locator('[data-testid="send-btn"]').click()
        expect(page.locator("#messages")).to_contain_text(payload, timeout=10_000)
    assert page.evaluate("() => window.__xss") is None
    assert page.locator("#messages img").count() == 0
    assert page.locator("#messages svg").count() == 0
