"""TheFork (La Fourchette) collector — browser-based, no reliable public
consumer API found (per config/platforms.json — a restaurant-partner API
exists but requires a partnership, not applicable here).

CONFIDENCE: medium-low, same caveat as this project's other browser
scaffolds — URL/selector guesses, not verified live.
"""

import asyncio
import re

from playwright.async_api import Browser, Page

from collectors._browser_common import human_pause
from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention

SEARCH_URL = "https://www.thefork.com/search"


class TheForkCollector(PlatformCollector):
    platform_id = "thefork"

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
        query = f"{restaurant_name} {city}"
        await page.goto(f"{SEARCH_URL}?query={query}", timeout=30_000)
        await human_pause(1.5, 3.0)

        result_link = page.locator('a[href*="/restaurant/"]').first
        if await result_link.count() == 0:
            return []
        await result_link.click()
        await human_pause()

        # TheFork reviews are typically on their own tab, not the landing view.
        reviews_tab = page.get_by_role("tab", name=re.compile("review", re.I))
        if await reviews_tab.count() > 0:
            await reviews_tab.click()
            await human_pause()

        for _ in range(3):
            await page.mouse.wheel(0, 1400)
            await human_pause(1.0, 2.0)

        review_cards = page.locator('[data-test*="review"], [class*="review-item"]')
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
            result = await TheForkCollector().collect(browser, "Picasso", "Paris", "FR")
            print(f"success={result.success} error={result.error}")
            for m in result.mentions:
                print(f"  [{m.rating}] {m.text[:80]}")
            await browser.close()

    asyncio.run(_manual_test())
