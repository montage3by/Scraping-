"""Common interface every platform collector implements.

Keeping this thin on purpose: the orchestrator only needs to call
`collect()` and get a CollectionResult back — it doesn't care whether the
platform underneath is Google Maps, Tripadvisor, or Wolt.
"""

from abc import ABC, abstractmethod

from playwright.async_api import Browser

from collectors.models import CollectionResult


class PlatformCollector(ABC):
    platform_id: str  # must match an id in config/platforms.json

    @abstractmethod
    async def collect(
        self,
        browser: Browser,
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        """Find the restaurant on this platform and return its latest reviews/mentions.

        Must not raise — catch everything internally and return a
        CollectionResult with success=False + error message. One flaky
        source should never take down the whole report (see the
        orchestrator's per-task timeout/merge logic).
        """
        raise NotImplementedError
