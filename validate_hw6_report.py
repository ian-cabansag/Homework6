"""Offline, source-reconciled browser checks for the standalone Problem 9 report."""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from build_hw6_report import ROOT, build_report_data


REPORT = ROOT / "output" / "hw6_report.html"
REQUIRED_SECTIONS = {"economics", "attack-surface", "protection", "exam", "decision"}


def main() -> None:
    html = REPORT.read_text(encoding="utf-8")
    match = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise AssertionError("Embedded report data block is missing.")
    embedded = json.loads(match.group(1))
    if embedded != build_report_data():
        raise AssertionError("Embedded report values no longer match source JSON records.")
    if re.search(r"https?://", html, re.I):
        raise AssertionError("Unexpected remote URL in standalone report source.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, offline=True)
        page = context.new_page()
        errors: list[str] = []
        remote_requests: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: remote_requests.append(request.url) if request.url.startswith(("http:", "https:")) else None)
        page.goto(REPORT.resolve().as_uri(), wait_until="load")

        sections = set(page.locator("main section[id]").evaluate_all("nodes => nodes.map(n => n.id)"))
        if sections != REQUIRED_SECTIONS:
            raise AssertionError(f"Unexpected chapter anchors: {sections}")
        if page.locator("#cache-bars .bar-row").count() != 12:
            raise AssertionError("Expected twelve per-document cache chart rows.")
        if page.locator("#exam-tbody tr").count() != 10:
            raise AssertionError("Expected ten exam table entries.")
        if page.locator("#redteam-cards article").count() != 2:
            raise AssertionError("Expected two red-team experiment cards.")
        if page.locator("link[href], img[src], script[src], iframe[src]").count():
            raise AssertionError("Report contains an external or separately-hosted asset reference.")

        page.get_by_role("button", name="No reuse").click()
        if not page.locator("#cache-bars .cached-line").first.is_hidden() or page.locator("#cache-bars .uncached-line").first.is_hidden():
            raise AssertionError("No-reuse chart filter did not update both series.")
        page.get_by_role("button", name="Cached", exact=True).click()
        if page.locator("#cache-bars .cached-line").first.is_hidden() or not page.locator("#cache-bars .uncached-line").first.is_hidden():
            raise AssertionError("Cached chart filter did not update both series.")
        page.get_by_role("button", name="Both").click()
        if page.locator("#cache-bars .cached-line").first.is_hidden() or page.locator("#cache-bars .uncached-line").first.is_hidden():
            raise AssertionError("Combined chart filter did not restore both series.")

        widths: dict[int, int] = {}
        for width, height in ((1440, 1000), (390, 844), (320, 740)):
            page.set_viewport_size({"width": width, "height": height})
            widths[width] = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if widths[width] > 1:
                offenders = page.evaluate(
                    "Array.from(document.getElementsByTagName('*')).filter(e => !e.closest('.table-wrap') && !e.closest('.chapter-nav .inner')).map(e => [e.tagName, String(e.className), (e.textContent||'').slice(0,25), Math.round(e.getBoundingClientRect().left), Math.round(e.getBoundingClientRect().right), Math.round(e.getBoundingClientRect().width), e.parentElement?.tagName, Math.round(e.parentElement?.getBoundingClientRect().left||0), Math.round(e.parentElement?.getBoundingClientRect().width||0)]).filter(x => x[4] > innerWidth + 1 && x[5] > 0).sort((a,b) => b[4]-a[4]).slice(0,12)"
                )
                raise AssertionError(f"Horizontal overflow at {width}px ({widths[width]}px): {offenders}")
        if errors:
            raise AssertionError(f"Browser runtime errors: {errors}")
        if remote_requests:
            raise AssertionError(f"Unexpected online requests: {remote_requests}")

        print(f"Source values match embedded JSON; chapters={len(sections)}, cache rows=12, exam rows=10, red-team experiments=2.")
        print(f"Offline browser checks passed; external references=0, external requests=0, page errors=0, viewport overflow={widths}.")
        browser.close()


if __name__ == "__main__":
    main()
