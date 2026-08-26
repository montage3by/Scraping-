"""Turns a list of CollectionResult (raw mentions from all platforms) into
the structured data the docx report builder renders.

Deliberately simple keyword-based sentiment for the MVP — good enough to
flag alerts and sort mentions; swap for an LLM-based pass later if the
keyword approach proves too coarse on real data.

Matching is language-agnostic on purpose: a mention's language isn't
detected, every known word (any language) is checked against the text.
That's fine for keyword matching (no need to know which language a review
is in before checking it) and keeps this simple — just keep the per-language
sets honest about confidence, see the Georgian note below.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from collectors.models import CollectionResult, Competitor, Mention

# Keyed by language so it's obvious what's covered and what isn't — flatten
# into POSITIVE_WORDS/NEGATIVE_WORDS/CRISIS_WORDS below rather than scoring
# per-language (matching doesn't need to know which language a review is in).
_SENTIMENT_BY_LANGUAGE = {
    "en": {
        "positive": {
            "great", "excellent", "amazing", "delicious", "friendly", "perfect",
            "love", "best", "recommend", "wonderful", "fantastic", "cozy", "fresh",
        },
        "negative": {
            "bad", "terrible", "awful", "worst", "poor", "disappointing", "slow",
            "rude", "cold", "overpriced", "dirty", "poisoning", "sick",
        },
    },
    "ru": {
        # High confidence — Russian is a priority language for this product
        # (widely used across Caucasus/Central Asia business audiences, not
        # just literally Russia).
        "positive": {
            "отлично", "прекрасно", "прекрасный", "вкусно", "вкусный",
            "дружелюбный", "уютно", "уютный", "рекомендую", "лучший",
            "супер", "великолепно", "чисто", "быстро",
        },
        "negative": {
            "плохо", "ужасно", "отвратительно", "грубый", "хамство",
            "холодный", "дорого", "грязно", "медленно", "долго ждали",
            "испортил", "отравление", "тошнота", "невкусно",
        },
    },
    "ka": {
        # LOW CONFIDENCE — only the handful of words I'm genuinely sure of.
        # Needs a native Georgian speaker's review before this is trusted at
        # the same level as en/ru. Do not extend this list by guessing.
        "positive": {"კარგი", "გემრიელი", "საუკეთესო"},
        "negative": set(),
    },
    # Armenian, Kazakh, Uzbek: deliberately not included yet — didn't have
    # enough confidence in exact review-relevant vocabulary to avoid
    # shipping wrong words in a script I can't proofread reliably myself.
    # Add a new "hy"/"kk"/"uz" entry here once reviewed by a speaker,
    # following the same {"positive": {...}, "negative": {...}} shape.
}

POSITIVE_WORDS: set[str] = {w for lang in _SENTIMENT_BY_LANGUAGE.values() for w in lang["positive"]}
NEGATIVE_WORDS: set[str] = {w for lang in _SENTIMENT_BY_LANGUAGE.values() for w in lang["negative"]}

CRISIS_WORDS = {
    "poisoning", "sick", "hygiene", "lawsuit", "health inspector", "roach", "vomit",
    "отравление", "тошнота", "антисанитария", "таракан", "суд", "роспотребнадзор",
}


@dataclass
class Alert:
    level: str  # "warning" | "crisis"
    message: str


@dataclass
class ReportData:
    restaurant_name: str
    city: str
    country: str
    generated_at: str
    total_mentions: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    platform_breakdown: dict[str, int]
    alerts: list[Alert]
    top_positive: list[Mention]
    top_negative: list[Mention]
    sources_ok: list[str]
    sources_failed: list[str]  # platform names that errored — see CollectionResult.success
    own_avg_rating: Optional[float]  # None if no rated mentions were collected
    competitors: list[Competitor]    # second-class citizen by design — see build_report(); always
                                      # rendered after the reputation section, never before it


def _score_sentiment(text: str) -> int:
    """+1 positive / -1 negative / 0 neutral, based on keyword hits."""
    lowered = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in lowered)
    neg = sum(1 for w in NEGATIVE_WORDS if w in lowered)
    if pos > neg:
        return 1
    if neg > pos:
        return -1
    return 0


def _has_crisis_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(w in lowered for w in CRISIS_WORDS)


def build_report(
    results: list[CollectionResult],
    restaurant_name: str,
    city: str,
    country: str,
    competitors: list[Competitor] | None = None,
) -> ReportData:
    competitors = competitors or []
    all_mentions: list[Mention] = []
    platform_breakdown: Counter = Counter()
    sources_ok, sources_failed = [], []

    for result in results:
        if result.success:
            sources_ok.append(result.platform)
            all_mentions.extend(result.mentions)
            platform_breakdown[result.platform] = len(result.mentions)
        else:
            sources_failed.append(result.platform)

    scored = [(_score_sentiment(m.text), m) for m in all_mentions]
    pos = [m for s, m in scored if s > 0]
    neg = [m for s, m in scored if s < 0]
    neu = [m for s, m in scored if s == 0]
    total = len(all_mentions) or 1  # avoid div-by-zero when a report has no mentions at all

    alerts: list[Alert] = []
    negative_ratio = len(neg) / total
    if negative_ratio > 0.4:
        alerts.append(Alert("crisis", f"Negative mentions at {negative_ratio*100:.0f}% — above the 40% threshold"))
    elif negative_ratio > 0.25:
        alerts.append(Alert("warning", f"Negative mentions at {negative_ratio*100:.0f}% — trending up, worth watching"))

    crisis_mentions = [m for m in all_mentions if _has_crisis_keyword(m.text)]
    if crisis_mentions:
        alerts.append(Alert("crisis", f"{len(crisis_mentions)} mention(s) contain crisis-related keywords (health/safety)"))

    if sources_failed:
        alerts.append(Alert("warning", f"Could not collect from: {', '.join(sources_failed)} — report is based on partial data"))

    rated_mentions = [m for m in all_mentions if m.rating is not None]
    own_avg_rating = round(sum(m.rating for m in rated_mentions) / len(rated_mentions), 2) if rated_mentions else None

    # Competitor alerts are appended last on purpose — reputation alerts
    # (negative ratio, crisis keywords, failed sources) always take priority
    # in the list, matching "сначала анализ репутации, потом конкурентов".
    if own_avg_rating is not None:
        rated_competitors = [c for c in competitors if c.rating is not None]
        if rated_competitors:
            best_competitor = max(rated_competitors, key=lambda c: c.rating)
            # round() guards against float dust at the boundary (e.g.
            # 4.3 - 4.0 == 0.2999999999999998 in Python) silently missing
            # the documented >= 0.3 threshold.
            if round(best_competitor.rating - own_avg_rating, 2) >= 0.3:
                alerts.append(Alert(
                    "warning",
                    f"{best_competitor.name} rated {best_competitor.rating} vs your {own_avg_rating} — worth a look",
                ))

    return ReportData(
        restaurant_name=restaurant_name,
        city=city,
        country=country,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total_mentions=len(all_mentions),
        positive_pct=round(len(pos) / total * 100, 1),
        negative_pct=round(len(neg) / total * 100, 1),
        neutral_pct=round(len(neu) / total * 100, 1),
        platform_breakdown=dict(platform_breakdown),
        alerts=alerts,
        top_positive=sorted(pos, key=lambda m: m.rating or 0, reverse=True)[:3],
        top_negative=sorted(neg, key=lambda m: m.rating or 5)[:3],
        sources_ok=sources_ok,
        sources_failed=sources_failed,
        own_avg_rating=own_avg_rating,
        competitors=competitors,
    )


def render_text_summary(report: ReportData) -> str:
    """Plain-text version of the report for the email body — used as the
    whole message when there's no PDF attachment yet, and as a readable
    summary alongside it when there is."""
    lines = [
        f"Отчёт о репутации: {report.restaurant_name} ({report.city}, {report.country})",
        f"Сформирован: {report.generated_at}",
        "",
        f"Всего упоминаний: {report.total_mentions}",
        f"Позитив {report.positive_pct}% / Негатив {report.negative_pct}% / Нейтрально {report.neutral_pct}%",
        "",
    ]
    if report.alerts:
        lines.append("Алерты:")
        for a in report.alerts:
            lines.append(f"  [{a.level.upper()}] {a.message}")
        lines.append("")
    if report.platform_breakdown:
        lines.append("По площадкам:")
        for platform, count in report.platform_breakdown.items():
            lines.append(f"  {platform}: {count}")
        lines.append("")
    if report.sources_failed:
        lines.append(f"Не удалось собрать: {', '.join(report.sources_failed)}")

    # Competitors section always comes last — reputation analysis is the
    # primary deliverable, competitors is a "и ещё" addendum, per product decision.
    if report.competitors:
        lines.append("")
        lines.append("Конкуренты поблизости (авто-подбор):")
        own = f"{report.own_avg_rating}" if report.own_avg_rating is not None else "н/д"
        lines.append(f"  Вы ({report.restaurant_name}): {own}")
        for c in report.competitors:
            rating = f"{c.rating}" if c.rating is not None else "рейтинг не найден"
            lines.append(f"  {c.name}: {rating}")

    return "\n".join(lines)


def to_json_dict(report: ReportData) -> dict:
    """Flattens ReportData (incl. nested Mention objects) into plain JSON for build_docx.js."""
    def mention_dict(m: Mention) -> dict:
        return {"platform": m.platform, "text": m.text, "rating": m.rating, "author": m.author}

    return {
        "restaurant_name": report.restaurant_name,
        "city": report.city,
        "country": report.country,
        "generated_at": report.generated_at,
        "total_mentions": report.total_mentions,
        "positive_pct": report.positive_pct,
        "negative_pct": report.negative_pct,
        "neutral_pct": report.neutral_pct,
        "platform_breakdown": report.platform_breakdown,
        "alerts": [{"level": a.level, "message": a.message} for a in report.alerts],
        "top_positive": [mention_dict(m) for m in report.top_positive],
        "top_negative": [mention_dict(m) for m in report.top_negative],
        "sources_ok": report.sources_ok,
        "sources_failed": report.sources_failed,
        "own_avg_rating": report.own_avg_rating,
        # Rendered as its own section in build_docx.js, placed after the
        # reputation sections — see that file's section ordering.
        "competitors": [
            {"name": c.name, "rating": c.rating, "source_url": c.source_url}
            for c in report.competitors
        ],
    }
