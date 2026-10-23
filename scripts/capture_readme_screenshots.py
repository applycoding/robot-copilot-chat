"""Capture README screenshots against a running local server."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
BASE = "http://127.0.0.1:8765"


def expand_chat_log_for_screenshot(page: Page) -> None:
    """Show the full chat transcript without clipping (capture-only; not app behaviour)."""
    page.evaluate(
        """() => {
        const el = document.getElementById('messages');
        if (!el) return;
        el.style.maxHeight = 'none';
        el.style.overflow = 'visible';
        el.style.height = 'auto';
        el.scrollTop = 0;
        el.style.minHeight = el.scrollHeight + 'px';
        window.scrollTo(0, 0);
    }"""
    )


def screenshot_readme_page(page: Page, path: Path) -> None:
    expand_chat_log_for_screenshot(page)
    page.wait_for_timeout(100)
    expand_chat_log_for_screenshot(page)
    page.wait_for_function(
        "() => { const m = document.getElementById('messages');"
        " return m && m.scrollTop === 0 && window.scrollY === 0; }"
    )
    page.screenshot(path=str(path), full_page=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(BASE)
        page.fill("#battery-input", "100")
        page.fill("#chat-input", "inspect the north fence")
        page.click("#send-btn")
        page.wait_for_function(
            "() => !document.querySelector('[data-testid=\"mission-card\"]')?.hidden"
        )
        page.wait_for_function(
            "() => document.querySelector('[data-testid=\"mission-status\"]')"
            "?.textContent === 'valid'"
        )
        screenshot_readme_page(page, OUT / "01-plan.png")

        page.fill("#battery-input", "40")
        page.fill("#chat-input", "patrol the perimeter four times")
        page.click("#send-btn")
        status = '[data-testid="mission-status"]'
        page.wait_for_function(
            f"() => document.querySelector('{status}')?.textContent === 'invalid'"
        )
        page.click("#repair-btn")
        page.wait_for_function(
            f"() => document.querySelector('{status}')?.textContent === 'invalid'"
        )
        page.click("#repair-btn")
        page.wait_for_function(f"() => document.querySelector('{status}')?.textContent === 'valid'")
        page.wait_for_selector('[data-testid="plan-summary"]')
        page.wait_for_function(
            "() => document.querySelector('[data-testid=\"plan-summary\"]')"
            "?.textContent.includes('1 of 4 loops')"
        )
        screenshot_readme_page(page, OUT / "02-repair.png")

        page.click("#confirm-btn")
        page.wait_for_selector("#confirm-dialog")
        page.click("#execute-btn")
        page.wait_for_function(
            "() => document.querySelector('[data-testid=\"mission-status\"]')"
            "?.textContent === 'executed'"
        )
        page.click("#end-btn")
        page.wait_for_selector('[data-testid="playback-status"]')
        screenshot_readme_page(page, OUT / "03-executing.png")
        browser.close()


if __name__ == "__main__":
    main()
