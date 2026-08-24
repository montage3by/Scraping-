"""Resolves which platforms to scan for a given restaurant's country.

Usage:
    from config.platforms import get_platforms_for_country

    plan = get_platforms_for_country("GE")
    # -> list[dict] of platform definitions, universal + country-specific,
    #    each tagged with confidence ("confirmed" / "needs_verification")
"""

import json
from pathlib import Path

_DIR = Path(__file__).parent
_PLATFORMS = {p["id"]: p for p in json.loads((_DIR / "platforms.json").read_text())["platforms"]}
_COUNTRIES = json.loads((_DIR / "countries.json").read_text())


def get_platforms_for_country(country_code: str) -> list[dict]:
    """Return the resolved platform list for one country.

    Each item is the full platform definition from platforms.json plus a
    'confidence' field: 'confirmed' for universal/verified entries,
    or whatever the country entry specifies for regional add-ons.
    """
    country_code = country_code.upper()
    country = _COUNTRIES["countries"].get(country_code)
    if country is None:
        raise KeyError(
            f"No platform mapping for country '{country_code}'. "
            f"Add it to config/countries.json first."
        )

    resolved = []

    for platform_id in _COUNTRIES["_universal_platforms"]:
        resolved.append({**_PLATFORMS[platform_id], "confidence": "confirmed"})

    for entry in country.get("extra_maps_reviews", []) + country.get("delivery", []):
        platform = _PLATFORMS[entry["platform"]]
        resolved.append({**platform, "confidence": entry["confidence"]})

    return resolved


def get_unverified_platforms(country_code: str) -> list[str]:
    """Convenience: platform names in this country's plan still needing a manual check."""
    return [p["name"] for p in get_platforms_for_country(country_code) if p["confidence"] == "needs_verification"]


if __name__ == "__main__":
    import sys

    code = sys.argv[1] if len(sys.argv) > 1 else "GE"
    plan = get_platforms_for_country(code)
    print(f"Platforms for {code} ({len(plan)} total):")
    for p in plan:
        flag = " ⚠ needs verification" if p["confidence"] == "needs_verification" else ""
        print(f"  - {p['name']:20s} [{p['category']:12s}] risk={p['risk']}{flag}")
