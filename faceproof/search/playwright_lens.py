"""Headless Google Lens via Playwright. Free, no API key.

This is a scraper: it drives a real Chromium, uploads the probe crop to
lens.google.com and reads the result list out of the DOM. It is genuine (the
query really goes to Google) but it is also the most fragile provider here --
Google changes that DOM regularly. Treat it as the no-budget fallback, not the
primary path.

Setup:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

from .. import config
from .base import Candidate, SearchProvider

_RESULT_SELECTORS = [
    'a[href^="http"][data-ved]',
    'div[data-ved] a[href^="http"]',
    "a.ngTNl",
]


class PlaywrightLens(SearchProvider):
    name = "playwright_google_lens"
    requires_key = False

    def available(self) -> bool:
        try:
            import playwright.sync_api  # noqa: F401
        except ImportError:
            return False
        return True

    def search(self, image_path: str, limit: int = 25) -> list[Candidate]:
        from playwright.sync_api import sync_playwright

        out: list[Candidate] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.PLAYWRIGHT_HEADLESS)
            ctx = browser.new_context(user_agent=config.USER_AGENT,
                                      viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            try:
                page.goto("https://lens.google.com/upload", wait_until="domcontentloaded",
                          timeout=45_000)
                _dismiss_consent(page)

                # The upload input is often hidden behind the "upload a file" tab.
                page.set_input_files('input[type="file"]', image_path, timeout=30_000)
                page.wait_for_load_state("networkidle", timeout=60_000)
                page.wait_for_timeout(2500)

                anchors = []
                for sel in _RESULT_SELECTORS:
                    anchors = page.query_selector_all(sel)
                    if len(anchors) > 5:
                        break

                seen = set()
                for a in anchors:
                    href = a.get_attribute("href") or ""
                    if (not href.startswith("http")
                            or "google.com" in href
                            or href in seen):
                        continue
                    seen.add(href)
                    img = a.query_selector("img")
                    img_url = (img.get_attribute("src") if img else "") or ""
                    if img_url.startswith("data:"):
                        img_url = ""
                    out.append(Candidate(
                        page_url=href,
                        image_url=img_url,
                        title=(a.inner_text() or "").strip()[:200],
                        provider=self.name,
                        raw={"href": href},
                    ))
                    if len(out) >= limit:
                        break
            finally:
                ctx.close()
                browser.close()

        # candidates with no usable image URL cannot be face-verified
        return [c for c in out if c.image_url]


def _dismiss_consent(page) -> None:
    for text in ("Accept all", "I agree", "Reject all", "Alle akzeptieren"):
        try:
            btn = page.get_by_role("button", name=text)
            if btn.count():
                btn.first.click(timeout=3000)
                page.wait_for_timeout(800)
                return
        except Exception:
            continue
