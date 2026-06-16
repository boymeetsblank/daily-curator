# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-06-15] Fix: clicking "new picks" banner now actually refreshes the feed

`dismissBanner()` was only hiding the banner without reloading data. Added a `loadFeed()` call so clicking the banner fetches and renders the new picks as expected.

---

## [2026-06-13] Optimization: token efficiency — halve breaking-news poll rate, cache Haiku prompt, trim scoring context

Four changes to reduce daily API token spend (~650K–1.3M tokens/day → ~400–800K estimated). (1) **Breaking news cron 5min→10min** (`.github/workflows/breaking_news.yml`): halves the number of Haiku calls from 288/day to 144/day, saving ~144K–288K tokens/day with at most 5 min added latency to a breaking story. (2) **Prompt cache on Haiku quality gate** (`breaking_news_check.py`, `filter_and_enrich_items()`): the static scoring rubric (~1.5K tokens) is now split out with `cache_control: ephemeral` so calls 2–N within the 5-min cache TTL reuse a warm cache — saves ~60–70% of per-call input tokens. (3) **Trending topics cap 30→10** (`daily_curator.py`, `evaluate_articles_with_claude()`): scoring context block now injects only the top 10 trending topics instead of 30; the signal from ranks 11–30 is negligible. (4) **Recently-covered window 3 days→1 day** (`daily_curator.py`, `load_recently_covered_topics()`): the 3-day lookback was loading 40–100+ stale entries into every scoring prompt; 1 day captures all the meaningful same-day dedup signal while actual URL dedup is handled separately.

## [2026-06-13] Feature: "Other angles" — cross-run duplicates become linked alternatives instead of deletions

Three changes to how same-story duplicates are handled when they span multiple runs. (1) **Within-run dedup prompt**: added an explicit rule that two articles describing different *consequences* of the same event (e.g. "SpaceX stock up 19%" and "Musk becomes trillionaire" are both outcomes of the SpaceX IPO closing) are one story and must cluster — Haiku was previously splitting them by subject (company vs. founder). (2) **Cross-run why context**: `load_todays_published_titles()` now returns `{title, why}` dicts instead of bare strings, so the ALREADY IN THE FEED block in `deduplicate_after_scoring()` shows the editorial rationale alongside the title — letting Haiku match abstract headlines like "A trillion dollars is a stupid amount of money" to concrete SpaceX IPO articles in the current run. (3) **ALREADY COVERED drops all + merges into primary**: when Haiku groups current articles under "ALREADY COVERED: <title>", ALL of them (including the winner) are now dropped from the current run and merged into the already-published pick's `**Other angles:**` section via a new `_add_to_published_pick_related()` helper — previously the winner still appeared in the feed. The `**Folded:** true` marker on a pick tells the deploy script to exclude it from the feed JSON entirely (it survives only as a link in the primary pick's Other angles). `**Other angles:**` is parsed in `deploy-pages.yml` into a `related_articles` array and shown in the expand panel as clickable links.

## [2026-06-04] Fix: systemic cross-run dedup — X trending picks now visible to all dedup paths

Three regex patterns in the dedup pipeline used `[Read the full article` to find published picks, which excluded X trending and Google Trends picks from daily curator runs (those use `*Trending on X right now*` with no link). As a result, "Knicks" published at 5:28 AM was invisible to every dedup guard, causing the 9:03 AM live run to re-escalate it as a new story. Fixed by broadening the regex in `_todays_pick_titles()` (breaking_news_check.py), `load_todays_published_titles()` (daily_curator.py), and `load_recently_covered_topics()` (daily_curator.py) to also match `*Trending` format picks. Added a guard in `escalate_to_sonnet()` (previously only cluster escalation had this check) with a lower threshold of 1 keyword for single-word trending topics like "Knicks". Strengthened `deduplicate_after_scoring()` prompt to explicitly cluster X trend topics with same-event articles within a run.

## [2026-06-03] Fix: Reddit subreddits switch from /hot to /top?t=day + upvote floor

`fetch_subreddit_hot_posts()` now hits `/top.json?t=day` instead of `/hot.json`. Top-of-day ranking guarantees posts are from today, so the 48h age filter is removed entirely — upvotes is the only quality gate (200+ minimum). Hot was Reddit's decay algorithm that mixed old viral posts with new ones, causing many fresh posts to be filtered by the age cutoff before Claude ever saw them.

