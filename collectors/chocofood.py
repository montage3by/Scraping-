"""Chocofood (Kazakhstan/Central Asia delivery) collector — no confirmed
public reviews surface.

CONFIDENCE: low, same tier as bolt_food.py. I don't have solid, current
knowledge of Chocofood's web client URL structure or whether it exposes
per-restaurant reviews at all (vs. just ratings on delivery apps in
general). Treat this as a placeholder for real research once the site can
actually be opened and inspected, not a near-working draft.
"""

import asyncio

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult


class ChocofoodCollector(PlatformCollector):
    platform_id = "chocofood"

    async def collect(
        self,
        browser: Browser,
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        # Deliberately not attempting a real request — see module
        # docstring. Fill in once the real web entry point and DOM are
        # confirmed by opening the site directly, not by guessing.
        return CollectionResult(
            platform=self.platform_id,
            restaurant_name=restaurant_name,
            country=country,
            mentions=[],
            success=False,
            error="not implemented — needs research: confirm Chocofood's public web search URL and whether it exposes reviews at all",
        )


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await ChocofoodCollector().collect(None, "Picasso", "Almaty", "KZ")
        print(f"success={result.success} error={result.error}")

    asyncio.run(_manual_test())
