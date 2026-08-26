"""Google Maps collector — finds a restaurant by name+city and pulls its
latest reviews straight from the map UI (no Places API key needed).

NOTE: written against Google Maps' current DOM structure, but this sandbox's
network proxy blocks google.com/maps entirely (confirmed via curl — 403 on
the CONNECT tunnel), so none of this has been run against a live page yet.
Treat the selectors below as a first draft: run `python -m collectors.google_maps`
on the real server first and fix whatever breaks before wiring it into the
orchestrator.
"""

import asyncio
import re

from playwright.async_api import Browser, Page

from collectors._browser_common import human_pause, url_query
from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention


class GoogleMapsCollector(PlatformCollector):
    platform_id = "google_maps"

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
        query = url_query(f"{restaurant_name} {city}")
        await page.goto(f"https://www.google.com/maps/search/{query}", timeout=30_000)
        await human_pause(1.5, 3.0)

        # A specific-enough query usually lands directly on the place page.
        # If Maps instead shows a results list, click the first result card.
        first_result = page.locator('a[href*="/maps/place/"]').first
        if await first_result.count() > 0 and "/maps/place/" not in page.url:
            await first_result.click()
            await human_pause()

        # Open the Reviews tab (button text is locale-dependent; en-US -> "Reviews").
        reviews_tab = page.get_by_role("tab", name=re.compile("reviews", re.I))
        if await reviews_tab.count() > 0:
            await reviews_tab.click()
            await human_pause()

        # The reviews list lives in a scrollable pane — scroll it a few times
        # to lazy-load enough reviews to cover max_reviews.
        scroll_container = page.locator('div[role="feed"]').first
        for _ in range(4):
            if await scroll_container.count() == 0:
                break
            await scroll_container.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            await human_pause(1.0, 2.0)

        review_cards = page.locator('div[data-review-id]')
        count = min(await review_cards.count(), max_reviews)

        mentions: list[Mention] = []
        for i in range(count):
            card = review_cards.nth(i)

            author = ""
            author_el = card.locator("button[aria-label]").first
            if await author_el.count() > 0:
                author = (await author_el.get_attribute("aria-label")) or ""

            rating = None
            rating_el = card.locator('span[role="img"][aria-label*="star"]').first
            if await rating_el.count() > 0:
                label = (await rating_el.get_attribute("aria-label")) or ""
                match = re.search(r"([\d.]+)", label)
                if match:
                    rating = float(match.group(1))

            text = ""
            text_el = card.locator('span[class*="review"]').first
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
            result = await GoogleMapsCollector().collect(browser, "Picasso restaurant", "Kazan", "RU")
            print(f"success={result.success} error={result.error}")
            for m in result.mentions:
                print(f"  [{m.rating}] {m.author}: {m.text[:80]}")
            await browser.close()

    asyncio.run(_manual_test())
