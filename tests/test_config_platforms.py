"""Tests for config/platforms.py and data-integrity checks across
config/platforms.json + config/countries.json + collectors/registry.py.

The integrity checks matter because these two JSON files are hand-edited
(see countries.json's history — GE/AM/AZ/KZ/... added incrementally across
sessions) with nothing structural stopping a typo'd platform id from
silently breaking country resolution.
"""

import json
from pathlib import Path

import pytest

from collectors.registry import COLLECTORS
from config.platforms import get_platforms_for_country, get_unverified_platforms

_CONFIG_DIR = Path(__file__).parents[1] / "config"
_PLATFORM_IDS = {p["id"] for p in json.loads((_CONFIG_DIR / "platforms.json").read_text())["platforms"]}
_COUNTRIES = json.loads((_CONFIG_DIR / "countries.json").read_text())


# --- get_platforms_for_country -------------------------------------------

def test_known_country_returns_universal_plus_regional_platforms():
    plan = get_platforms_for_country("GE")
    ids = {p["id"] for p in plan}
    assert {"google_maps", "tripadvisor", "facebook", "instagram", "google_news"} <= ids
    assert "yandex_maps" in ids  # GE's extra_maps_reviews entry
    assert "wolt" in ids         # GE's delivery entry


def test_country_code_is_case_insensitive():
    assert get_platforms_for_country("ge") == get_platforms_for_country("GE")


def test_unknown_country_raises_keyerror():
    with pytest.raises(KeyError):
        get_platforms_for_country("ZZ")


def test_universal_platforms_are_marked_confirmed():
    plan = get_platforms_for_country("GE")
    universal = {p["id"]: p for p in plan if p["id"] in _COUNTRIES["_universal_platforms"]}
    assert all(p["confidence"] == "confirmed" for p in universal.values())


def test_regional_platform_confidence_matches_country_config():
    plan = get_platforms_for_country("AM")
    by_id = {p["id"]: p for p in plan}
    # AM's countries.json entry marks yandex_maps as needs_verification
    assert by_id["yandex_maps"]["confidence"] == "needs_verification"
    # ...and glovo as confirmed
    assert by_id["glovo"]["confidence"] == "confirmed"


def test_get_unverified_platforms_filters_correctly():
    unverified = get_unverified_platforms("AM")
    plan = get_platforms_for_country("AM")
    expected = {p["name"] for p in plan if p["confidence"] == "needs_verification"}
    assert set(unverified) == expected
    assert len(unverified) > 0  # AM has known needs_verification entries — sanity check the fixture assumption


def test_country_with_no_extra_platforms_still_gets_universal_set():
    # TM has empty extra_maps_reviews/delivery in countries.json
    plan = get_platforms_for_country("TM")
    ids = {p["id"] for p in plan}
    assert ids == set(_COUNTRIES["_universal_platforms"])


# --- data integrity: countries.json <-> platforms.json <-> registry.py ---

def test_every_universal_platform_id_exists_in_platforms_json():
    missing = set(_COUNTRIES["_universal_platforms"]) - _PLATFORM_IDS
    assert not missing, f"_universal_platforms references unknown platform ids: {missing}"


def test_every_country_referenced_platform_id_exists_in_platforms_json():
    referenced = set()
    for country in _COUNTRIES["countries"].values():
        for entry in country.get("extra_maps_reviews", []) + country.get("delivery", []):
            referenced.add(entry["platform"])
    missing = referenced - _PLATFORM_IDS
    assert not missing, f"countries.json references platform ids missing from platforms.json: {missing}"


def test_every_platform_in_platforms_json_has_a_registered_collector():
    # Every platform ever gets *some* collector (even a deliberate
    # "not implemented" placeholder — see bolt_food.py/facebook.py/etc.),
    # so a country's report is always honest about what it tried, not
    # silently missing a whole platform because nobody wired it up.
    missing = _PLATFORM_IDS - set(COLLECTORS.keys())
    assert not missing, f"platforms.json has ids with no collectors.registry.py entry: {missing}"


def test_every_country_has_a_valid_region():
    valid_regions = {"caucasus", "central_asia", "western_europe", "eastern_europe"}
    for code, country in _COUNTRIES["countries"].items():
        assert country["region"] in valid_regions, f"{code} has unexpected region {country['region']!r}"


def test_every_country_entry_has_a_two_letter_code():
    for code in _COUNTRIES["countries"]:
        assert len(code) == 2 and code.isupper(), f"country code {code!r} is not a 2-letter uppercase ISO code"
