"""Yandex Maps collector — via the official Geosearch API (org search,
documented REST API, no browser needed). Requires YANDEX_API_KEY.

IMPORTANT license constraint, found earlier in this project and designed
around here rather than ignored: the Geosearch API's standard license
forbids storing raw results long-term. So this collector deliberately
only extracts the aggregate rating, never review text — there isn't any
in the API response anyway (Geosearch returns org metadata, not reviews),
but even the org name/address returned here should be treated as
transient (used to compute the report, not persisted verbatim into a
database) if this product needs to keep a long-term history later. See
config/platforms.json's api_notes for the same note.

Free tier: up to 500 requests/day, per config/platforms.json.
"""

import asyncio
import json
import os
import urllib.parse
import urllib.request

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention

API_BASE = "https://search-maps.yandex.ru/v1/"


class YandexMapsCollector(PlatformCollector):
    platform_id = "yandex_maps"

    async def collect(
        self,
        browser: Browser,  # unused — pure API collector; see module docstring
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        api_key = os.environ.get("YANDEX_API_KEY")
        if not api_key:
            return CollectionResult(
                platform=self.platform_id, restaurant_name=restaurant_name, country=country,
                mentions=[], success=False, error="YANDEX_API_KEY not configured",
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
            "text": f"{restaurant_name} {city}",
            "type": "biz",
            "apikey": api_key,
            "results": 1,
        })
        req = urllib.request.Request(f"{API_BASE}?{params}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        features = data.get("features", [])
        if not features:
            return []

        props = features[0].get("properties", {}).get("CompanyMetaData", {})
        rating_info = props.get("Rating", {})  # not present on every org
        rating = rating_info.get("value")

        if rating is None:
            return []

        return [Mention(
            platform=self.platform_id,
            text=f"Aggregate rating (Yandex Geosearch does not return review text)",
            rating=float(rating),
            author="",
        )]


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await YandexMapsCollector().collect(None, "Picasso", "Tbilisi", "GE")
        print(f"success={result.success} error={result.error}")
        for m in result.mentions:
            print(f"  [{m.rating}] {m.text}")

    asyncio.run(_manual_test())
