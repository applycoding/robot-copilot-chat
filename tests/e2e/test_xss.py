from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_xss_inert(page, base_url):
    page.goto(base_url)
    payload = '<img src=x onerror="window.__xss=1">'
    page.fill("#chat-input", payload)
    page.click("#send-btn")
    page.wait_for_timeout(500)
    assert page.evaluate("() => window.__xss") is None
    assert page.locator("#messages img").count() == 0
