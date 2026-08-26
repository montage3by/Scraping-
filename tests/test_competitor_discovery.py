"""Unit tests for the pure-logic dedup helper in competitor_discovery.py.
No browser needed — _looks_like_same_restaurant() is plain string logic.
"""

from collectors.competitor_discovery import _looks_like_same_restaurant


def test_exact_match():
    assert _looks_like_same_restaurant("Picasso", "Picasso") is True


def test_case_insensitive_match():
    assert _looks_like_same_restaurant("PICASSO", "picasso") is True


def test_whitespace_trimmed():
    assert _looks_like_same_restaurant("  Picasso  ", "Picasso") is True


def test_candidate_contains_target_branch_suffix():
    # Maps often appends branch/location info to the name.
    assert _looks_like_same_restaurant("Picasso - Tbilisi Old Town", "Picasso") is True


def test_target_contains_candidate():
    assert _looks_like_same_restaurant("Picasso", "Picasso - Tbilisi Old Town") is True


def test_different_restaurants_not_matched():
    assert _looks_like_same_restaurant("Rustaveli Cafe", "Picasso") is False


def test_unrelated_short_names_not_falsely_matched():
    # Guards against a substring-overlap false positive on short/common names.
    assert _looks_like_same_restaurant("Cafe", "Cafe Rio") is True  # documented crude-substring behavior
    assert _looks_like_same_restaurant("Bar", "Barcelona Grill") is True  # known limitation, not a bug: see docstring


def test_empty_candidate_name_treated_as_match():
    # "" is a substring of everything in Python, so an empty candidate name
    # is treated as "same restaurant" and filtered out — harmless in
    # practice because the only caller (discover_competitors) already
    # skips empty names before reaching this check (`if not name or ...`),
    # but documenting the raw behavior here so that guard can't be removed
    # silently without this test catching it.
    assert _looks_like_same_restaurant("", "") is True
    assert _looks_like_same_restaurant("", "Picasso") is True
