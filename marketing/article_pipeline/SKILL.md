---
name: restaurateur-articles
description: Researches a topic relevant to restaurant/cafe owners (reputation management, marketing technology, online advertising for food service, and related subjects it identifies itself), writes an article, and selects which platform(s) to publish it on based on the target geo. Use when it's time to publish content for the Repas marketing channel.
---

# Restaurateur Articles — geo-aware research-to-publish pipeline

Writes and distributes content marketing articles for restaurant/cafe owners,
choosing *where* to publish based on the target region — not a single fixed
blog. Companion to the video channel (Instagram/Facebook) as Repas's second
free-product marketing channel (see `plans/2026-08-26-repas-program-plan.md`,
Phase 2).

## The honest constraint this skill is built around

**Most content platforms do not offer a real "post as this account"
API to arbitrary developers.** Treating "autopost" as uniform across
platforms is how this kind of pipeline quietly turns into "autopost to the
one platform that actually has an API, manually copy-paste everywhere else."
This skill is explicit about that instead of hiding it — see
`platforms.json`'s `automation_tier` field:

| Tier | Meaning | Platforms |
|---|---|---|
| **1 — full auto** | Real API, no editorial gatekeeping, publishes unattended | own blog (WordPress/Ghost REST API), Telegram channel (Bot API) |
| **2 — auto after approval** | Real API, but needs an approved developer app first (Meta-style lead time — see Phase 0 in the program plan) | LinkedIn Company Page (Marketing Developer Platform), Medium (if the account still has legacy API access — verify, Medium closed it to new integrations) |
| **3 — draft only** | Editorial/community-moderated platforms with no public autopost path — the skill prepares a ready-to-submit draft, a human posts it | VC.ru, Habr (RU-language business/tech media — both require human submission through their own editorial flow regardless of what any pipeline does) |

Don't build against a platform's API before confirming its current tier —
platform APIs change (Medium's is a known example: closed to new write-API
integrations). Tier 3 platforms are still worth including in geo selection
— restaurateurs in RU-speaking markets do read Habr/VC.ru — the skill just
outputs a polished draft + suggested submission notes instead of pretending
to auto-publish there.

## Workflow

### Stage 1 — Topic research
- Pick from: **репутация** (reputation/reviews management), **технологии** (POS, delivery-platform integrations, automation), **реклама в сети для общепита** (online ads/marketing for food service), or a topic the skill identifies itself via research (menu engineering, staff retention, seasonal promotions, delivery economics, etc.) — don't limit to a fixed list, that defeats the point of "он сам проведёт ресерч"
- `WebSearch`: what are restaurateurs in the target region actually asking/struggling with right now? What's already been written well on this topic — don't rehash it, find the angle that's missing
- Output: one clear angle, not a generic overview — e.g. not "how reviews matter" but "why a 4.6 rating can still mean lost bookings" (concrete, specific)

### Stage 2 — Write
- Language matches the target geo (see Stage 3) — a Georgian-market article in Russian differs from a German-market article in English/German, not a translated copy of the same text
- Length/format fits the destination platform (Telegram post ≠ long-form blog post ≠ LinkedIn article) — don't write one article and paste it everywhere unchanged
- Run through the `humanizer` skill before finalizing — AI-sounding marketing copy undermines the exact credibility this content is meant to build for a reputation-management product
- Ground claims in the research from Stage 1, not generic assertions

### Stage 3 — Geo → platform selection
- Look up the target country's region in `config/countries.json` (already defines caucasus / central_asia / western_europe / eastern_europe for the whole product — reuse it, don't re-derive)
- Match region to platforms via `platforms.json` in this directory
- Prefer Tier 1 platforms first (they publish unattended); include Tier 2 only once its approval has actually landed (check `plans/2026-08-26-repas-program-plan.md` Phase 0 status); Tier 3 always produces a draft package, never a live post

### Stage 4 — Publish or package
- Tier 1: call the platform's API directly, confirm the post is live, log the URL
- Tier 2: same, but only if approval is confirmed — otherwise fall back to producing a draft like Tier 3
- Tier 3: write the final article + a short submission note (why this fits the platform's audience) to `marketing/article_pipeline/_drafts/`, notify that it's ready for manual submission — do not claim it was published

## What this skill does NOT do

- Does not fabricate platform access it doesn't have — a platform with no confirmed API key/approval never gets a "success", only a draft
- Does not reuse one article verbatim across platforms/languages
- Does not publish without going through `humanizer` first
