# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-05-24] Fix: cross-run and live-cluster dedup — Colbert/Kyle Busch pattern

Two clustering failures fixed. (1) Cross-run main feed dedup: `deduplicate_after_scoring()` now receives titles published in earlier runs today via `load_todays_published_titles()`. Sonnet compares current picks against already-published titles and removes duplicates — "Colbert Signs Off CBS" at 17:46 will now block "Stephen Colbert Makes Quick Return" in a later run. (2) Live cluster assignment: tightened the Haiku cluster prompt rules so that follow-up details, cause-of-death reveals, and reaction pieces are assigned to the originating cluster rather than spawning a new one — "Kyle Busch Dead at 39" and "Family: Busch died from pneumonia, sepsis" will cluster as one story.

## [2026-05-24] Live feed: social content overhaul — Google Trends RSS fix + Reddit culture subreddits

Three changes to make social content consistently present in the live feed. (1) Google Trends switched from the broken JSON endpoint to the RSS endpoint (`/daily/rss?geo=US`) — the JSON endpoint was returning non-JSON in GitHub Actions and silently failing; the RSS endpoint is XML-based and reliable. (2) Removed YouTube trending RSS — it has been consistently returning 0 results in GitHub Actions from both the free RSS and Apify; removed rather than silently failing every run. (3) Added `fetch_reddit_culture_hot()` which directly calls Reddit's hot.json API for 8 culture subreddits (r/popculturechat, r/music, r/movies, r/hiphopheads, r/streetwear, r/sneakers, r/nba, r/soccer) — bypasses the 90-min RSS publication window so posts surface when they're actually hot. Posts need 200+ upvotes and be under 12 hours old. Also: r/all threshold lowered 1000→500 upvotes; r/all and culture subreddits both use the 12h age window.

## [2026-05-22] Live feed: Reddit r/all added to clustering pipeline

`breaking_news_check.py` now fetches Reddit r/all hot posts every 5 minutes via `fetch_reddit_all_hot()`. Posts need 1,000+ upvotes and must be under 6 hours old to enter the pipeline — a higher bar than subscribed subreddits to ensure only genuinely viral content triggers clusters. Also: `load_social_trends()` now reads `reddit_hot` from the daily_curator cache so Haiku sees r/all titles as social context when scoring; `filter_and_enrich_items()` surfaces those titles in the live social signals block.

## [2026-05-22] Social-first signal upgrade: X posts, Reddit r/all, engagement data, 6x/day

Six changes landed together: (1) Curator now runs 6x/day (every ~3 hours, 7:30am–10:30pm CT) instead of 3x. (2) New `fetch_reddit_hot()` pulls top 25 posts from Reddit r/all via free public API — upvotes and comment counts flow into scoring. (3) New `fetch_twitter_posts()` fetches top tweets for the 3 highest-trending X topics via Apify (capped at 15 tweets/run to stay within free tier) — actual tweet text and likes/retweets/replies now scoreable as standalone picks. (4) X trending topics bumped from 20 → 30, Google Trends from 20 → 30. (5) Every article in the scoring prompt now shows an `Engagement:` line when data is available (rank on X, upvotes, likes, search volume), so Claude scores with full context rather than guessing. (6) `social_trends.json` now tracks `x_posts` and `reddit_hot` lists alongside existing platform signals, and `x_ranks` is now populated directly from the main curator run.

## [2026-05-22] Fix: cluster dedup now correctly removes all non-primary members

Previously, the post-scoring cluster dedup only pruned "orphaned" secondaries (where the primary was removed by cross-run dedup) but left all secondaries intact when the primary survived — causing multiple versions of the same story to appear in picks. Fixed to remove all non-primary cluster members unconditionally, keeping only the highest-scoring pick per cluster as intended.

## [2026-05-22] Automatic Inoreader refresh token rotation

On every run, if Inoreader returns a new refresh token (token rotation), `daily_curator.py` now automatically saves it back to the `INOREADER_REFRESH_TOKEN` GitHub Actions secret via the API. Requires `GITHUB_PAT` to be set as a GitHub Actions secret. This keeps the token perpetually fresh with no manual re-auth needed.

## [2026-05-22] Main feed: retry on Claude 529 overloaded error

