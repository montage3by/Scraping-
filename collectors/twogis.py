"""2GIS collector — via the official Catalog API (documented REST API,
no browser needed). Requires TWOGIS_API_KEY.

Honest limitation: confident about org search + rating via
/3.0/items?q=...&key=... (matches config/platforms.json's api_notes).
Less confident about pulling full review *text* through this same API —
2GIS's public docs for review-text retrieval weren't something I could
verify without live access. This collector returns rating-only Mentions
(text left as a placeholder noting the limitation) rather than guessing
an endpoint shape that might not exist. If full review text turns out to
need browser scraping instead, that's a separate collector, not a fix to
this one.
"""

import asyncio
import json
import os
import urllib.parse
import urllib.request

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention

API_BASE = "https://catalog.api.2gis.com/3.0/items"


class TwoGisCollector(PlatformCollector):
    platform_id = "2gis"

    async def collect(
        self,
        browser: Browser,  # unused — pure API collector for the rating; see module docstring
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        api_key = os.environ.get("TWOGIS_API_KEY")
        if not api_key:
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=[], success=False, error="TWOGIS_API_KEY not configured",
            )
        try:
            mentions = await asyncio.to_thread(self._fetch, restaurant_name, city, api_key)
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=mentions, success=True,
            )
        except Exception as exc:  # noqa: BLE001
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=[], success=False, error=f"{type(exc).__name__}: {exc}",
            )

    def _fetch(self, restaurant_name: str, city: str, api_key: str) -> list[Mention]:
        params = urllib.parse.urlencode({
            "q": f"{restaurant_name} {city}",
            "fields": "items.reviews,items.point",
            "key": api_key,
        })
        req = urllib.request.Request(f"{API_BASE}?{params}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        items = data.get("result", {}).get("items", [])
        if not items:
            return []

        item = items[0]
        reviews_meta = item.get("reviews", {})
        rating = reviews_meta.get("general_rating")
        count = reviews_meta.get("general_review_count")

        if rating is None:
            return []

        # Single aggregate Mention, not per-review text — see module docstring.
        return [Mention(
            platform=self.platform_id,
            text=f"Aggregate rating from {count or '?'} reviews (2GIS Catalog API does not expose review text here)",
            rating=float(rating),
            author="",
        )]


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await TwoGisCollector().collect(None, "Picasso", "Almaty", "KZ")
        print(f"success={result.success} error={result.error}")
        for m in result.mentions:
            print(f"  [{m.rating}] {m.text}")

    asyncio.run(_manual_test())