## [2026-06-01] Feature: light runs (Inoreader + RSS + Reddit only, no Apify)

Added `--light` flag to `daily_curator.py` that skips all 4 Apify calls (Twitter Trends, Google Trends, TikTok Trends, Twitter Posts). Light runs still fetch Inoreader, Direct RSS, Reddit, and YouTube RSS, then score with Claude Sonnet. Also added `.github/workflows/light_curator.yml` — runs at 10:00 AM CT and 4:00 PM CT to fill the gaps between full runs, adding ~$7/month in Claude costs. Light runs skip the `social_trends.json` write to preserve the last full run's X/Google/TikTok data.

---

## [2026-05-31] Feature: fetch subreddit hot posts via Reddit API (not RSS)

Reddit RSS feeds return "hot" posts regardless of age, most of which were filtered by the 48h cutoff — leaving only ~15 Reddit posts per run with no upvote data. Replaced with direct Reddit JSON API calls (`/hot.json`) for all 20 configured subreddits, run in parallel (10 workers). Posts are filtered to `HOURS_BACK` and include upvote/comment counts, enabling engagement scoring floors (10K+ upvotes → min 7, 30K+ → min 8). Expected Reddit pool: 50–100 posts per run.

---

## [2026-05-31] Fix: let Reddit posts recirculate across runs

Reddit hot posts persist in RSS feeds for hours/days, but unpicked posts were being added to seen_urls after every run — permanently blocking them from later runs even as they gained upvotes. Now Reddit-sourced articles (sources starting with "r/" or containing "reddit") are only added to seen_urls if they were actually picked (score ≥ 6). This allows a post that scored 5 at 8 AM to resurface at 1 PM with 50K upvotes and hit the engagement floor. News articles unchanged.

---

## [2026-05-31] Fix: use Claude's `why` context in post-scoring dedup input

Post-scoring dedup was failing to cluster related picks (e.g. 10+ NBA Finals items, two Jay-Z Roots Picnic items) because trending keyword items like "Spurs" or "Thunder" had no summary text, leaving Haiku with no signal to group them with related articles. Now uses the `why` field (Claude's scoring rationale) as the primary context for each item, falling back to `hook` then `summary`. The `why` field always contains a plain-English editorial explanation of what the item is about, giving dedup the connective tissue to cluster even bare-keyword trend items.

---

## [2026-05-25] Fix: stronger dedup prompt + switch to Haiku for post-scoring dedup

`deduplicate_after_scoring()` had two issues: (1) the "one single thing that happened" test let reaction pieces and analysis articles through as "different stories," and (2) it was using Sonnet for a simple pattern-matching task. Fixed: expanded the grouping rules to explicitly include reaction pieces, multi-outlet coverage, and any articles sharing the same person + topic in the same news cycle. Switched the dedup model from `claude-sonnet-4-6` to `claude-haiku-4-5-20251001` — same accuracy for this task, ~20× cheaper, max_tokens reduced 2048→1024.

## [2026-05-25] Fix: cross-run and within-run clustering now catches named-entity stories

Two clustering bugs caused same-story articles (e.g. multiple Pope Leo AI encyclical pieces) to survive as separate picks across runs. Fixed:
1. **Named-entity bigrams** — `_extract_keywords()` now extracts consecutive title-cased word pairs (e.g. "pope leo", "elon musk") as bonus tokens. Possessives are stripped first so "Leo's" correctly yields "leo".
2. **Looser cross-run threshold** — `merge_cross_run_clusters()` now matches if ≥1 bigram overlaps OR ≥2 unigrams overlap (was: total ≥3 unigrams). Bigrams count double in the ranking score.
3. **Possessive fix in entity extraction** — `_extract_primary_entity()` strips "'s" before cleaning so "Pope Leo's" and "Pope Leo" produce the same entity.
4. **Prefix entity matching** — within-run secondary pass now clusters articles where one entity is a prefix of the other (e.g. "pope" matches "pope leo"), instead of requiring exact string equality.

## [2026-05-24] Fix: live cluster escalation now checks for already-published stories

Added a pre-write guard in `escalate_cluster_to_sonnet()`: before writing a new picks file, it loads today's already-published pick titles and checks keyword overlap with the cluster topic. If 2+ distinctive keywords match an existing pick, the escalation is skipped — fixing cases like "Neon Extends Palme d'Or Streak" (main feed at 14:13) being duplicated by a live cluster escalation 3 minutes later.

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
















