# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-03-22] Removed Google Trends Integration
Removed `fetch_google_trends()`, the `pytrends` import, and all `trending_topics` references from `evaluate_articles_with_claude()`. Removed `pytrends` from `requirements.txt`. The script runs exactly as before the feature was added.

## [2026-03-22] Smarter Within-Run Deduplication (Claude Topic Clustering)
Replaced the word-overlap heuristic for within-run deduplication with a Claude-based topic clustering approach. After scoring, Claude receives the full list of picks and groups them into same-story clusters. Only the single best pick per cluster survives — highest score wins; ties go to the more culturally relevant source (Claude decides). This ensures a day like a Luka 60-point game produces one pick, not six.

## [2026-03-17] Google Trends Integration
Added `fetch_google_trends()` to pull the top trending US searches from Google Trends each run. Trending topics are matched against article headlines to boost scores, surfacing articles tied to what people are actively searching.

## [2026-03-17] Deduplication (Within-Run and Cross-Run)
Added two layers of deduplication:
- **Within-run topic deduplication** — Claude de-duplicates articles covering the same story so the picks list stays varied. *(Replaced 2026-03-22 with Claude topic clustering — see above.)*
- **Cross-run URL deduplication** — URLs from recent picks files are tracked and excluded from new runs so the same article never appears twice across runs.

## [2026-03-17] Celebrity Gossip Filter
Added an explicit instruction to the Claude scoring prompt to score celebrity gossip (drama, feuds, relationships) as a 1. Content focus is cultural impact, not tabloid news.

## [2026-03-16] Cross-Source Trend Detection
Added `detect_cross_source_trends()` to identify topics appearing across 3+ independent sources. Articles flagged as trending across sources receive a score boost, surfacing stories with genuine multi-outlet momentum.

## [2026-03-12] Raised MAX_PICKS from 5 to 10
Increased the maximum picks per run from 5 to 10 so each run surfaces enough content to fill a content calendar before the next run.

## [2026-03-11] Politics Filter
Added an explicit instruction to the Claude scoring prompt to score any political content as a 1, regardless of traction. The @boymeetsblank_ account is politics-free.

## [2026-03-11] Per-Source Article Cap
Added `MAX_ARTICLES_PER_SOURCE = 5` to cap articles from any single RSS source. Prevents high-volume outlets like ESPN and Complex from dominating the candidate pool.

## [2026-03-11] Timestamped Output Filenames
Changed output filenames from `picks-YYYY-MM-DD.md` to `picks-YYYY-MM-DD-HHMM.md` so all three daily runs produce separate, preserved files.

## [2026-03-11] GitHub Actions Automation
Added `.github/workflows/daily_curator.yml` to run the script automatically 3x per day (8:30 AM, 3:30 PM, and 8:30 PM CT). Each run commits its picks file back to the repo.

## [2026-03-10] Auto Token Refresh
Added auto token refresh logic using `INOREADER_REFRESH_TOKEN` so the script always has a valid Inoreader access token — no manual token management needed.

## [2026-03-05] Initial Script
Created `daily_curator.py` — fetches articles from Inoreader RSS feeds, sends them to Claude AI for scoring (1–10) on four criteria (trending, timely, cultural, carousel-ready), and saves the top picks to a markdown file in the `picks/` folder.
