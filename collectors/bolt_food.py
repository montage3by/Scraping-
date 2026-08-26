"""Bolt Food collector — browser-based, no reliable public API found.

CONFIDENCE: low — lower than wolt.py/glovo.py/etc. Bolt Food is more
app-centric than some competitors; I don't have solid confidence in a
public, searchable web client URL structure for it (unlike Wolt, which
has a well-known consumer web app). The URL below is a guess, not even a
best-effort based on real familiarity — treat this file as a placeholder
to fill in once someone actually opens food.bolt.eu (or whatever the
real entry point turns out to be) and inspects it, not as a draft that's
close to working.
"""

import asyncio

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult


class BoltFoodCollector(PlatformCollector):
    platform_id = "bolt_food"

    async def collect(
        self,
        browser: Browser,
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        # Deliberately not attempting a real request yet — see module
        # docstring. Fill this in once the actual web entry point and DOM
        # are confirmed by opening the site directly, not by guessing.
        return CollectionResult(
            platform=self.platform_id,
            restaurant_name=restaurant_name,
            country=country,
            mentions=[],
            success=False,
            error="not implemented — needs research: confirm Bolt Food's public web search URL and review DOM before writing selectors",
        )


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await BoltFoodCollector().collect(None, "Picasso", "Tbilisi", "GE")
        print(f"success={result.success} error={result.error}")

    asyncio.run(_manual_test())
