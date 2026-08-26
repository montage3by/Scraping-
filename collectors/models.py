"""Shared data shapes every platform collector returns, so the report
generator doesn't need to know which platform a mention came from."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Mention:
    platform: str          # matches an id in config/platforms.json, e.g. "google_maps"
    text: str
    rating: Optional[float] = None      # 1-5 stars, None if not applicable (e.g. news article)
    author: str = ""
    url: str = ""
    published_at: Optional[datetime] = None   # None if the site only gives a relative date we couldn't parse
    collected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CollectionResult:
    platform: str
    restaurant_name: str
    country: str
    mentions: list[Mention]
    success: bool
    error: Optional[str] = None   # set when success=False — lets the orchestrator report a partial failure


@dataclass
class Competitor:
    """A nearby restaurant found automatically (not entered by the user —
    the free-MVP quiz only asks for the user's own restaurant). Lightweight
    on purpose: only what's visible in a Maps search result list (name +
    rating), not a full per-competitor scrape — running the whole collector
    pipeline against 2-3 competitors too would blow the ~10-15 min report
    budget. See collectors/competitor_discovery.py."""
    name: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    source_url: str = ""
