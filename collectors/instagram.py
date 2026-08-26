"""Instagram (comments on tagged/location posts) collector — HIGH RISK,
scaffold only.

CONFIDENCE: low, same tier as facebook.py. Instagram has no native
"reviews" concept — the closest signal would be comments on posts tagged
at the restaurant's location, which is a much weaker and noisier signal
than a star-rated review, on top of the same aggressive anti-automation
posture as Facebook (same parent company). Per this project's plan this
should run last, only after other collectors are stable. This file
intentionally does NOT attempt a real request.
"""

import asyncio

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult


class InstagramCollector(PlatformCollector):
    platform_id = "instagram"

    async def collect(
        self,
        browser: Browser,
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        # Deliberately not attempting a real request. Needs a decision on
        # whether location-tagged post comments are even a usable proxy
        # for reviews before any selector work — this is a weaker signal
        # than a star rating, not just a harder scrape.
        return CollectionResult(
            platform=self.platform_id,
            restaurant_name=restaurant_name,
            country=country,
            mentions=[],
            success=False,
            error="not implemented — deliberately deferred: highest anti-automation risk + no native review concept, needs explicit go/no-go",
        )


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await InstagramCollector().collect(None, "Picasso", "Tbilisi", "GE")
        print(f"success={result.success} error={result.error}")

    asyncio.run(_manual_test())
