"""Shared helpers for Playwright-based collectors — was duplicated across
google_maps.py, tripadvisor.py, and competitor_discovery.py; centralized
here once a 4th copy was about to happen.
"""

import asyncio
import random
import urllib.parse


async def human_pause(min_s: float = 0.8, max_s: float = 2.2) -> None:
    """Randomized delay between browser actions — see the project-wide
    discussion on why fixed-interval scripted timing is what gets flagged
    by anti-bot systems."""
    await asyncio.sleep(random.uniform(min_s, max_s))


def url_query(text: str) -> str:
    """URL-encodes a search term before it's spliced into a target site's
    URL. Every collector builds its search URL from restaurant_name/city —
    both come straight from the public quiz form — so this must run on
    that text before it touches an f-string. Without it: spaces produce
    malformed paths, '&'/'#' silently truncate or inject extra query
    params into the target site's own request, and non-ASCII text (very
    common for this product's markets — Cyrillic, Georgian, Armenian
    restaurant names) doesn't get encoded at all. google_news.py already
    did this correctly via urllib.parse.quote(); this centralizes the same
    fix for every browser-based collector."""
    return urllib.parse.quote(text)
