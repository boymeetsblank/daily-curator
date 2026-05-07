# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-05-06] Live feed scoring overhaul — tighter quality gate, no bare social trends

Rewrote the Haiku scoring prompt in `breaking_news_check.py` to match the main curator's scoring anchors (10: cultural moment, 9: tell someone now, 8: bring up today, 7: worth surfacing, 6: minimum bar). Tightened the politics filter to cover routine political/geopolitical/economic policy content while preserving a carve-out for genuinely historic moments. Removed bare X/Google/TikTok trend topic names as live feed candidates — social context signal is preserved in the scoring prompt but bare names no longer enter the pipeline. Dropped Reddit hot post threshold from 500 → 200 upvotes and raised per-source cap from 3 → 5 to increase candidate volume.

## [2026-05-06] Remove Reddit and Instagram Apify actors to stay within free tier

Reddit Trending was redundant (r/popular and r/all already covered by direct RSS). Instagram scraping requires browser automation — too expensive for the free plan. Apify stack is now 4 lightweight actors: X, Google, YouTube, TikTok.

## [2026-05-06] Raise per-subreddit article cap to 25

Reddit sources (any source name starting with "r/") now get a cap of 25 articles per run instead of the default 15. All other sources remain at 15. The overall 200-article hard cap still applies.

## [2026-05-06] Add r/popular and r/all as wide net sources

Added r/popular and r/all to sources.json as direct RSS feeds under the "wide net" category.

## [2026-05-02] Fix: Live section disappears overnight — extend TTL, commit social trends

Extended `BREAKING_NEWS_TTL_HOURS` from 6 → 12 so items from the previous evening survive the overnight dead zone (US feeds go quiet ~11 PM CT, next curator run at 7:30 AM CT). Fixed `social_trends.json` never being committed: added it to `git add` in `daily_curator.yml` so X, Google, and TikTok trending candidates are available to the breaking news monitor after each 3×/day curator run. Both issues were causing the Live section to show nothing for 8+ hours overnight.

## [2026-05-01] Digest slides: sentence-aware body copy + substack text on image slides

Body copy on story slides now stops at complete sentence boundaries instead of truncating mid-sentence with "...". Added `_wrap_sentences` helper that accumulates sentences until adding another would overflow the line limit, then stops clean. Also switched the image path to use the Substack copy field (already used by text-only slides) instead of the shorter "why" field, matching the more analytical tone.

---

## [2026-05-01] Hook prompt: natural punctuation guidance

Replaced the blunt "no period at the end of every line" rule with nuanced guidance: punctuate naturally based on rhythm — complete standalone thoughts get a period, fragments flowing as one sentence don't. Fixes hooks like "TIM COOK IS OUT / APPLE JUST HAD ITS BEST QUARTER EVER..." where the first line is a distinct beat that needs its own punctuation.

---

## [2026-04-30] Fix: live feed not updating after breaking news commits

GitHub blocks workflow-triggered pushes (via default GITHUB_TOKEN) from re-triggering other workflows, so breaking_news.yml commits to main were never firing deploy-pages.yml. Fixed by tracking whether a push actually happened (GITHUB_OUTPUT) and explicitly calling `gh workflow run deploy-pages.yml` only when new items were committed.

## [2026-04-30] Digest slide polish: remove borders, widen dividers, anchor text-only layout

Removed the outer border from all slides (cover and story). Widened the divider rule from 60px to 160px on both image and text-only story slides. On text-only slides, switched the content block from vertically centered to bottom-anchored (matching the image-path layout) and added a bottom gradient overlay starting at y=600 to ground the text zone instead of letting it float.

## [2026-04-30] Hook prompt: drop TRIGGER mechanic, break three-sentence pattern

