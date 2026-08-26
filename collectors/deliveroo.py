"""Deliveroo collector — browser-based, no reliable public API found.

CONFIDENCE: medium-low, same caveat as wolt.py/glovo.py/uber_eats.py.
Deliveroo's domain varies by country (deliveroo.co.uk, deliveroo.fr, ...);
this uses the UK domain as a default starting point — country-specific
TLD selection isn't implemented yet and would need to be before this is
trustworthy outside the UK. Verify on the real server.
"""

import asyncio
import re

from playwright.async_api import Browser, Page

from collectors._browser_common import human_pause
from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention

SEARCH_URL = "https://deliveroo.co.uk/restaurants"


class DeliverooCollector(PlatformCollector):
    platform_id = "deliveroo"

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
        # TODO(verify on real server + fix): needs a per-country domain map
        # (deliveroo.co.uk / .fr / .ie / etc) keyed off the restaurant's
        # country — hardcoded to .co.uk here is wrong for non-UK requests.
        query = f"{restaurant_name} {city}"
        await page.goto(f"{SEARCH_URL}/{city}?q={query}", timeout=30_000)
        await human_pause(1.5, 3.0)

        result_link = page.locator('a[href*="/menu/"]').first
        if await result_link.count() == 0:
            return []
        await result_link.click()
        await human_pause()

        for _ in range(3):
            await page.mouse.wheel(0, 1400)
            await human_pause(1.0, 2.0)

        review_cards = page.locator('[data-testid*="review"], [class*="review"]')
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
            result = await DeliverooCollector().collect(browser, "Picasso", "London", "GB")
            print(f"success={result.success} error={result.error}")
            for m in result.mentions:
                print(f"  [{m.rating}] {m.text[:80]}")
            await browser.close()

    asyncio.run(_manual_test())