`_score_batch()` now retries up to 4 times with exponential backoff (2s, 4s, 8s, 16s) when the Anthropic API returns a 529 overloaded error instead of crashing the run. All other errors (auth failures, rate limits, unexpected exceptions) still exit immediately.

## [2026-05-22] Live feed: removed Bluesky as a source

Removed `fetch_bluesky_trending()` and the Bluesky What's Hot feed from the live feed pipeline. The platform's "What's Hot" feed skews toward indie creators, journalists, and political commentators — not the mainstream culture audience Blank targets. Engagement signals on Bluesky (1–2K likes) don't translate to the same real-world significance as equivalent Reddit upvotes or X trending positions. Reddit, X trending, YouTube trending, and RSS feeds cover the same signal space without the noise. Removed Bluesky-specific scoring guidance from the Haiku prompt.

## [2026-05-22] Live feed: tighter Bluesky auto-1 rules — creator promos, crowdfunding, trivial posts

Three new categories added to the Haiku auto-1 list to stop personal Bluesky posts from passing the quality gate: (1) personal creator self-promotion (artist/creator announcing their own art, stickers, prints, merch — regardless of engagement); (2) crowdfunding and campaign posts (Kickstarter, Patreon, Indiegogo "last day to back" type content); (3) trivial observations, viral jokes, or "look at this funny thing" posts with no cultural news significance (e.g. pointing out a typo in a book). These types were scoring 5 (the gate minimum) and appearing in the feed despite having no editorial value.

## [2026-05-21] Disabled digest publisher

Commented out the "Run Digest Publisher" and "Commit digest" steps in `daily_curator.yml`. The `digest_publisher.py` script is still present — uncomment those steps to re-enable.

## [2026-05-21] Main feed: stronger same-event dedup — different angles on one event now cluster

The post-scoring Sonnet dedup was good at catching "same story, different outlets" but missed "one event generating multiple distinct angle headlines" (e.g. a single IPO filing producing three separately-worded picks). Fixed by replacing category-specific examples in the dedup prompt with event-identity logic: if all articles trace back to one single thing that happened, they are the same story and should cluster — regardless of how different the angles or revelations are.

## [2026-05-20] Live feed: Haiku now sees building clusters when scoring

Haiku was scoring each live feed item in isolation — it had no awareness that 2 other items about the same topic had already passed the quality gate. A third corroborating signal might score 6 because Haiku didn't know it was the third, not the first. Fixed by passing the current cluster state into `filter_and_enrich_items()` and injecting a "BUILDING STORIES" block into the Haiku prompt listing all active clusters with their signal count. If an incoming item matches a building story, Haiku is instructed to score it at least 1 point higher than it would in isolation — because convergence across independent sources is itself strong evidence something real is happening.

## [2026-05-20] Engagement signals in both feeds + recalibrated thresholds

Engagement signals now apply to both the live feed (Haiku) and the main feed (Sonnet). Main feed changes: (1) ENGAGEMENT SIGNALS section added to Sonnet scoring prompt with calibrated Reddit/Google thresholds; (2) trending context block now shows X rank positions (`#1 Josh Hart`) and Google search volumes (`Apple — 500K+ searches`) so Sonnet can see the scale of real-time interest, not just a flat topic list; (3) `social_trends.json` write now preserves `x_ranks`, `google_engagement`, `x_fetched_at`, and `google_fetched_at` written by the live feed instead of overwriting them. Threshold recalibration across both feeds: Reddit 10K+ upvotes → minimum 7; Reddit 30K+ → minimum 8 (was a single 50K threshold); Google 100K+ searches → strong signal, 250K+ → dominating the day (was a single 500K threshold that was too high for most genuinely trending topics).

## [2026-05-20] Live feed: engagement signals now flow into Haiku scoring

