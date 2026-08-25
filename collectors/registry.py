"""Maps a platform id (from config/platforms.json) to the collector class
that knows how to scrape it. Platforms with no entry here don't have a
collector built yet — the worker reports that honestly instead of
pretending to have collected something.
"""

from collectors.base import PlatformCollector
from collectors.google_maps import GoogleMapsCollector
from collectors.google_news import GoogleNewsCollector

COLLECTORS: dict[str, type[PlatformCollector]] = {
    "google_maps": GoogleMapsCollector,
    "google_news": GoogleNewsCollector,
    # tripadvisor, wolt, glovo, 2gis, yandex_maps, facebook, ... — not built yet.
    # Add each here as its collector lands; the worker already handles the
    # "not implemented" case for anything missing from this dict.
}


def get_collector(platform_id: str) -> PlatformCollector | None:
    cls = COLLECTORS.get(platform_id)
    return cls() if cls else None
