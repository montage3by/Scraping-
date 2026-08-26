"""Finds nearby competing restaurants automatically — the free-MVP quiz only
asks for the user's own restaurant (name + city + country + email), there's
no field for the user to type in competitors themselves. So "compare to
competitors" has to mean auto-discovery, not user input.

Deliberately lightweight: pulls name + rating straight from the Google Maps
search results list (visible without opening each place), not a full
collector run per competitor. Running the whole multi-platform pipeline
against 2-3 competitors too would multiply report time well past the
~10-15 min budget — see report/analysis.py's competitor section, which is
a simple rating comparison, not deep sentiment analysis of competitors'
reviews.

Same caveat as every other collector in this project: untested against the
live page (this sandbox blocks google.com/maps — see google_maps.py's
docstring). Search-results-list scraping is a different DOM area than a
single place's review pane, so this needs its own selector verification on
the real server, not just reuse of google_maps.py's.
"""

import asyncio
import re

from playwright.async_api import Browser

from collectors._browser_common import human_pause, url_query
from collectors.models import Competitor

SEARCH_URL = "https://www.google.com/maps/search/"


def _looks_like_same_restaurant(candidate_name: str, target_name: str) -> bool:
    """Crude dedup so the target restaurant doesn't show up as its own
    "competitor" — normalize case/whitespace and check substring overlap
    rather than requiring an exact match (Maps often appends branch info,
    e.g. "Picasso - Tbilisi Old Town")."""
    a = candidate_name.strip().lower()
    b = target_name.strip().lower()
    return a == b or a in b or b in a


async def _find_named_competitor(browser: Browser, name: str, city: str) -> Competitor | None:
    """Looks up one specific competitor by name — used when the user filled
    in the optional "какой конкурент вас интересует" quiz field. Same
    search-and-take-first-result approach as google_maps.py, so it carries
    the same "might match the wrong branch for a common name" caveat."""
    page = await browser.new_page(locale="en-US")
    try:
        await page.goto(f"{SEARCH_URL}{url_query(f'{name} {city}')}", timeout=30_000)
        await human_pause(1.5, 3.0)

        card = page.locator('a[href*="/maps/place/"]').first
        if await card.count() == 0:
            return None

        label = ((await card.get_attribute("aria-label")) or "").strip()
        url = (await card.get_attribute("href")) or ""
        if not label:
            return None
        return Competitor(name=label, source_url=url)
    except Exception:  # noqa: BLE001 — enrichment only
        return None
    finally:
        await page.close()


async def discover_competitors(
    browser: Browser,
    restaurant_name: str,
    city: str,
    max_competitors: int = 2,
    competitor_hint: str | None = None,
) -> list[Competitor]:
    """Returns up to max_competitors nearby restaurants, excluding the
    target itself. Returns an empty list on any failure — this is a
    best-effort enrichment, not a required part of the report (see
    build_report()'s handling of an empty competitors list).

    competitor_hint: the optional quiz field — a specific competitor name
    the user typed in. When present, it's looked up first and takes one of
    the max_competitors slots; the rest are still auto-discovered, so a
    hint narrows the search but doesn't replace it (the user isn't required
    to know every nearby competitor, just optionally point at one)."""
    competitors: list[Competitor] = []

    if competitor_hint:
        named = await _find_named_competitor(browser, competitor_hint, city)
        if named and not _looks_like_same_restaurant(named.name, restaurant_name):
            competitors.append(named)

    remaining_slots = max_competitors - len(competitors)
    if remaining_slots <= 0:
        return competitors

    page = await browser.new_page(locale="en-US")
    try:
        # Generic "restaurants near <city>" rather than matching the target's
        # cuisine — we don't reliably know the cuisine type without an extra
        # lookup, and a generic query still surfaces genuinely nearby competitors.
        query = url_query(f"restaurants {city}")
        await page.goto(f"{SEARCH_URL}{query}", timeout=30_000)
        await human_pause(1.5, 3.0)

        # Search results render as a scrollable feed of place cards, each an
        # <a href=".../maps/place/..."> with the name and rating in nearby
        # aria-labels — same general shape as the reviews list in
        # google_maps.py, different feed.
        for _ in range(2):
            feed = page.locator('div[role="feed"]').first
            if await feed.count() == 0:
                break
            await feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            await human_pause(1.0, 2.0)

        cards = page.locator('a[href*="/maps/place/"]')
        total = await cards.count()

        already_have = {c.name.strip().lower() for c in competitors}
        for i in range(total):
            if len(competitors) >= max_competitors:
                break

            card = cards.nth(i)
            name = (await card.get_attribute("aria-label")) or ""
            name = name.strip()
            if (
                not name
                or _looks_like_same_restaurant(name, restaurant_name)
                or name.lower() in already_have
            ):
                continue

            url = (await card.get_attribute("href")) or ""

            # Rating usually sits in a sibling element with an aria-label
            # like "4.5 stars" near the same card — best-effort only, a
            # missing rating still keeps the competitor (name-only compare).
            rating = None
            rating_el = card.locator('xpath=following::span[contains(@aria-label, "star")][1]')
            if await rating_el.count() > 0:
                label = (await rating_el.get_attribute("aria-label")) or ""
                match = re.search(r"([\d.]+)\s*star", label)
                if match:
                    rating = float(match.group(1))

            competitors.append(Competitor(name=name, rating=rating, source_url=url))

        return competitors

    except Exception:  # noqa: BLE001 — enrichment only, never break the main report over this
        # Keep whatever we already had (e.g. the hint-based lookup, if that
        # part succeeded) rather than discarding it just because the
        # generic-discovery pass failed afterward.
        return competitors
    finally:
        await page.close()


if __name__ == "__main__":
    from playwright.async_api import async_playwright

    async def _manual_test() -> None:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            competitors = await discover_competitors(browser, "Picasso", "Kazan")
            print(f"Found {len(competitors)} competitors:")
            for c in competitors:
                print(f"  {c.name} — {c.rating} ({c.source_url})")
            await browser.close()

    asyncio.run(_manual_test())
