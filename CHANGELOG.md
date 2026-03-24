# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-03-22] Claude evaluation retry on unexpected format; verify Apify URL
Added retry logic to `evaluate_articles_with_claude()`: if Claude returns a response that can't be parsed as JSON, the call is retried once before the script exits. Verified all Apify base URLs — "appi.apify.com" typo was not present in the committed code.

## [2026-03-22] Fix Google Trends actor input; verify Apify base URL
Google Trends: changed input to `{"searchTerms": [""], "geo": "US"}` to fetch general US trending topics. Verified all Apify base URLs are correct (`api.apify.com`) — no typo was present in the committed code.

## [2026-03-23] Fix Twitter trends actor input — country must be numeric ID
The `karamelo/twitter-trends-scraper` actor's `country` field takes a numeric string ID, not a country name. Changed input from `{"country": "United States"}` to `{"country": "2", "live": true}` (`"2"` is the actor's internal ID for United States). This was the cause of the 400 Bad Request errors.

## [2026-03-22] Fix Apify actor inputs — Twitter 400 error and Google 0 results
Twitter trends: removed `timeOptions` parameter (was causing 400); input is now just `{"country": "United States"}`. Google Trends: replaced `searchTerms`/`timeRange` input with `{"geo": "US", "outputType": "trending-now"}` to fetch currently trending searches rather than analyzing a specific term.

## [2026-03-22] Fix Apify API calls — two-step run/poll/fetch pattern
Replaced the failing `run-sync-get-dataset-items` calls with the correct two-step Apify pattern: POST to `/runs` to start the actor, poll until `SUCCEEDED` (up to 60 seconds), then GET `/datasets/{id}/items`. Extracted shared `_run_apify_actor()` helper used by both trend functions. Updated inputs: Twitter uses `{"country": "United States", "timeOptions": ["0"]}`, Google uses `{"searchTerms": ["trending"], "geo": "US", "timeRange": "now 1-d"}`.

## [2026-03-22] Apify Integrations — Twitter Trends and Google Trends
Added two new content streams via Apify that are scored by Claude alongside Inoreader articles:
- **`fetch_twitter_trends()`** — calls Apify actor `karamelo/twitter-trends-scraper` to fetch top US trending topics from X (Twitter). Each trend appears as a standalone item with source "X (Twitter) Trending".
- **`fetch_google_trends()`** — calls Apify actor `apify/google-trends-scraper` to fetch top US trending search terms. Each trend appears as a standalone item with source "Google Trends".
Both functions fail gracefully — if Apify is unavailable the run continues without them. Added `APIFY_API_TOKEN` to the required credentials. In the picks file, trend items display "Trending on X right now" or "Trending on Google right now" instead of an article link.

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
