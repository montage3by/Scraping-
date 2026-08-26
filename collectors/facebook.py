"""Facebook Page reviews/recommendations collector — HIGH RISK, scaffold
only.

CONFIDENCE: low, and deliberately treated as higher-risk than the
delivery-app scaffolds. Per config/platforms.json this platform is
flagged risk="high" and per this project's own plan it should run last,
only after the other collectors are stable ("Facebook — самая агрессивная
защита. Запускать только после стабилизации остальных"). Facebook is
known for aggressive anti-automation (login walls, behavioral detection,
rate limiting) and scraping Page content may also raise ToS concerns
beyond the purely technical ones every other collector in this project
has. This file intentionally does NOT attempt a real request — it exists
to hold the platform_id and document why it's stubbed, not as a draft
selector implementation.
"""

import asyncio

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult


class FacebookCollector(PlatformCollector):
    platform_id = "facebook"

    async def collect(
        self,
        browser: Browser,
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        # Deliberately not attempting a real request. Needs a deliberate
        # decision (not just selector research) on whether unauthenticated
        # scraping of a public Page's reviews/recommendations is viable at
        # all before writing code, since Facebook is the most aggressive
        # anti-automation surface this project touches.
        return CollectionResult(
            platform=self.platform_id,
            restaurant_name=restaurant_name,
            country=country,
            mentions=[],
            success=False,
            error="not implemented — deliberately deferred: highest anti-automation risk, needs explicit go/no-go before any selector work",
        )


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await FacebookCollector().collect(None, "Picasso", "Tbilisi", "GE")
        print(f"success={result.success} error={result.error}")

    asyncio.run(_manual_test())
