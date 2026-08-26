"""Yandex Eda (Яндекс Еда) collector — no confirmed public reviews surface.

CONFIDENCE: low, same tier as bolt_food.py. Yandex Eda's restaurant
ratings may actually be sourced from / shared with Yandex Maps org data
rather than living on a separate reviewable page — unconfirmed. Given the
project's earlier finding that Yandex data has real licensing/storage
constraints (see collectors/yandex_maps_api.py), this platform also needs
a legal check on top of a technical one before writing real selectors.
Also: Yandex Eda is Russia/CIS-focused, which cuts against this project's
explicit non-Russia market focus — low priority to build out further.
"""

import asyncio

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult


class YandexEdaCollector(PlatformCollector):
    platform_id = "yandex_eda"

    async def collect(
        self,
        browser: Browser,
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        # Deliberately not attempting a real request — see module
        # docstring. Needs research on (a) whether a separate reviewable
        # surface exists at all, and (b) the same licensing check already
        # done for yandex_maps_api.py, before writing selectors.
        return CollectionResult(
            platform=self.platform_id,
            restaurant_name=restaurant_name,
            country=country,
            mentions=[],
            success=False,
            error="not implemented — needs research: confirm whether Yandex Eda exposes reviews separately from Yandex Maps, and check licensing terms",
        )


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await YandexEdaCollector().collect(None, "Picasso", "Almaty", "KZ")
        print(f"success={result.success} error={result.error}")

    asyncio.run(_manual_test())
