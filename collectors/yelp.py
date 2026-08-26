"""Yelp collector — via the official Yelp Fusion API (documented REST API,
no browser needed). Requires YELP_API_KEY.

Real, documented limitation worth knowing before relying on this: Yelp
Fusion's free tier only returns up to 3 reviews per business via
/v3/businesses/{id}/reviews — it is not a way to pull a business's full
review history. Fine as one MVP source among several, not a complete
picture on its own.

Same "written but never run against the live API" caveat as this
project's other collectors — this sandbox has no YELP_API_KEY configured
and blocks most outbound network anyway. Verify against a real key on
the server.
"""

import asyncio
import json
import os
import urllib.parse
import urllib.request

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention

API_BASE = "https://api.yelp.com/v3"


class YelpCollector(PlatformCollector):
    platform_id = "yelp"

    async def collect(
        self,
        browser: Browser,  # unused — pure API collector, no browser needed
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        api_key = os.environ.get("YELP_API_KEY")
        if not api_key:
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=[], success=False, error="YELP_API_KEY not configured",
            )
        try:
            mentions = await asyncio.to_thread(self._fetch, restaurant_name, city, api_key, max_reviews)
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=mentions, success=True,
            )
        except Exception as exc:  # noqa: BLE001
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=[], success=False, error=f"{type(exc).__name__}: {exc}",
            )

    def _fetch(self, restaurant_name: str, city: str, api_key: str, max_reviews: int) -> list[Mention]:
        headers = {"Authorization": f"Bearer {api_key}"}

        search_params = urllib.parse.urlencode({"term": restaurant_name, "location": city, "limit": 1})
        search_req = urllib.request.Request(f"{API_BASE}/businesses/search?{search_params}", headers=headers)
        with urllib.request.urlopen(search_req, timeout=15) as resp:
            businesses = json.loads(resp.read())["businesses"]

        if not businesses:
            return []
        business_id = businesses[0]["id"]

        reviews_req = urllib.request.Request(f"{API_BASE}/businesses/{business_id}/reviews", headers=headers)
        with urllib.request.urlopen(reviews_req, timeout=15) as resp:
            reviews = json.loads(resp.read())["reviews"]

        mentions = []
        for r in reviews[:max_reviews]:
            mentions.append(Mention(
                platform=self.platform_id,
                text=r.get("text", ""),
                rating=r.get("rating"),
                author=r.get("user", {}).get("name", ""),
                url=r.get("url", ""),
            ))
        return mentions


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await YelpCollector().collect(None, "Picasso", "Kazan", "RU")
        print(f"success={result.success} error={result.error}")
        for m in result.mentions:
            print(f"  [{m.rating}] {m.author}: {m.text[:80]}")

    asyncio.run(_manual_test())
