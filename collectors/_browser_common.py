"""Shared helpers for Playwright-based collectors — was duplicated across
google_maps.py, tripadvisor.py, and competitor_discovery.py; centralized
here once a 4th copy was about to happen.
"""

import asyncio
import random


async def human_pause(min_s: float = 0.8, max_s: float = 2.2) -> None:
    """Randomized delay between browser actions — see the project-wide
    discussion on why fixed-interval scripted timing is what gets flagged
    by anti-bot systems."""
    await asyncio.sleep(random.uniform(min_s, max_s))
