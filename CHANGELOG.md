# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

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

## [2026-05-20] Cut Apify YouTube actor — replaced with free RSS

`fetch_youtube_trends()` in `daily_curator.py` now uses the free public YouTube trending RSS feed instead of the `streamers~youtube-trending-videos` Apify actor. Same data, zero Apify compute cost. Saves 3 actor runs/day. The live feed was already using this free RSS endpoint — the main curator now does the same.

## [2026-05-19] Live feed overhaul — more active, more social, smarter scoring

Raised live feed quality gate from 6→5 and Sonnet escalation threshold from 9→8, so more content surfaces and more reaches the main picks feed. Added Reddit 6-hour age filter (hot.json can return stale posts). Added Bluesky What's Hot as a source (free public API, no auth). Updated Haiku prompt with velocity/recency signal and Bluesky context. Added pip caching to breaking_news.yml to reduce run latency. Lowered Reddit upvote threshold 200→150. Fixed 3 broken Reddit RSS URLs (missing .rss suffix on r/InterestingAsFuck, r/NotTheOnion, r/Damnthatsinteresting). Added r/nextfuckinglevel, r/BeAmazed, r/PublicFreakout, r/streetwear to sources. Added Reddit first-mover signal to main curator scoring prompt. Fixed main feed auto-opening archive when today only has live picks.

## [2026-05-10] Main feed: stronger cross-source signal + any-topic scoring philosophy + MMA sources

Three changes to catch high-value stories that were slipping through. (1) Cross-source threshold lowered 3→2: stories covered by 2+ sources now trigger the TRENDING flag, giving more stories the benefit of the doubt. (2) Cross-source bonus upgraded to hard score floors: 2+ sources → minimum 7, 3+ sources → minimum 8, applied regardless of topic. (3) Haiku prompt rewritten from category-list framing ("sneakers, music, sports...") to audience-first framing ("well-connected, culturally aware person") — anything genuinely significant has a fair shot regardless of topic bucket. (4) Added MMA Fighting, MMA Junkie, and r/MMA as sources so major fight events surface reliably.

## [2026-05-07] Live feed: purely reverse-chronological, no score pinning

Removed the two-tier sort that pinned 9+ items to the top of the Live feed. The Live section is now strictly newest-first. Score-based pinning belongs in the main feed only.

## [2026-05-07] Live feed: MAX_FEED_SIZE raised 20→40

Increased the live feed display cap from 20 to 40 items. With the pipeline now generating 5–12 new items/hour during peak hours, the old cap was filling up within 2–4 hours and blocking new entries until older items expired.

## [2026-05-07] Live feed volume: social candidates restored, 6 new RSS sources, 5 subreddits, free Google Trends refresh, 4h failed-item window, wider article window

Six changes to restore and grow live feed candidate volume after the May 6 overhaul thinned the pipeline: (1) restored `build_social_candidates()` call so X/Google/TikTok topics re-enter as Haiku-scored candidates; (2) added 6 RSS sources — Pitchfork, Billboard, Rolling Stone, The Ringer, Deadline, Bleacher Report; (3) breaking news monitor now tops up Google Trends data from the free unofficial daily endpoint when `social_trends.json` is >60 minutes old — no Apify cost; (4) added 5 subreddits — r/hiphopheads, r/sneakers, r/soccer, r/movies, r/music; (5) failed items (score 1–5) are now suppressed for only 4 hours instead of permanently, so slow-burn stories can resurface; (6) `FEED_WINDOW_MINUTES` widened 60→90 to reduce misses from delayed GitHub Actions runs.

## [2026-05-06] Live feed scoring overhaul — tighter quality gate, no bare social trends

Rewrote the Haiku scoring prompt in `breaking_news_check.py` to match the main curator's scoring anchors (10: cultural moment, 9: tell someone now, 8: bring up today, 7: worth surfacing, 6: minimum bar). Tightened the politics filter to cover routine political/geopolitical/economic policy content while preserving a carve-out for genuinely historic moments. Removed bare X/Google/TikTok trend topic names as live feed candidates — social context signal is preserved in the scoring prompt but bare names no longer enter the pipeline. Dropped Reddit hot post threshold from 500 → 200 upvotes and raised per-source cap from 3 → 5 to increase candidate volume.

## [2026-05-06] Remove Reddit and Instagram Apify actors to stay within free tier

Reddit Trending was redundant (r/popular and r/all already covered by direct RSS). Instagram scraping requires browser automation — too expensive for the free plan. Apify stack is now 4 lightweight actors: X, Google, YouTube, TikTok.

## [2026-05-06] Raise per-subreddit article cap to 25

Reddit sources (any source name starting with "r/") now get a cap of 25 articles per run instead of the default 15. All other sources remain at 15. The overall 200-article hard cap still applies.

## [2026-05-06] Add r/popular and r/all as wide net sources

Added r/popular and r/all to sources.json as direct RSS feeds under the "wide net" category.





