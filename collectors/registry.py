"""Maps a platform id (from config/platforms.json) to the collector class
that knows how to scrape it. Platforms with no entry here don't have a
collector built yet — the worker reports that honestly instead of
pretending to have collected something.
"""

from collectors.base import PlatformCollector
from collectors.bolt_food import BoltFoodCollector
from collectors.chocofood import ChocofoodCollector
from collectors.deliveroo import DeliverooCollector
from collectors.facebook import FacebookCollector
from collectors.glovo import GlovoCollector
from collectors.google_maps import GoogleMapsCollector
from collectors.google_news import GoogleNewsCollector
from collectors.instagram import InstagramCollector
from collectors.thefork import TheForkCollector
from collectors.tripadvisor import TripadvisorCollector
from collectors.twogis import TwoGisCollector
from collectors.uber_eats import UberEatsCollector
from collectors.wolt import WoltCollector
from collectors.yandex_eda import YandexEdaCollector
from collectors.yandex_maps_api import YandexMapsCollector
from collectors.yelp import YelpCollector

COLLECTORS: dict[str, type[PlatformCollector]] = {
    "google_maps": GoogleMapsCollector,
    "google_news": GoogleNewsCollector,
    "tripadvisor": TripadvisorCollector,
    "yelp": YelpCollector,
    "2gis": TwoGisCollector,
    "yandex_maps": YandexMapsCollector,
    "wolt": WoltCollector,
    "glovo": GlovoCollector,
    "uber_eats": UberEatsCollector,
    "deliveroo": DeliverooCollector,
    "thefork": TheForkCollector,
    "bolt_food": BoltFoodCollector,
    "yandex_eda": YandexEdaCollector,
    "chocofood": ChocofoodCollector,
    "facebook": FacebookCollector,
    "instagram": InstagramCollector,
    # Every platform in config/platforms.json now has a registered
    # collector. That does NOT mean every collector is verified working —
    # several (yelp/2gis/yandex_maps) fail cleanly without an API key,
    # several (wolt/glovo/uber_eats/deliveroo/thefork) are unverified
    # browser scaffolds, and several (bolt_food/yandex_eda/chocofood/
    # facebook/instagram) deliberately return success=False with a
    # "not implemented" error rather than guess selectors. The worker
    # already handles all of these as normal per-platform failures.
}


def get_collector(platform_id: str) -> PlatformCollector | None:
    cls = COLLECTORS.get(platform_id)
    return cls() if cls else None
