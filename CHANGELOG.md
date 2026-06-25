# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-06-25] Feat: cluster expand reveals clickable article perspectives

Expanding a cluster strip now shows an "Other perspectives" drawer with each related article as a clickable row — source name in amber mono above an italic serif headline. Rows have an amber left-border rule on hover. Restructured list card HTML so the main `<a>` and the cluster section are siblings inside `.list-card-outer` (valid HTML — nested `<a>` tags are not). CSS transitions use max-height for smooth open/close. Condition for showing the cluster section now also triggers when `related_articles` has entries, even if cluster_size is 1.

## [2026-06-25] Fix: blank.yml merge conflicts + blank.db feed integration

`blank.yml` no longer commits `index.html` — only `blank.db` is staged per run, eliminating the rebase conflict with the Canvas design. `deploy-pages.yml` now reads scored items directly from `blank.db` (scores ≥ 6, last 72 hours), groups them into synthetic hour-batch runs, and merges them into `picks_data.json` alongside picks/*.md data — so the Canvas feed displays new-engine articles.

## [2026-06-25] Fix: cluster expand arrow always visible on cluster strips

Expand `↓` button was only rendered when a cluster had 4+ listed sources (extra > 0). Most clusters have 2–3 listed sources so the button never appeared. Now the button always renders on any cluster strip. Added a `.cluster-total` span (shown on expand) that displays "{N} sources total" when `cluster_size` exceeds the number of listed pills.

## [2026-06-24] Fix: image support in continuous pipeline (db → ingest → publish)

Added `image_url TEXT` column to `items` table in `db.py`. `init_db()` runs `ALTER TABLE items ADD COLUMN image_url TEXT` as a migration so existing `blank.db` files upgrade automatically. `insert_item()` now accepts `image_url`. `get_feed()` now includes `image_url` in its SELECT. In `ingest.py`, each feedparser entry is checked for `media_content` → `enclosures` → `media_thumbnail` (in that order) to extract an inline image URL, which is passed to `insert_item()`. In `publish.py`, `_render_card()` renders a `<img class="card-img">` when an image is present, the deferred JSON includes `image_url`, and the lazy-load `renderCard()` JS function does the same.

## [2026-06-24] Fix: cluster expand button now works

Changed the cluster expand trigger from a static `<span>` (no handler) to a `<button>` with event delegation on `#js-feed`. All source pills are now pre-rendered in the DOM (extras marked `.cluster-pill-extra`); CSS toggles their visibility when `.cluster-strip.expanded` is set. Clicking the button stops propagation so the card link doesn't fire, toggles the expanded class, and swaps the arrow between `↓` and `↑`.

## [2026-06-24] Fix: extract inline images from RSS feeds and Reddit API

`fetch_feed_articles` now extracts `<media:content url>` (MRSS namespace, both Yahoo variants) and `<enclosure url>` from each RSS item and includes an `image` field in the returned article dict. All three Reddit fetch functions (`fetch_reddit_hot_posts`, `fetch_reddit_all_hot`, `fetch_reddit_culture_hot`) now call `_reddit_image(post)` to pull the high-res preview URL (or thumbnail fallback) from Reddit's JSON response. The inline image is preferred in both pick write paths; `_fetch_og_image()` is only called as a fallback when no inline image is available. Added `_reddit_image()` helper that decodes HTML-encoded `&amp;` in Reddit CDN URLs.

## [2026-06-24] Feature: infinite scroll — 50 picks per page

Feed now loads 50 picks at a time. An IntersectionObserver on a sentinel element at the bottom fires when the user nears the end, appending the next 50 picks without a page reload. Newly added cards animate in with a staggered `translateY` + fade (first 7 cards, 42ms apart). Three bouncing dots mark the sentinel while the next batch is pending. A `· · ·` end-of-feed marker appears when all picks are exhausted. The 100-pick cap on data loading is removed — all picks across all runs are now available for pagination.

## [2026-06-24] Fix: feed now shows 6s and 7s, not just 8s

The JS was loading only the 10 most recent *runs*, but each live cluster pick is its own file — so 10 runs = 10 single-pick files, all scored 8. Changed to load all runs and cap at 100 total picks instead, so multi-pick regular-curator runs (with 6s and 7s) are always included.

## [2026-06-24] Fix: og:image enrichment for live cluster picks

Added `_fetch_og_image()` to `breaking_news_check.py` (mirrors the same helper in `daily_curator.py`). Both live pick write paths (single-item escalation and cluster escalation) now fetch the og:image from the primary article URL before writing the picks file, and emit `**Image:** <url>` when one is found. Google News redirect URLs are followed automatically. Live cluster cards in the web feed will now show real article thumbnails instead of placeholder colors.

## [2026-06-24] UI: The Canvas redesign — web feed overhaul

Replaced the static hardcoded `index.html` with a fully dynamic, design-system-faithful implementation of "The Canvas" direction from the Blank News Reader design handoff. The page now fetches `picks_data.json` at runtime and renders a live feed. Key changes: hero card (full-bleed image + gradient overlay, score pill, "Top Story" badge), 2-up mini grid for picks 2–3, list cards with score pills (amber ≥7, muted ≤6), cluster strips showing cross-source coverage, trend badges, and warm placeholder colors for articles without images. Typography uses DM Mono (wordmark/metadata), DM Sans (UI/body), and Newsreader (headlines). Filter pills added: All, Top Picks (score ≥8), Live (from_live or trending). Sticky app bar with backdrop blur. Service worker registration preserved. `__VOTE_TOKEN__` and `__VAPID_PUBLIC_KEY__` placeholders retained for deploy-workflow injection.

## [2026-06-24] Fix: Reddit 429 rate-limiting â€” user-agent + inter-request delay

Added `USER_AGENT = "blank-engine/0.1 (personal feed reader)"` constant to `ingest.py` and passed it through `feedparser.parse(..., agent=USER_AGENT)` on every feed fetch. Reddit (and some other hosts) rejects requests with a generic or absent user-agent, causing all-or-most Reddit sources to get 429'd in bursts. Added `REDDIT_DELAY = 2.0` constant and a delay pass in `poll_all_active()`: before each Reddit source is polled, the loop checks how long it's been since the last Reddit request and sleeps the remainder of `REDDIT_DELAY` if needed â€” keeping requests at least 2 s apart. Non-Reddit sources are unaffected. All 20 active Reddit sources were already active in the DB; no reactivation was needed. Tested against all 20 Reddit sources: **20/20 succeeded with 0 errors** (vs 1/19 previously). Also fixed a pre-existing `_sqlite3` name error in the `__main__` block.

## [2026-06-24] Fix: Remove DEFAULT_SOURCES auto-seeding; purge BBC test data

Removed `DEFAULT_SOURCES` list and `seed_sources()` helper from `ingest.py`. Removed the `ingest.seed_sources()` call from `run_pipeline.py` that was re-activating test seeds (BBC, TechCrunch, Reddit r/popular, Pitchfork News) on every pipeline run. Sources are now managed exclusively via `sources.json` import. Purged all 52 BBC News World items from blank.db (scores, triage rows, and items deleted). BBC source (id=1) confirmed inactive. TechCrunch (id=2) and Reddit r/popular (id=3) remain active per user request.

## [2026-06-24] Feature: Source-balanced feed assembly

Added `_balance_feed()` helper and `max_source_share` parameter to `get_feed()` in `db.py`. Feed candidates are now pulled in bulk (5Ã— the target limit), sorted score DESC, then passed through a greedy capping pass: each source may claim at most `round(limit Ã— max_source_share)` slots. Items that exceed the cap are deferred and appended in score order after the main pass â€” they still appear in the feed, just below less-dominant sources. High-scoring stories from any source are never suppressed. Added `FEED_SOURCE_CAP = 0.30` constant in `publish.py` to make the threshold easy to tune. `get_feed()` prints a before/after source-distribution report to stdout on every call so the effect is visible in logs. Also changed the base sort from `scored_at DESC` to `score DESC, scored_at DESC` so score is the true primary signal.

## [2026-06-24] Fix: Prevent Google News articles with no pubDate from showing stale ages

When a Google News RSS entry has no `pubDate` (common with `site:` search feeds), `ingest.py` now substitutes the current fetch time as `published_at` instead of leaving it `None`. This ensures the 48-hour backlog cutoff always fires and articles never display a misleading age like "1962d ago". Also changed `get_feed()` in `db.py` to filter by `fetched_at` instead of `COALESCE(published_at, fetched_at)`, so even articles with an old stored `published_at` age out of the feed 48 hours after they were ingested.

## [2026-06-23] Feature: Infinite scroll feed (up to 200 items)

Increased `FEED_LIMIT` from 50 â†’ 200 in `publish.py`. The first 20 cards are now server-rendered as static HTML for instant load; remaining items are embedded as a JSON blob in the page. An `IntersectionObserver` on a sentinel element at the bottom of the list loads the next 20 cards each time the user scrolls to the end â€” no extra network requests, works on the static GitHub Pages site. Added `FEED_PAGE_SIZE = 20` constant and extracted `_render_card()` helper so the Python and JS card renderers stay structurally in sync.

## [2026-06-23] Fix: Old articles (1000+ days) surfacing in feed

Two bugs allowed ancient articles into the feed. **Bug 1 (`ingest.py`):** The 48-hour age cutoff was gated behind a `first_poll` check, so it only ran when a source was first added. Subsequent polls accepted any article regardless of age. Fixed by removing the `first_poll` guard â€” the cutoff now applies on every poll. **Bug 2 (`db.py`):** `get_feed()` had no age filter; it returned any scored item with score â‰¥ 6, no matter how old. Fixed by adding `AND COALESCE(i.published_at, i.fetched_at) >= ?` (48-hour cutoff) to the WHERE clause. These two fixes together mean old articles are rejected at ingest and also blocked at the feed query as a safety net.

## [2026-06-22] New: GitHub Actions cron + pipeline orchestrator

Created `run_pipeline.py` â€” orchestrates the full cascade (ingest â†’ triage â†’ score â†’ publish) with per-stage error isolation. Each stage is wrapped so failures log cleanly and later stages still run where possible. Publish runs with `no_push=True`; git is handled by the workflow. Created `.github/workflows/blank.yml` â€” new separate workflow (does NOT touch old daily_curator.yml) that runs every 10 minutes + workflow_dispatch, installs feedparser + anthropic, runs the pipeline, then commits `blank.db` + `index.html` back to main with a timestamped message. Concurrency group with `cancel-in-progress: false` prevents simultaneous DB writes. Committed `blank.db` (97 items, 84 scored) as starting state so the first cron run builds on existing data.

## [2026-06-22] New: Static site publisher (publish.py)

Created `publish.py` â€” reads the scored feed from blank.db via `get_feed(min_score=6, limit=50)` and generates a self-contained static index.html with all CSS inline (system font stack, 1px borders, no gradients, mobile-first). Detects Pages deployment method at runtime (Actions/docs/root) and prints findings before writing anything. Requires explicit confirmation before overwriting existing index.html. Flags: `--no-push` (generate locally, print browser path, skip git); `--confirm` (skip interactive prompt); `--out PATH` (override output file). Commits with timestamped message and pushes to origin/main. Never force-pushes.

## [2026-06-22] New: Sonnet scoring layer (score.py)

Created `score.py` â€” scores escalated items 1â€“10 via Claude Sonnet against the full editorial rubric (interest OR importance, either qualifies; topic-neutral; soft floor flags never force score; 6/7 ties go to 7). Batches 12 items per call. Per item writes: score, four criteria sub-scores (trending/timely/cultural/significance), editor why (1â€“2 sentences), punchy hook (one line), and soft_floor_flags via `record_score()`. Defensive JSON parsing with fence-stripping; batch parse failures skip gracefully (items stay in queue for re-run). Verified on 92 live items: 84 scored, 4Ã—9, 18Ã—8, 33Ã—7, 22Ã—6, 7 below threshold. One batch (8 items) skipped due to Sonnet breaking JSON format to fact-check potentially fabricated news â€” known behavior, noted as future prompt hardening TODO.

## [2026-06-22] Feature: audit.py â€” opt-in recovery of wrongly-killed items

Extended `audit.py` with recovery mode. Default (`python audit.py`) remains measure-only â€” reports false-negative rate, changes nothing. `python audit.py --recover` flips each WRONGLY_KILLED item's triage row from KILL to ESCALATE so it reaches Sonnet scoring on the next run. Every recovery is logged with the item title, Haiku's original kill_reason, and Sonnet's overrule reasoning. Safety cap: if wrongly-killed rate exceeds 30% of the audited sample, recovery is withheld and a warning is printed (a spike that large signals a structural triage break, not occasional misses). `_recover_item()` annotates the triage signals JSON with `recovered_by_audit`, `original_kill_reason`, and `audit_reasoning` for traceability.

## [2026-06-22] Fix: Haiku triage over-killing Reddit/title-only items

Patched the Haiku triage prompt in `triage.py` to add explicit handling for title-only items (Reddit, link-aggregators). The "no substance" rule was incorrectly firing when description was empty, even when the title itself described real content. Fix: added a `TITLE-ONLY ITEMS` rule block clarifying that empty description is never alone sufficient to KILL, and that a title describing a video/event/question/subject IS content. Also added `--empty description` to the NEVER kill list. Added `reset_killed_items()` helper + `--retriage-kills` CLI flag to clear KILL rows for re-evaluation after a prompt fix. Result: false-negative rate dropped from 50% â†’ 0% (14 items re-triaged; 9 recovered to ESCALATE, 5 confirmed correct kills).

## [2026-06-22] New: Sonnet kill-pile audit (audit.py)

Created `audit.py` â€” read-only second-opinion audit that pulls Haiku's recent KILL decisions and asks Sonnet whether each was correct. Per-item output: title, Haiku's kill_reason, and Sonnet's one-sentence verdict side-by-side, so false negatives are immediately visible and actionable. Supports a `sample_size` param for cheap audits at scale. Prints calibration guidance based on false-negative rate (OK â‰¤10%, WARN â‰¤25%, FLAG >25%). Also added `description` to `get_kill_pile()` in db.py. Read-only â€” never mutates item/triage/score state.

## [2026-06-22] New: Haiku triage layer (triage.py)

Created `triage.py` â€” the recall gate that reads un-triaged items and asks Claude Haiku to decide KILL or ESCALATE for each. Core design: Haiku identifies what's safe to discard, not what's important. Fails toward escalation everywhere (parse failure, API error, omitted items all â†’ ESCALATE). KILL criteria are structural only (no substance, non-content, routine triviality, stale rehash) â€” never for topic, niche, or uncertainty. Batches 20 items per call; defensively parses JSON (strips accidental markdown fences, escalates entire batch if unparseable). Prints calibration flag if escalation rate drops below 40%. Added `get_untriaged_items()` to db.py. Verified on 97 live items: 85.6% escalation rate, 0 parse failures, 13s total.

## [2026-06-22] New: RSS ingestion layer (ingest.py)

Created `ingest.py` â€” polls active RSS sources and writes normalized items into the DB via `db.py`. Key behaviors: HTML-stripped descriptions, ISO UTC timestamps, 48h backlog cutoff on first poll of a new source, per-source try/except so one bad feed never kills the run. `poll_all_active()` returns a new/skipped/error summary. `seed_sources()` pre-loads 4 default feeds (BBC World, TechCrunch, Reddit r/popular, Pitchfork). Standalone; not wired into the existing pipeline.

## [2026-06-22] New: SQLite data layer for continuous engine (db.py)

Created `db.py` â€” a standalone SQLite-backed data layer for the planned Haikuâ†’Sonnet continuous pipeline. Not wired into the existing batch pipeline; exists alongside current files for later migration. Five tables: `sources`, `items` (content-hash dedup), `triage` (KILL/ESCALATE audit log), `scores` (1â€“10 with criteria/hook/soft_floor_flags), and `engagement` (behavioral signals from day one). Helper functions: `init_db`, `upsert_source`, `insert_item`, `record_triage`, `record_score`, `log_engagement`, `get_unscored_escalated_items`, `get_kill_pile`, `get_feed`. Standard library only (sqlite3, json, hashlib, datetime). Includes a self-test block verified passing.

## [2026-06-15] Feature: curator self-improvement loop

Added a self-improving editorial memory system. After each run, `load_curator_memory()` checks if `curator_memory.json` is older than 24 hours. If so, `generate_curator_memory()` parses the past 14 days of picks, builds a one-line-per-pick log, and calls Claude Haiku to synthesize a 3â€“5 paragraph prose memo covering calibration anchors (what distinguishes 9s from 10s), framing signals (narrative angles that correlate with high scores), and blind spots (underrepresented topic areas). The memo is injected into every Sonnet scoring run via the cached static preamble â€” between the cross-source trend block and cultural velocity signals. Anti-bias design: the Haiku prompt explicitly forbids topic category or source preferences; the injection header also instructs Sonnet not to let the memo reduce discoverability. Cost: ~$1.50â€“2/month (Haiku analysis once/day; memo rides the existing prompt cache on runs 2 and 3).

## [2026-06-16] Fix: scoring pipeline no longer aborts on transient Anthropic 5xx errors

A run failed mid-scoring (batch 2/5) when Anthropic returned a transient `500 Internal Server Error`. The retry logic in `_score_batch()` (`daily_curator.py`) only retried on status `529` (overloaded); any other `APIStatusError`, including `500`, fell through to `sys.exit(1)` and killed the entire run. Extended the retry condition to cover the standard transient set â€” `500`, `502`, `503`, `529` â€” with the same exponential backoff (up to 4 attempts).

---

## [2026-06-15] Fix: clicking "new picks" banner now actually refreshes the feed

`dismissBanner()` was only hiding the banner without reloading data. Added a `loadFeed()` call so clicking the banner fetches and renders the new picks as expected.

---

## [2026-06-13] Optimization: token efficiency â€” halve breaking-news poll rate, cache Haiku prompt, trim scoring context

Four changes to reduce daily API token spend (~650Kâ€“1.3M tokens/day â†’ ~400â€“800K estimated). (1) **Breaking news cron 5minâ†’10min** (`.github/workflows/breaking_news.yml`): halves the number of Haiku calls from 288/day to 144/day, saving ~144Kâ€“288K tokens/day with at most 5 min added latency to a breaking story. (2) **Prompt cache on Haiku quality gate** (`breaking_news_check.py`, `filter_and_enrich_items()`): the static scoring rubric (~1.5K tokens) is now split out with `cache_control: ephemeral` so calls 2â€“N within the 5-min cache TTL reuse a warm cache â€” saves ~60â€“70% of per-call input tokens. (3) **Trending topics cap 30â†’10** (`daily_curator.py`, `evaluate_articles_with_claude()`): scoring context block now injects only the top 10 trending topics instead of 30; the signal from ranks 11â€“30 is negligible. (4) **Recently-covered window 3 daysâ†’1 day** (`daily_curator.py`, `load_recently_covered_topics()`): the 3-day lookback was loading 40â€“100+ stale entries into every scoring prompt; 1 day captures all the meaningful same-day dedup signal while actual URL dedup is handled separately.

## [2026-06-13] Feature: "Other angles" â€” cross-run duplicates become linked alternatives instead of deletions

Three changes to how same-story duplicates are handled when they span multiple runs. (1) **Within-run dedup prompt**: added an explicit rule that two articles describing different *consequences* of the same event (e.g. "SpaceX stock up 19%" and "Musk becomes trillionaire" are both outcomes of the SpaceX IPO closing) are one story and must cluster â€” Haiku was previously splitting them by subject (company vs. founder). (2) **Cross-run why context**: `load_todays_published_titles()` now returns `{title, why}` dicts instead of bare strings, so the ALREADY IN THE FEED block in `deduplicate_after_scoring()` shows the editorial rationale alongside the title â€” letting Haiku match abstract headlines like "A trillion dollars is a stupid amount of money" to concrete SpaceX IPO articles in the current run. (3) **ALREADY COVERED drops all + merges into primary**: when Haiku groups current articles under "ALREADY COVERED: <title>", ALL of them (including the winner) are now dropped from the current run and merged into the already-published pick's `**Other angles:**` section via a new `_add_to_published_pick_related()` helper â€” previously the winner still appeared in the feed. The `**Folded:** true` marker on a pick tells the deploy script to exclude it from the feed JSON entirely (it survives only as a link in the primary pick's Other angles). `**Other angles:**` is parsed in `deploy-pages.yml` into a `related_articles` array and shown in the expand panel as clickable links.