Removed the `[TRIGGER: X]` emotional-label requirement — it was forcing Claude into a formulaic "emotion → three parallel sentences with periods" structure. Replaced with guidance to write like a text to a friend: fragments OK, lines can flow together as one broken thought, no period at the end of every line, vary between 2 and 3 lines. Updated the JSON example to show a natural-sounding hook instead of the old "Nobody saw this coming. / Not even the insiders. / It changes everything." pattern.

---

## [2026-04-30] Fix: digest slide headline text no longer clips at right edge

`_wrap_text` and `_truncate_lines` were using `draw.textlength()` (advance-width metric) to check if text fits within the content area. For Bebas Neue at 100px, actual rendered glyph extents exceed the advance width, so long hook lines appeared to fit but overflowed the canvas. Switched both functions to `draw.textbbox()` which returns real pixel bounds (including sidebearings), extracted into a shared `_text_width()` helper.

---

## [2026-05-01] Live feed: lower quality gate to 6, add MAX_FEED_SIZE cap

Lowered Haiku quality gate from `>= 7` to `>= 6` so the live feed consistently accumulates 5–10+ items per hour instead of going sparse during off-peak periods. Updated scoring prompt to define 6 as "the minimum for the live feed" rather than "could wait for the main daily feed." Added `MAX_FEED_SIZE = 20` to cap the total live feed size so active-hour volume doesn't overflow the section.

---

## [2026-04-30] Live feed: per-source cap uses 2-hour rolling window

Changed `MAX_LIVE_PER_SOURCE` from a TTL-based concurrent cap to a 2-hour rolling window. Only items detected in the last 2 hours count against a source's slot limit — items older than 2 hours no longer block new ones from the same source. Added `SOURCE_CAP_WINDOW_HOURS = 2` constant.

---

## [2026-04-30] Live feed: wider article window + per-source cap

Extended `FEED_WINDOW_MINUTES` from 30 → 60 so articles aren't silently dropped when GitHub Actions queue delays push evaluation past the old cutoff. Added `MAX_LIVE_PER_SOURCE = 3` cap applied in two places: before the Haiku quality gate (to avoid scoring excess articles from burst-publishing sources) and when merging items into the active Live feed (to prevent any one source from holding more than 3 slots at once).

---

## [2026-04-29] Fix: main feed list view — older picks showing latest run timestamp

