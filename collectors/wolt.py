"""Wolt collector — browser-based, no reliable public API found.

CONFIDENCE: medium-low. Wolt's public web client uses URLs like
wolt.com/en/{country}/{city}/restaurant/{slug} — the search flow and
exact review-section selectors below are a best-effort guess based on
general knowledge of the site, NOT verified against the live app (this
sandbox blocks outbound network to essentially everything, see the other
collectors' docstrings). Treat this file as a stronger-than-empty
starting point, not a working scraper: run
`python -m collectors.wolt` on the real server FIRST, expect to rework
the selectors, and only then trust its output.
"""

import asyncio
import re

from playwright.async_api import Browser, Page

from collectors._browser_common import human_pause, url_query
from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention

SEARCH_URL = "https://wolt.com/en/search"


class WoltCollector(PlatformCollector):
    platform_id = "wolt"

    async def collect(
        self,
        browser: Browser,
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        page = await browser.new_page(locale="en-US")
        try:
            mentions = await self._collect(page, restaurant_name, city, max_reviews)
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=mentions, success=True,
            )
        except Exception as exc:  # noqa: BLE001
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=[], success=False, error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            await page.close()

    async def _collect(self, page: Page, restaurant_name: str, city: str, max_reviews: int) -> list[Mention]:
        query = url_query(f"{restaurant_name} {city}")
        await page.goto(f"{SEARCH_URL}?q={query}", timeout=30_000)
        await human_pause(1.5, 3.0)

        # TODO(verify on real server): confirm this is actually the result
        # link pattern — restaurant pages are typically /restaurant/{slug}.
        result_link = page.locator('a[href*="/restaurant/"]').first
        if await result_link.count() == 0:
            return []
        await result_link.click()
        await human_pause()

        # TODO(verify): Wolt's restaurant page may not expose a review-text
        # list at all in the consumer web app (rating badge is common,
        # per-review text less certain to be public) — confirm before
        # assuming this selector exists.
        for _ in range(3):
            await page.mouse.wheel(0, 1400)
            await human_pause(1.0, 2.0)

        review_cards = page.locator('[data-test-id*="review"]')
        count = min(await review_cards.count(), max_reviews)

        mentions: list[Mention] = []
        for i in range(count):
            card = review_cards.nth(i)
            text = (await card.inner_text()).strip()
            rating = None
            match = re.search(r"([\d.]+)\s*/\s*5|([\d.]+)\s*star", text, re.I)
            if match:
                rating = float(match.group(1) or match.group(2))
            if text:
                mentions.append(Mention(platform=self.platform_id, text=text, rating=rating))

        return mentions


if __name__ == "__main__":
    from playwright.async_api import async_playwright

    async def _manual_test() -> None:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            result = await WoltCollector().collect(browser, "Picasso", "Tbilisi", "GE")
            print(f"success={result.success} error={result.error}")
            for m in result.mentions:
                print(f"  [{m.rating}] {m.text[:80]}")
            await browser.close()

    asyncio.run(_manual_test())
