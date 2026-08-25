"""Turns a list of CollectionResult (raw mentions from all platforms) into
the structured data the docx report builder renders.

Deliberately simple keyword-based sentiment for the MVP — good enough to
flag alerts and sort mentions; swap for an LLM-based pass later if the
keyword approach proves too coarse on real data.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from collectors.models import CollectionResult, Mention

POSITIVE_WORDS = {
    "great", "excellent", "amazing", "delicious", "friendly", "perfect",
    "love", "best", "recommend", "wonderful", "fantastic", "cozy", "fresh",
}
NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "worst", "poor", "disappointing", "slow",
    "rude", "cold", "overpriced", "dirty", "poisoning", "sick",
}
CRISIS_WORDS = {"poisoning", "sick", "hygiene", "lawsuit", "health inspector", "roach", "vomit"}


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


def build_report(results: list[CollectionResult], restaurant_name: str, city: str, country: str) -> ReportData:
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
    }