Pinned (8+) and regular picks in list view were all rendered with `latestIsoTs` (the newest run's timestamp), so every article showed "X minutes ago" relative to the most recent pull. Fixed by grouping pinned picks by their own `runIsoTs` before passing to `renderPicksGrouped`, and restoring per-run rendering for regular picks (matching the original archive-day behavior). Card view was already correct.

## [2026-04-29] Fix: Live feed — crash on null haiku_score + stale source labels

`breaking_news_check.py` was crashing every 5-minute run with `TypeError: '>=' not supported between 'NoneType' and 'int'` when sorting items by tier. Legacy items written before the quality gate have `haiku_score: null` in `breaking_news.json`; `dict.get(key, default)` returns `None` (not 0) when the key exists with a null value. Fixed both tier sort lines to use `(x.get("haiku_score") or 0)`. Also fixed `renderBreakingCard` in `index.html`: all non-wire items were falling through to a hard-coded "Google Trends" label and "Search Google →" CTA. Now dispatches on `source_type` (feed/reddit/youtube/x/tiktok/google) for correct labels and CTAs on every item.

## [2026-04-28] Live feed: refined Haiku scoring prompt — 4-band scale, platform-aware

Replaced the binary pass/fail Haiku prompt with a 4-band scoring guide (9–10 must-know, 7–8 worth surfacing, 5–6 interesting, 1–4 noise). Trending topics (X, TikTok, YouTube, Google) are now explicitly told they don't need to be discrete breaking events — scored on cultural relevance instead. Haiku is instructed to score generously for culture-adjacent items (sneakers, music, sports, entertainment). Threshold stays at 7; the finer bands give Haiku permission to surface borderline items that the old binary prompt was silently killing.

---

## [2026-04-28] Main feed: 8+ picks always pinned to top of today's section

All picks scoring 8+ from any of today's curator runs are collected and sorted to the top of the main feed by score descending. Lower-scoring picks follow in their original order. Archive days are unaffected.

---

## [2026-04-28] X, Google, TikTok trending topics added as Live feed candidates

X trends link to x.com/search, Google to google.com/search, TikTok to tiktok.com/search. All pass through the Haiku quality gate alongside Reddit and YouTube candidates.

---

## [2026-04-28] Social-first Live feed — YouTube trending + trend-boosted scoring

- `daily_curator.py` now writes `social_trends.json` after each 3×/day Apify run, caching X, Google, YouTube, and TikTok trending topics
- `breaking_news_check.py` loads `social_trends.json` and injects live social signals into the Haiku scoring prompt — items matching live trends score higher
- YouTube trending videos added as real candidates via the free public RSS feed (no API key, no Apify cost)
- Reddit hot posts remain as primary social candidates alongside YouTube
- Zero increase in Apify usage — all social trend data reuses existing 3×/day curator runs

---

## [2026-04-28] Live picks inject into main feed without page refresh

- Main feed polls picks_data.json every 2 minutes (was 5)
- New live picks (from_live: true) detected during polling show a red "N new live picks — tap to view" banner
- Tapping the banner injects the new cards at the top of today's feed without re-rendering or resetting scroll
- Regular "new picks available" banner still fires for normal curator runs, but is suppressed when a live picks banner is shown instead
- renderedLiveUrls set prevents already-visible picks from re-surfacing on subsequent polls

---

## [2026-04-28] Live feed overhaul — tighter gate, Sonnet escalation, LIVE badge

- Rewrote Haiku quality gate prompt: scores for "did something just happen AND does it matter" — pass threshold raised from 7 to 8
- Items scoring 9+ are escalated to Sonnet, which writes editorial context and a carousel hook, then saves a picks markdown file so they appear in the main feed
- Push notifications now only fire for 9+ escalated items, not all gate-passers
- 9+ items are pinned to the top of the Live section; 8s flow chronologically below
- Live picks in the main feed display a red LIVE badge in the card meta row
- `deploy-pages.yml` now parses the `from_live` field from picks markdown files

---

## [2026-04-28] Live section feed window widened to 30 minutes

Increased `FEED_WINDOW_MINUTES` from 15 to 30 in `breaking_news_check.py` to reduce missed articles from slow feeds and delayed cron runs.

---

## [2026-04-28] Fix: breaking_news_check.py — Haiku batch quality gate

Replaced the zero-filter approach (every article from every source in the last
15 minutes was surfaced as "BREAKING") with a Claude Haiku batch quality gate.
All new candidates are now collected first, then sent to Haiku in a single API
call. Each item is scored 1–10 for cultural significance; only items scoring ≥ 7
are surfaced. Items scoring < 7 are recorded as seen (suppressed permanently) but
not shown. Context enrichment is now part of the same batch call rather than a
separate per-item call. Falls back to surfacing all candidates unfiltered if the
API is unavailable.

## [2026-04-27] Feat: YouTube Trending + TikTok Trending (3x/day) + Reddit Hot Posts (breaking)

Added three new cultural signals. `daily_curator.py`: `fetch_youtube_trends()` calls Apify actor `streamers~youtube-trending-videos` (US, 20 results); `fetch_tiktok_trends()` calls `clockworks~free-tiktok-scraper` (20 results). Both follow the exact `fetch_twitter_trends()` pattern and merge into `all_items` + `trending_topics` for velocity context. Scoring prompt updated to name all four trend sources and note that YouTube/TikTok viral items precede mainstream coverage. `breaking_news_check.py`: `fetch_reddit_hot_posts()` polls each Reddit subreddit in `sources.json` via the free hot.json API (no auth), surfaces posts with ≥500 upvotes not yet seen, enriches with Haiku context, and tracks IDs in the existing `known_ids` state.

## [2026-04-27] Feat: breaking news — Web Push notifications + remove dead Google Trends RSS

Google Trends RSS endpoint was returning 404 (Google deprecated it), meaning the monitor was silently producing nothing from that source on every run. Removed entirely. Added Web Push notifications to the breaking news workflow: when new items are detected, a "Breaking" push is sent to all subscribers with the Haiku context as the body. Updated `breaking_news.yml` to pass `VAPID_PRIVATE_KEY`/`VAPID_PUBLIC_KEY` and install `pywebpush`. State file simplified to a single `known_ids` list (no longer splits trend vs wire IDs).

## [2026-04-27] Fix: breaking news — use sources.json feeds instead of AP/BBC/NPR

Replaced hardcoded wire services (AP News, BBC, NPR) with a dynamic read from `sources.json`, so breaking news now monitors the exact RSS feeds from your Inoreader subscriptions. No API calls — direct RSS polling only.

## [2026-04-27] Feat: breaking news — fix dead pipeline, add wire services + Haiku enrichment

Fixed the breaking news pipeline which had never successfully run (state files never existed, XML parse errors were uncaught). Rewrote `breaking_news_check.py`: hardened Google Trends with proper XML error handling, added AP News/BBC/NPR RSS as wire sources detecting articles from the last 15 min, and enriched each new item with a Claude Haiku context line. Updated `breaking_news.yml`: cron 15min → 5min, concurrency guard, git pull moved before script runs, ANTHROPIC_API_KEY added. Updated `renderBreakingCard` in `index.html`: shows context, source label, and correct CTA per source type.

## [2026-04-27] UX: digest_publisher.py — larger body text on text-only story slides

Increased Inter body size from 19px → 26px on the no-image fallback path. Reduced max body lines from 6 → 5 to keep the layout balanced at the larger size.

## [2026-04-27] Fix: digest_publisher.py — prevent headline text overflow on story slides

Hook lines from picks files are now re-wrapped through `_wrap_text` before rendering. Previously, lines pre-split on " / " were drawn directly without measuring against canvas width, causing headline text to bleed past the right edge of the image.

## [2026-04-26] Ranking: cluster velocity scoring (+1 boost for fast-growing clusters)

Added `_annotate_cluster_velocities()` which computes `velocity = (member_count - 1) / hours_since_first_seen` for each cross-run cluster and sets `velocity_boosted = true` when velocity >= 1.0 members/hour. Fast-growing clusters get a +1 ranking boost (capped at 10) in `select_top_picks()`. Fields are persisted to `today_clusters.json` for future frontend use. Displayed article scores are unchanged.

## [2026-04-26] Scoring: flip tiebreaker from 6 to 7

Changed the scoring prompt tiebreaker from "when in doubt between a 6 and a 7, score it a 6" to "score it a 7". Audit showed 62% of picks landing at 6, compressing the feed into a narrow 6-7 band. This shifts the borderline population up without changing MIN_SCORE or the inclusion threshold.

## [2026-04-25] UX: index.html — move expand button below thumbnail, grow images to 96px

Removed the dedicated 32px expand-button column from list-mode grid (`auto 1fr auto 32px` → `auto 1fr auto`). Expand "+" now sits below the thumbnail (col 3, row 2, centered). Thumbnails grown from 72px → 96px desktop, 52px → 64px mobile.



## [2026-04-24] Feat: daily_curator.py — cross-run cluster persistence via today_clusters.json

Three new functions: `load_today_clusters()` (midnight CST reset), `save_today_clusters()`, and `merge_cross_run_clusters()` (keyword-overlap matching, ≥3 words). Articles matched to prior-run clusters inherit their cluster_id; updated clusters emit `**Updated:** true` in the markdown output. Resets daily at midnight CST via pytz/zoneinfo.



