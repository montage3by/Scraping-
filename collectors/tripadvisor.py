"""Tripadvisor collector — finds a restaurant by name+city and pulls its
latest reviews.

NOTE: same caveat as collectors/google_maps.py — this sandbox blocks
www.tripadvisor.com outright (confirmed via curl — 403 on the CONNECT
tunnel earlier in the project), so none of this has run against a live
page. Tripadvisor's DOM uses obfuscated/hashed CSS class names that churn
often (a known pain point for anyone scraping it), so selectors below lean
on more stable anchors where possible: `data-reviewid` on each review card
and `aria-label` for ratings ("X of 5 bubbles") rather than guessing class
names. Still: run `python -m collectors.tripadvisor` on the real server
first and expect to fix selectors against the actual current markup.
"""

import asyncio
import re

from playwright.async_api import Browser, Page

from collectors._browser_common import human_pause
from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention

SEARCH_URL = "https://www.tripadvisor.com/Search"


class TripadvisorCollector(PlatformCollector):
    platform_id = "tripadvisor"

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
                platform=self.platform_id,
                restaurant_name=restaurant_name,
                country=country,
                mentions=mentions,
                success=True,
            )
        except Exception as exc:  # noqa: BLE001 — a broken source must not kill the whole report
            return CollectionResult(
                platform=self.platform_id,
                restaurant_name=restaurant_name,
                country=country,
                mentions=[],
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            await page.close()

    async def _collect(self, page: Page, restaurant_name: str, city: str, max_reviews: int) -> list[Mention]:
        query = f"{restaurant_name} {city}"
        await page.goto(f"{SEARCH_URL}?q={query}", timeout=30_000)
        await human_pause(1.5, 3.0)

        # Search results list restaurants/hotels/attractions together — take
        # the first link that points at a restaurant review page specifically.
        result_link = page.locator('a[href*="/Restaurant_Review-"]').first
        if await result_link.count() > 0:
            await result_link.click()
            await human_pause()
        elif "/Restaurant_Review-" not in page.url:
            # No matching restaurant result at all — nothing further to do.
            return []

        # Reviews aren't always on the landing tab — look for a reviews
        # section/tab and jump to it if present.
        reviews_tab = page.get_by_role("tab", name=re.compile("review", re.I))
        if await reviews_tab.count() > 0:
            await reviews_tab.click()
            await human_pause()

        # Scroll a few times to lazy-load enough reviews.
        for _ in range(4):
            await page.mouse.wheel(0, 1600)
            await human_pause(1.0, 2.0)

        review_cards = page.locator("[data-reviewid]")
        count = min(await review_cards.count(), max_reviews)

        mentions: list[Mention] = []
        for i in range(count):
            card = review_cards.nth(i)

            author = ""
            author_el = card.locator('a[href*="/Profile/"]').first
            if await author_el.count() > 0:
                author = (await author_el.inner_text()).strip()

            rating = None
            rating_el = card.locator('[aria-label*="bubble"], [aria-label*="of 5"]').first
            if await rating_el.count() > 0:
                label = (await rating_el.get_attribute("aria-label")) or ""
                match = re.search(r"([\d.]+)\s*(?:of 5|bubble)", label)
                if match:
                    rating = float(match.group(1))

            text = ""
            text_el = card.locator("q, span[data-test-target='review-body'], .partial_entry").first
            if await text_el.count() > 0:
                text = (await text_el.inner_text()).strip()

            if text:
                mentions.append(Mention(platform=self.platform_id, text=text, rating=rating, author=author))

        return mentions


if __name__ == "__main__":
    from playwright.async_api import async_playwright

    async def _manual_test() -> None:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            result = await TripadvisorCollector().collect(browser, "Picasso restaurant", "Kazan", "RU")
            print(f"success={result.success} error={result.error}")
            for m in result.mentions:
                print(f"  [{m.rating}] {m.author}: {m.text[:80]}")
            await browser.close()

    asyncio.run(_manual_test())