Engagement data is now surfaced to the Haiku quality gate so high-engagement content gets scored appropriately. Five changes: (1) Reddit upvotes + comment count and Bluesky likes + reposts + replies were fetched but never shown to Haiku — now included as brackets after each item in the scoring prompt (e.g. `[50,000 upvotes · 1,200 comments]`); (2) YouTube view counts extracted from `<yt:statistics>` in the RSS feed; (3) Google Trends `formattedTraffic` (e.g. "200K+ searches") extracted from the daily endpoint and stored in `social_trends.json`; (4) X trending rank position tracked and stored (`#1` through `#30`) so Haiku knows position-1 topics carry more weight; (5) Haiku prompt updated with explicit engagement scoring guidance — 50K+ Reddit upvotes, 10K+ Bluesky likes, and #1–5 X positions are treated as strong upward score signals.

## [2026-05-20] Main feed: live cluster awareness — confirmed stories get a score floor

`daily_curator.py` now reads `breaking_news_state.json` before scoring. Any live feed cluster already escalated to the main feed (i.e. confirmed by 3+ independent real-time signals) is injected into the Sonnet scoring prompt as a "LIVE FEED CONFIRMED STORIES" block. Articles that match a live cluster topic receive a score floor: 3–5 live signals → minimum 7; 6+ signals → minimum 8. This closes the gap between the live and main feed pipelines — if a story has been building for hours across Reddit, YouTube, X, and Bluesky, the 3×/day curator runs now know about it and prioritize it accordingly. Also fixed misleading log message in `detect_cross_source_trends()` (said "3+ sources" but threshold is 2+).

## [2026-05-20] Fix: Google Trends — dedicated TTL field + remove news-only filter

Two bugs fixed. (1) `refresh_google_trends()` was reading the global `fetched_at` timestamp (written by `daily_curator.py`'s Apify run) as its TTL, causing Google trends to appear "fresh" for up to 10 minutes after an Apify run even though the live refresh hadn't fired. Fixed with a dedicated `google_fetched_at` field, independent of Apify's timestamp. (2) Removed `ns=15` parameter from the Google Trends URL — this flag was silently filtering to news-only topics, excluding entertainment, sports, and celebrity trends. Full trending list now flows through.

## [2026-05-20] Push notifications for cluster escalation and updates

`escalate_cluster_to_sonnet()` now calls `send_breaking_push()` on both escalation paths: initial story escalation (when a cluster first hits 3 signals) sends the synthesized headline and "Why it matters" as the notification body; re-escalation (every 3 additional signals) sends an "Update: {topic}" notification with the new timestamped update paragraph. Users are notified in real time whenever a live cluster story is created or updated in the main feed.

## [2026-05-20] Live feed: X trending and Google Trends now refresh every 10 minutes

X (Twitter) trending topics now refresh every 10 minutes via trends24.in (free, no API key) instead of waiting for the 3×/day Apify run. Google Trends TTL tightened from 60 → 10 minutes. Combined with Reddit hot posts (already real-time), YouTube trending RSS (real-time), and Bluesky What's Hot (real-time), all five major social signals now feed the live feed continuously every ~10 minutes rather than in daily batches.

## [2026-05-20] Live feed: cluster-based escalation to main feed

When multiple live feed items converge on the same story, they now automatically cluster and escalate as one unified main feed pick. How it works: after each quality gate pass, a Haiku clustering call assigns new items to existing clusters or creates new ones (e.g., "Knicks win Game 1 of NBA Eastern Conference Finals" groups Knicks, Josh Hart, Harden, and Mike Breen signals together). When a cluster hits 3 items, Sonnet synthesizes all signals into one editorial story — headline, Why It Matters, and hook — and writes it to the main feed. Re-escalates every 3 additional items so evolving stories stay current. Cluster state persists in `breaking_news_state.json` with a 24-hour TTL.

## [2026-05-20] Live feed: tighter Haiku scoring gate + escalation threshold restored to 9

Rewrote the Haiku scoring prompt to fix junk flowing into the main feed after the May 19 overhaul. Four changes: (1) replaced "score generously" with "be strict — when in doubt, score lower"; (2) added explicit auto-1 list covering political content, generic social posts (good morning/lifestyle/emoji filler), local/trade niche articles, and bare trending topic names with no news context; (3) tightened Bluesky guidance — viral engagement alone is not enough, post must contain actual news or a genuine cultural flashpoint; (4) tightened the 8-anchor to require broad audience significance, not just niche relevance. Escalation threshold raised 8→9 so only "you have to tell someone right now" items reach the main feed.











