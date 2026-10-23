"""Capture README screenshots against a running local server."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
BASE = "http://127.0.0.1:8765"


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
        page.screenshot(path=str(OUT / "01-plan.png"), full_page=True)

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
        page.wait_for_function(
            f"() => document.querySelector('{status}')?.textContent === 'valid'"
        )
        page.wait_for_selector('[data-testid="plan-summary"]')
        page.wait_for_function(
            "() => document.querySelector('[data-testid=\"plan-summary\"]')"
            "?.textContent.includes('1 of 4 loops')"
        )
        page.screenshot(path=str(OUT / "02-repair.png"), full_page=True)

        page.click("#confirm-btn")
        page.wait_for_selector("#confirm-dialog")
        page.click("#execute-btn")
        page.wait_for_function(
            "() => document.querySelector('[data-testid=\"mission-status\"]')"
            "?.textContent === 'executed'"
        )
        page.click("#end-btn")
        page.wait_for_selector('[data-testid="playback-status"]')
        page.screenshot(path=str(OUT / "03-executing.png"), full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
