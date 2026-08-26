"""Unit tests for report/analysis.py — sentiment scoring, alert thresholds,
competitor comparison, and ordering guarantees (reputation before competitors).

Pure logic, no network/browser — runs anywhere, including this sandbox.
"""

from collectors.models import CollectionResult, Competitor, Mention
from report.analysis import (
    _has_crisis_keyword,
    _score_sentiment,
    build_report,
    render_text_summary,
    to_json_dict,
)


def _result(platform: str, mentions: list[Mention], success: bool = True, error: str | None = None) -> CollectionResult:
    return CollectionResult(platform=platform, restaurant_name="Test", country="GE", mentions=mentions, success=success, error=error)


def _mention(text: str, rating: float | None = None, platform: str = "google_maps") -> Mention:
    return Mention(platform=platform, text=text, rating=rating)


# --- _score_sentiment -------------------------------------------------

def test_score_sentiment_positive_english():
    assert _score_sentiment("The food was great and the staff was friendly") == 1


def test_score_sentiment_negative_english():
    assert _score_sentiment("Terrible service, food was cold and overpriced") == -1


def test_score_sentiment_positive_russian():
    assert _score_sentiment("Очень вкусно и уютно, всем рекомендую") == 1


def test_score_sentiment_negative_russian():
    assert _score_sentiment("Грязно, хамство, ужасно медленно") == -1


def test_score_sentiment_neutral_no_keywords():
    assert _score_sentiment("We visited on a Tuesday evening") == 0


def test_score_sentiment_mixed_ties_to_neutral():
    # one positive + one negative word -> tie -> neutral
    assert _score_sentiment("great food but terrible service") == 0


def test_score_sentiment_case_insensitive():
    assert _score_sentiment("GREAT FOOD") == 1


def test_score_sentiment_georgian_low_confidence_words_still_match():
    # documented low-confidence set, but should still score if present
    assert _score_sentiment("კარგი რესტორანი") == 1


# --- _has_crisis_keyword -----------------------------------------------

def test_crisis_keyword_english():
    assert _has_crisis_keyword("Got food poisoning after eating here") is True


def test_crisis_keyword_russian():
    assert _has_crisis_keyword("Массовое отравление, был суд") is True


def test_crisis_keyword_absent():
    assert _has_crisis_keyword("The soup was a bit cold") is False


# --- build_report: percentages and basic shape --------------------------

def test_build_report_empty_results_no_crash():
    report = build_report([], restaurant_name="Test", city="Tbilisi", country="GE")
    assert report.total_mentions == 0
    assert report.positive_pct == 0.0
    assert report.negative_pct == 0.0
    assert report.neutral_pct == 0.0
    assert report.alerts == []
    assert report.own_avg_rating is None
    assert report.competitors == []


def test_build_report_percentages_sum_correctly():
    mentions = [
        _mention("great amazing food", rating=5),
        _mention("terrible awful service", rating=1),
        _mention("we ate lunch here", rating=3),
    ]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE")
    assert report.total_mentions == 3
    assert report.positive_pct == round(1 / 3 * 100, 1)
    assert report.negative_pct == round(1 / 3 * 100, 1)
    assert report.neutral_pct == round(1 / 3 * 100, 1)


def test_build_report_sources_ok_and_failed():
    ok = _result("google_maps", [_mention("great food")])
    failed = _result("tripadvisor", [], success=False, error="ERR_CONNECTION_RESET")
    report = build_report([ok, failed], "Test", "Tbilisi", "GE")
    assert report.sources_ok == ["google_maps"]
    assert report.sources_failed == ["tripadvisor"]


def test_build_report_own_avg_rating_computed_from_rated_mentions_only():
    mentions = [
        _mention("great", rating=5),
        _mention("bad", rating=1),
        _mention("no rating here", rating=None),
    ]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE")
    assert report.own_avg_rating == 3.0


# --- build_report: alert thresholds -------------------------------------

def test_build_report_no_alert_below_25pct_negative():
    mentions = [_mention("great food")] * 3 + [_mention("terrible food")]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE")
    assert not any("threshold" in a.message or "watching" in a.message for a in report.alerts)


def test_build_report_warning_alert_between_25_and_40pct_negative():
    # 1/3 negative = 33% -> warning tier
    mentions = [_mention("great food"), _mention("great food again"), _mention("terrible food")]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE")
    warning = [a for a in report.alerts if a.level == "warning" and "trending up" in a.message]
    assert len(warning) == 1


