"""Google News collector — pulls the RSS feed for "{restaurant} {city}",
no browser, no API key.

NOTE: like google_maps.py, this hasn't run against the live feed — this
sandbox's network proxy blocks news.google.com outright too (confirmed via
curl — 403 on the CONNECT tunnel, same as every other collector target).
RSS is a much more stable target than scraped HTML DOM though, so this is
lower-risk than the browser collectors even unverified. Run
`python -m collectors.google_news` on the real server first to confirm.
"""

import asyncio
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from playwright.async_api import Browser

from collectors.base import PlatformCollector
from collectors.models import CollectionResult, Mention

RSS_URL = "https://news.google.com/rss/search"
USER_AGENT = "Mozilla/5.0 (compatible; RepasBot/1.0; +https://repas.example)"


class GoogleNewsCollector(PlatformCollector):
    platform_id = "google_news"

    async def collect(
        self,
        browser: Browser,  # unused — no browser needed for RSS, kept for interface consistency
        restaurant_name: str,
        city: str,
        country: str,
        max_reviews: int = 5,
    ) -> CollectionResult:
        try:
            mentions = await asyncio.to_thread(self._fetch, restaurant_name, city, max_reviews)
            return CollectionResult(
                platform=self.platform_id,
                restaurant_name=restaurant_name,
                country=country,
                mentions=mentions,
                success=True,
            )
        except Exception as exc:  # noqa: BLE001 — a broken source must not kill the whole report
            return CollectionResult(
                platform=self.platform_id,
                restaurant_name=restaurant_name,
                country=country,
                mentions=[],
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _fetch(self, restaurant_name: str, city: str, max_reviews: int) -> list[Mention]:
        query = urllib.parse.quote(f'"{restaurant_name}" {city}')
        url = f"{RSS_URL}?q={query}&hl=en-US&gl=US&ceid=US:en"

        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()

        root = ET.fromstring(raw)
        items = root.findall("./channel/item")[:max_reviews]

        mentions = []
        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            source = item.findtext("source") or ""
            pub_date_raw = item.findtext("pubDate")

            published_at: datetime | None = None
            if pub_date_raw:
                try:
                    published_at = parsedate_to_datetime(pub_date_raw)
                except (TypeError, ValueError):
                    pass  # some feeds send malformed dates — skip rather than guess

            if title:
                mentions.append(Mention(
                    platform=self.platform_id,
                    text=title,
                    author=source,
                    url=link,
                    published_at=published_at,
                ))

        return mentions


if __name__ == "__main__":
    async def _manual_test() -> None:
        result = await GoogleNewsCollector().collect(None, "Picasso restaurant", "Kazan", "RU")
        print(f"success={result.success} error={result.error}")
        for m in result.mentions:
            print(f"  {m.published_at} [{m.author}] {m.text} -> {m.url}")

    asyncio.run(_manual_test())
