"""Tests for the shared url_query() helper — every browser-based collector
builds a target-site URL from restaurant_name/city, both of which come
straight from the public quiz form. Without encoding, spaces malform the
URL, '&'/'#' can truncate the query or inject extra params into the
target site's own request, and non-ASCII names (Cyrillic, Georgian,
Armenian — this product's actual markets) don't survive at all.
"""

from collectors._browser_common import url_query


def test_spaces_are_encoded():
    assert " " not in url_query("Picasso Tbilisi")


def test_ampersand_is_encoded_not_left_as_a_query_separator():
    encoded = url_query("Bob & Fries")
    assert "&" not in encoded


def test_hash_is_encoded_not_left_as_a_fragment_marker():
    encoded = url_query("Cafe #1")
    assert "#" not in encoded


def test_question_mark_is_encoded():
    encoded = url_query("What?")
    assert "?" not in encoded


def test_cyrillic_restaurant_name_is_encoded():
    encoded = url_query("Кафе Тбилиси")
    assert encoded == "%D0%9A%D0%B0%D1%84%D0%B5%20%D0%A2%D0%B1%D0%B8%D0%BB%D0%B8%D1%81%D0%B8"


def test_georgian_restaurant_name_survives_encoding_round_trip():
    import urllib.parse
    original = "რესტორანი თბილისი"
    encoded = url_query(original)
    assert urllib.parse.unquote(encoded) == original


def test_encoded_query_is_safe_to_splice_into_a_url():
    query = url_query("Bob & Fries #1?")
    url = f"https://example.com/search?q={query}"
    # No unencoded URL-structural characters leaked into the built URL's query value.
    query_value = url.split("q=", 1)[1]
    assert not any(c in query_value for c in " &#?")