def test_build_report_crisis_alert_above_40pct_negative():
    mentions = [_mention("terrible food"), _mention("awful service"), _mention("neutral text")]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE")
    crisis = [a for a in report.alerts if a.level == "crisis" and "40% threshold" in a.message]
    assert len(crisis) == 1


def test_build_report_crisis_keyword_alert_independent_of_ratio():
    # Only 1 of 5 mentions is negative-scored by keyword, but it's a crisis
    # keyword — should still raise a crisis alert regardless of the ratio.
    mentions = [_mention("great food")] * 4 + [_mention("we got food poisoning")]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE")
    crisis = [a for a in report.alerts if a.level == "crisis" and "crisis-related keywords" in a.message]
    assert len(crisis) == 1


def test_build_report_failed_sources_alert():
    ok = _result("google_maps", [_mention("great food")])
    failed = _result("tripadvisor", [], success=False, error="blocked")
    report = build_report([ok, failed], "Test", "Tbilisi", "GE")
    assert any("Could not collect from" in a.message and "tripadvisor" in a.message for a in report.alerts)


# --- build_report: competitor alert (ordering + threshold) --------------

def test_build_report_competitor_alert_appended_last():
    mentions = [_mention("terrible food", rating=1), _mention("awful service", rating=1), _mention("bad again", rating=1)]
    competitors = [Competitor(name="Rival", rating=4.8)]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE", competitors=competitors)
    # crisis-ratio alert should exist AND come before the competitor alert
    assert report.alerts[-1].message.startswith("Rival rated")
    assert any(a.level == "crisis" for a in report.alerts[:-1])


def test_build_report_no_competitor_alert_below_threshold():
    mentions = [_mention("great food", rating=4.5)]
    competitors = [Competitor(name="Rival", rating=4.7)]  # delta 0.2 < 0.3 threshold
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE", competitors=competitors)
    assert not any("Rival" in a.message for a in report.alerts)


def test_build_report_competitor_alert_at_exact_threshold():
    mentions = [_mention("great food", rating=4.0)]
    competitors = [Competitor(name="Rival", rating=4.3)]  # delta exactly 0.3
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE", competitors=competitors)
    assert any("Rival" in a.message for a in report.alerts)


def test_build_report_no_competitor_alert_when_own_rating_unknown():
    mentions = [_mention("no rating text")]  # no rated mentions -> own_avg_rating is None
    competitors = [Competitor(name="Rival", rating=4.9)]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE", competitors=competitors)
    assert report.own_avg_rating is None
    assert not any("Rival" in a.message for a in report.alerts)


def test_build_report_competitor_alert_picks_best_rated_competitor():
    mentions = [_mention("food", rating=4.0)]
    competitors = [
        Competitor(name="Weak", rating=4.1),
        Competitor(name="Strong", rating=4.9),
        Competitor(name="NoRating", rating=None),
    ]
    report = build_report([_result("google_maps", mentions)], "Test", "Tbilisi", "GE", competitors=competitors)
    assert any("Strong rated 4.9" in a.message for a in report.alerts)
    assert not any("Weak" in a.message for a in report.alerts)


# --- render_text_summary / to_json_dict: ordering ------------------------

def test_render_text_summary_competitors_section_comes_after_sources_failed():
    ok = _result("google_maps", [_mention("great food", rating=4.5)])
    failed = _result("tripadvisor", [], success=False, error="blocked")
    competitors = [Competitor(name="Rival", rating=4.9)]
    report = build_report([ok, failed], "Test", "Tbilisi", "GE", competitors=competitors)
    text = render_text_summary(report)
    failed_idx = text.index("Не удалось собрать")
    competitors_idx = text.index("Конкуренты поблизости")
    assert failed_idx < competitors_idx


def test_render_text_summary_no_competitors_section_when_empty():
    report = build_report([_result("google_maps", [_mention("great food")])], "Test", "Tbilisi", "GE")
    text = render_text_summary(report)
    assert "Конкуренты" not in text


def test_to_json_dict_competitors_key_is_last():
    competitors = [Competitor(name="Rival", rating=4.9, source_url="https://example.com")]
    report = build_report([_result("google_maps", [_mention("great food", rating=4.5)])], "Test", "Tbilisi", "GE", competitors=competitors)
    d = to_json_dict(report)
    keys = list(d.keys())
    assert keys[-1] == "competitors"
    assert d["competitors"] == [{"name": "Rival", "rating": 4.9, "source_url": "https://example.com"}]


def test_to_json_dict_own_avg_rating_present():
    report = build_report([_result("google_maps", [_mention("great food", rating=4.5)])], "Test", "Tbilisi", "GE")
    d = to_json_dict(report)
    assert d["own_avg_rating"] == 4.5
