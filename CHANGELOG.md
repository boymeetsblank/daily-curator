# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-04-21] Update: image_sourcer.py — portrait 4:5 output, stock-photo-only sourcing

**`image_sourcer.py`**
- **Portrait format**: output resized from 1080×1080 to 1080×1350 (Instagram 4:5). Cover-crop logic updated to target the 4:5 ratio; Unsplash and Pexels queries now request `orientation=portrait`.
- **Removed og:image extraction**: copyright risk eliminated. Sourcing chain is now: (1) Unsplash → (2) Pexels → (3) `#F5F5F5` placeholder.
- **Richer keyword prompt**: Claude Haiku is now instructed to produce creative, visually descriptive keywords focused on mood and scene rather than literal names or brands, improving stock-photo relevance.

## [2026-04-21] New: image_sourcer.py — Instagram-ready image sourcing for daily picks

**`image_sourcer.py`** (new standalone module)
- Reads the latest `picks/*.md` (or a path passed as argv), processes every cluster-primary story (one image per unique story, skipping perspective duplicates).
- **4-step sourcing chain**: (1) `og:image` scraped from the article URL via BeautifulSoup — accepted if ≥ 600px on either side; (2) Unsplash API — 2–3 keywords extracted by Claude Haiku from the headline; (3) Pexels API — same keywords; (4) `#F5F5F5` placeholder canvas with Bebas Neue headline text centered.
- **Formatting**: cover-crops to 1:1, resizes to 1080×1080 px, draws a 1 px `#111111` inset border 24 px from each edge, saves as JPEG quality 95.
- Output to `images/YYYY-MM-DD/` named by headline slug (e.g. `nike-air-max-drops-this-week.jpg`). Skips files that already exist so re-runs are safe.
- Bebas Neue font auto-downloaded and cached to `fonts/BebasNeue-Regular.ttf` on first placeholder run.
- Usage: `python image_sourcer.py` (auto-selects latest picks file) or `python image_sourcer.py picks/picks-2026-04-21-1420.md`.

**`requirements.txt`** — added `Pillow>=10.0.0` and `beautifulsoup4>=4.12.0`.

**`.gitignore`** — added `images/` and `fonts/` (local output / font cache, not committed).

## [2026-04-21] Fix: namespace cluster_ids in all_articles/*.json to prevent cross-run collisions

**`daily_curator.py`**
- **`write_all_articles_json()`** — cluster_ids are now prefixed with the run's date-time stamp (e.g., `"c0"` → `"2026-04-21-0730-c0"`, `"trend_0"` → `"2026-04-21-0730-trend_0"`). This makes cluster_ids globally unique across runs.
- **Root cause fixed**: cluster IDs (`c0`, `c1`, `trend_0`, …) were assigned per-run starting from index 0. When `deploy-pages.yml` aggregated all `all_articles/*.json` files into `all_articles.json`, the Feed's `buildFeedView()` incorrectly grouped unrelated articles from different runs that happened to share the same base cluster index — producing bogus "Read N perspectives" toggles and hiding articles as orphaned members of the wrong cluster.
- **No ordering change**: `write_all_articles_json()` was already called after both `detect_cross_source_trends()` and `mark_cluster_primaries()` in `main()` — no reordering was needed.

## [2026-04-21] Fix same-story duplication and broken website clustering

Four root-cause fixes for two persistent issues (same story appearing multiple
times in The Edit; cluster panels not working on the website):

1. **Prune orphaned cluster members** (`daily_curator.py` `main()`) — after
   `filter_already_picked_today()` removes a cluster's primary (already picked
   in an earlier run), non-primary members of that cluster are now explicitly
   dropped. Previously they remained as separate picks with no primary, causing
   them to appear individually in The Edit and breaking website cluster grouping.

2. **Fix false entity clustering for internet abbreviations** (`_STOPWORDS`) —
   "TIL", "AMA", "LPT", "ELI5" and similar Reddit/internet abbreviations are
   now in the stopwords list, preventing `_extract_primary_entity()` from
   treating them as named entities and clustering unrelated posts together.

3. **Richer cross-day dedup context** (`load_recently_covered_topics()`) —
   function now returns "Title — Why summary" strings instead of titles only,
   giving Claude substantially more context to recognise same-story variants
   under different headlines (e.g. ongoing Hormuz/Iran coverage).

4. **JS defensive fallback for missing cluster primary** (`index.html`) — if a
   cluster group has no primary (all members have `cluster_primary: false`),
   `renderPicksGrouped()` now promotes the first/highest-scored member to visual
   primary rather than silently discarding the group.

## [2026-04-20] Save feature — bookmark articles with persistent storage and slide-in panel

**`index.html`**
- **Bookmark button** — a save/unsave button (bookmark SVG) added to every card and row inside `.vote-btns`. Filling the icon on save mirrors the voted-up heart pattern.
- **Topbar saved indicator** — bookmark icon button in `.tb-actions` opens the saved panel; a badge shows the count when ≥1 article is saved.
- **Saved panel** — slide-in panel from the right with a backdrop overlay. Lists saved articles with rarity-tier left-border color coding. Each item shows title, source, score, and a `×` unsave button.
- **`savedMap`** — in-memory `Map<url, articleData>` tracks saved state across the session.
- **`saved.json` on GitHub** — saved state persists via the same GitHub Contents API write pattern used by `votes.json`. `loadSaved()` hydrates `savedMap` on init; `writeSaved()` PUTs on every toggle.
- **localStorage fallback** — saves to `blank_saved` in localStorage when GitHub write is unavailable (dev mode / unauthenticated).
- **`syncSaveButtons()`** — re-applies `.is-saved` class to all `.saved-btn` elements after any state change so buttons stay in sync across list and card views.

**`saved.json`** — new file in repo root, initialized as `[]`.

## [2026-04-20] Inoreader token automation — health check, graceful degradation, auto-secret update

**Backend (`daily_curator.py`)**
- **`InoreaderTokenError` exception** — new exception class raised by `get_fresh_token()` on any token failure instead of `sys.exit(1)`. Allows callers to degrade gracefully rather than aborting the process.
- **`get_fresh_token()` no longer exits** — raises `InoreaderTokenError` on HTTP errors or network failures; caller decides how to handle.
- **`fetch_articles_from_inoreader()` no longer exits** — catches `InoreaderTokenError` and all request errors, logs a `⚠️` warning, and returns `[]` so the run continues on Direct RSS.
- **Token health check in `main()`** — at startup (after `check_setup()`), attempts a token refresh. If it fails, sets `inoreader_available = False`, logs a clear remediation message, and skips all Inoreader fetches for that run without exiting.
- **Graceful degradation in `main()`** — when `inoreader_available = False`, skips parallel Inoreader fetch and `generate_sources_json()`, runs Direct RSS only, and passes `inoreader_unavailable=True` to the output writer.
- **`write_markdown_output()` degradation note** — when `inoreader_unavailable=True`, the picks file header now reads "Direct RSS feeds" as the source and includes a `⚠️ Inoreader unavailable` callout.

**`get_inoreader_token.py`**
- **Auto-updates `.env`** — after a successful token exchange, rewrites `INOREADER_REFRESH_TOKEN` in the local `.env` file in-place (or appends if not present).
- **Auto-updates GitHub Actions secret** — calls the GitHub REST API to update `INOREADER_REFRESH_TOKEN` in repo secrets. Reads or prompts for `GITHUB_PAT` (repo-scope PAT). Detects owner/repo from `git remote get-url origin`; falls back to prompt. Encrypts the secret with the repo's libsodium public key via PyNaCl (required by GitHub API). Saves `GITHUB_PAT` to `.env` for future runs if not already stored. Prints a direct settings URL if automatic update fails.

**New workflow (`.github/workflows/token-health-check.yml`)**
- Runs daily at 6:00 AM CST (`0 12 * * *`) and on manual dispatch.
- Attempts a refresh-token exchange using stdlib only (no pip install needed).
- On success: writes a green ✅ job summary.
- On failure: writes a detailed ❌ job summary with step-by-step remediation instructions and marks the job failed so it appears as a red X in the Actions tab.
- Never attempts to auto-refresh or start a new OAuth flow.

**`requirements.txt`** — added `PyNaCl>=1.5.0`.

## [2026-04-20] Fix: detect_cross_source_trends() now assigns cluster_id — closes frontend grouping gap

**Backend (`daily_curator.py`)**
- **`detect_cross_source_trends()` now assigns cluster fields** — when Claude identifies 2+ articles covering the same story, the function now assigns a shared `cluster_id` (e.g. `trend_0`, `trend_1`), `cluster_size`, and `cluster_sources` to all articles in the group. Previously it only set `trending_across_sources` and `trending_source_count`, meaning Claude-identified multi-source stories were never grouped in the frontend.
- **Existing cluster IDs preserved** — articles that already have a `cluster_id` from `tag_story_clusters()` (algorithmic title/entity clustering) are not overwritten. Only articles without an existing cluster ID receive a `trend_*` assignment.
- **Trending signal unchanged** — the 3+ source `trending_across_sources` / `trending_source_count` bonus still fires for all valid members of 3+ source groups, regardless of cluster ID status.
- **`mark_cluster_primaries()` docstring updated** — clarified that it handles both `c*` (algorithmic) and `trend_*` (Claude-detected) cluster IDs.

## [2026-04-17] Three scoring pipeline optimizations

1. **Prompt caching on scoring batches** — `_build_scoring_prompt()` now returns a `(static_preamble, dynamic_articles)` tuple. `_score_batch()` sends the user message as two content blocks, marking the static preamble (instructions, rules, recently-covered list, trending context) with `cache_control: {type: "ephemeral"}`. With 4 batches per run, this yields 3 cache hits per run, cutting ~61% of the static-portion token cost across batches 2–4.

2. **Hard article cap** — Added `MAX_ARTICLES_HARD_CAP = 200` constant and `apply_hard_article_cap()` function, called in `main()` after per-source capping and seen-URL filtering but before scoring. When the total exceeds 200, the most recently published articles are kept, with a log of how many were trimmed.

3. **Dead code deleted** — `deduplicate_articles_pre_scoring()` was defined but never called; it had been superseded by the local `tag_story_clusters()` function. Removed entirely.

## [2026-04-17] Fix multi-perspective cluster expansion panel

Two fixes to make the cluster expansion panel fully functional:

1. **`deduplicate_after_scoring()` preserves duplicates as perspectives** — instead of deleting losing articles, they are now marked `cluster_primary: False` and assigned the winner's `cluster_id`. The winner also gets a `cluster_sources` list built from all cluster members' sources. All articles are returned so non-primary members reach the picks file and the frontend expansion panel.

2. **`select_top_picks()` includes non-primary members** — selects up to `MAX_PICKS` primary/singleton articles first, then appends non-primary members whose cluster primary was selected, so the full cluster reaches the frontend.

3. **`cluster_sources` wired into JS toggle strips** — both `renderPicksGrouped()` and `buildFeedView()` now render a `.cst-sources` span in the toggle strip when `cluster_sources` is present, showing the contributing sources (e.g. "NYT · ESPN · The Atlantic").

## [2026-04-17] Improve clustering/dedup pipeline

Three fixes to the deduplication pipeline in `daily_curator.py`:

- **Pre-scoring dedup retry** — `deduplicate_articles_pre_scoring()` now retries with a stricter "return only raw JSON" prompt if Claude returns malformed JSON on the first attempt. If both attempts fail, logs a clear `❌` warning instead of silently passing all articles through unfiltered.
- **Post-scoring dedup pass** — new `deduplicate_after_scoring()` runs after `cap_cluster_sizes()` but before `select_top_picks()`. Checks all picks scoring ≥ MIN_SCORE for remaining same-topic duplicates. Keeps the highest-scored version; ties broken by metadata richness (has image, longer summary). Includes retry + clear failure logging.
- **Broader post-scoring prompt** — uses "same underlying event or topic" (vs pre-scoring's "exact same story") to catch sparse-entity matches like two arrest headlines that name the subject differently.

## [2026-04-15] Story clustering v2 — entity clustering, size cap, multi-perspective panel

**Backend (`daily_curator.py`)**
- **Similarity threshold lowered** — `CLUSTER_SIMILARITY_THRESHOLD` reduced from 80% to 65%. Catches more same-story variations with different phrasing while remaining selective enough to avoid false positives.
- **`_extract_primary_entity()`** — new helper that extracts the first 1–3 consecutive title-cased words (company, person, product, event) from an article title, ignoring common English stopwords.
- **`_parse_published_ts()`** — new helper that parses the `"YYYY-MM-DD HH:MM UTC"` published field into a Unix timestamp.
- **Entity-based clustering (second pass in `tag_story_clusters()`)** — after the title-similarity union-find pass, a secondary pass groups articles that share the same primary named entity AND were published within a 6-hour window, regardless of title similarity score.
- **`CLUSTER_MAX_SIZE = 6`** — new constant capping the number of articles kept per cluster.
- **`cap_cluster_sizes()`** — new post-scoring function that trims any cluster exceeding 6 total members, retaining the primary plus the 5 highest-scored non-primaries. Called in `main()` immediately after `mark_cluster_primaries()`.

**Frontend (`index.html`)**
- **Perspective card design** — replaces the old compact `cluster-sub-row` (source · title · time in one line) with a richer `.perspective-card` layout: source name (uppercase), headline as a clickable link, timestamp, and a 2-line clamped summary preview. Consistent with Blank's 1px-border, generous-spacing editorial language.
- **Toggle label updated** — "N sources covering this story" → "Read N perspectives →" in both The Edit and The Feed.
- **The Feed cluster grouping** — `buildFeedView()` now groups Feed articles by `cluster_id` in list view. The highest-scored article in each cluster becomes the Feed primary row, wrapped in a `.cluster-group.feed-cluster-group` div with the same toggle strip + perspectives panel as The Edit. Card view is unchanged (articles render individually).
- **`filterFeed()` updated** — source filter now selects `.feed-cluster-group` wrappers in addition to individual `.feed-row` and `.feed-card` elements, filtering by the primary's source.
- **CSS: feed cluster group** — `.feed-cluster-group` inherits the cluster layout without rarity color treatment; left border uses `var(--border)`.

## [2026-04-14] Phase 1 story clustering — multi-source grouping in The Edit

**Backend (`daily_curator.py`)**
- **`tag_story_clusters()`** — new pre-scoring function that groups articles by fuzzy title similarity (≥ 80% via `difflib.SequenceMatcher`) using union-find. Tags every article with `cluster_id`, `cluster_size`, and `cluster_sources`. Replaces the old `deduplicate_articles_pre_scoring()` Claude call — all cluster members are kept in the scoring batch rather than dropping duplicates.
- **Coverage boost** — clusters with 3+ distinct sources automatically set `trending_across_sources=True` and `trending_source_count` so the scoring prompt's CROSS-SOURCE TREND BONUS applies without a separate Claude call.
- **`mark_cluster_primaries()`** — called after Claude scoring; walks each cluster and marks the highest-scoring article as `cluster_primary=True`. Singletons are always primary.
- **`write_markdown_output`** — picks now include `Cluster ID`, `Cluster Size`, `Cluster Primary`, and `Cluster Sources` metadata lines for persistence and frontend consumption.
- **`write_all_articles_json`** — all_articles entries now carry the same cluster fields so The Feed data is consistent.

**Deploy (`deploy-pages.yml`)**
- `parse_file()` now extracts `cluster_id`, `cluster_size`, `cluster_primary`, `cluster_sources` from each pick block and includes them in `picks_data.json`. Old picks without these fields default to `cluster_primary: true` (backwards compatible).

**Frontend (`index.html`)**
- **`renderPicksGrouped()`** — new list-view renderer that groups picks by `cluster_id` before rendering. Primaries (and singletons) get a full `renderRow()` treatment; non-primaries are hidden from standalone view and attached as sub-rows.
- **`renderSubRow()`** — compact sub-source row: source name (uppercase, muted) · truncated title link · timestamp. No score badge, no rarity glow — intentionally subdued.
- **`toggleCluster()`** — collapses/expands a `.cluster-group` wrapper on the toggle-strip click.
- **Cluster toggle strip** — a thin row below the primary article showing "↓ N sources covering this story" in spaced uppercase faint text. Collapses the sub-list; chevron rotates 180° when expanded.
- **Cluster sub-list** — indented behind a 2px left border in the primary's rarity color (blue / purple / amber), carrying the rarity identity through the expanded list.
- **Coverage badge** — primary rows in clusters of 3+ sources display an accent-colored `N src` badge inline after the title (replaces the old `3+ SRC` fallback badge).
- **`buildSidebar()`** — score filter counts now reflect only primary/singleton picks, not hidden non-primary cluster members.
- The Feed is unchanged — all cluster members render as individual rows without grouping.

## [2026-04-14] Fix: Edit/Feed deduplication hardening — URL normalization and dual-source dedup

- **`normalize_url` enhanced** — now also lowercases the hostname, strips the `www.` prefix, normalises `http://` → `https://`, and strips default ports (`:80`, `:443`). Previously only tracking params and fragments were stripped, meaning `http://example.com/a` and `https://www.example.com/a` were treated as different URLs.
- **`dedup_articles_by_url` now prefers richer metadata** — when the same URL appears from both Inoreader and Direct RSS, the deduplication step now keeps the article version with the most metadata (image present → summary length → source name), rather than always keeping the first occurrence. This eliminates same-article duplicates between the two fetch paths and uses the best available thumbnail/summary.
- **`_get_today_pick_urls()` added** — new helper that reads all normalized pick URLs from today's existing picks files. Called in `main()` before writing `all_articles.json`, so articles that scored highly but were removed by `filter_already_picked_today()` (already in The Edit from an earlier run) are correctly excluded from The Feed.
- **`write_all_articles_json` exclusion count fixed** — now logs the actual number of articles excluded from the JSON file rather than the size of the exclusion URL set.
- **`deploy-pages.yml` `normalize_for_dedup` rewritten** — updated to match the new normalization logic: strips query string, lowercases host, strips `www.`, normalises `http` → `https`. Previously only `split('?')[0]` was applied, leaving `www.` and scheme mismatches unresolved.

## [2026-04-13] Scoring prompt rewrite — sharper criteria and anchors

Replaced the Claude scoring prompt with a tightened editorial brief: cleaner criteria framing, revised scoring anchors with explicit tier descriptions (10 as a rare cultural moment, 6 as "made the cut"), a bidirectional 10/10 rarity rule that penalizes both false positives AND false negatives, and a reframed CATEGORY DIVERSITY RULE that emphasizes editorial breadth over category enumeration.

## [2026-04-13] Fix: Edit picks no longer appear in The Feed

In `deploy-pages.yml`, the `all_articles.json` build step now cross-references all pick URLs from `picks_data.json` and strips any matching articles before writing The Feed. This fixes historical `all_articles/*.json` files generated before the per-run exclusion existed, and acts as a permanent safety net going forward.

## [2026-04-13] Cross-run & multi-day topic deduplication

Added `load_recently_covered_topics()` which reads picks files from the last 3 days and injects the story titles into the Claude scoring prompt. Claude now scores a 1 for any article covering a story already featured recently — preventing same-story duplicates across runs and across days, even when the articles have different URLs and headlines. A nuanced exception allows genuinely significant new developments on an old story (e.g. an arrest, a verdict) to still surface.

## [2026-04-12] Sources full-page overlay — dedicated source management experience

- **Sources page** (`#sources-page`): full-screen overlay that slides up from the bottom, replacing the old sidebar-confined source management. Triggered by the gear icon via `openSettings()` → `openSources()`.
- **Category grouping**: sources are organized into named sections — Sneakers, Watches, Streetwear, Culture, Wide Net, Other — matching the editorial aesthetic. Categories without sources are hidden.
- **Per-source health stats**: each row shows a health dot (green = active last run, yellow = stale, grey = no data, red = failed manual check), last pull timestamp, and avg articles/run — computed from `all_articles.json` without any new backend.
- **Manual ↻ Check button**: validates the source's RSS URL on demand via the existing `spTryFeed()` proxy chain. Dot turns green or red immediately.
- **Search/filter bar**: live filter across name, URL, and category without re-fetching.
- **Compact utility topbar**: Dark/Light mode, notifications, and List/Cards view toggles moved into the sources page header — gear now opens one destination.
- **`applyTheme()`, `initNotifBtn()`, `enableNotifications()`** updated to keep the sources page utility buttons in sync with the sidebar equivalents.

## [2026-04-12] Fix: Reddit RSS parsing — "reddit sub" and "reddit/sub" formats

- **Root cause:** The `spParseInput` Reddit regex only matched `r/sub` and `reddit.com/r/sub`. The patterns `reddit/todayilearned` and `reddit todayilearned` (space-separated) fell through to the bare-domain handler, which produced an invalid URL.
- **Fix:** Replaced the Reddit alternation with `reddit[\s/]+` which covers `reddit/sub` and `reddit sub` (any whitespace or slash after "reddit"). The alternation order ensures `reddit.com/r/sub` is still caught by the `.com/r/` pattern before `reddit[\s/]+` gets a chance to partially match it. All six variants now resolve to `https://www.reddit.com/r/[sub]/.rss`.

## [2026-04-12] Smart RSS discovery + source health indicators

- **Smart input parsing (`spParseInput`):** Detects input type before any network call and constructs the correct RSS URL automatically. Handles: `r/subreddit` or `reddit.com/r/sub` → Reddit JSON feed; `slug.substack.com` → Substack `/feed`; `youtube.com/channel/ID` or `youtube.com/@handle` → YouTube XML feed; bare domain (e.g. `hypebeast.com`) → tries `/feed`, `/rss`, `/rss.xml`, `/feed.xml`, `/atom.xml` in order; direct RSS/Atom URL → validated immediately; generic URL → autodiscovery.
- **Validation chain (`spTryFeed`):** Each candidate URL is fetched via the allorigins.win proxy and tested for RSS/Atom markers. If none of the pattern candidates succeed, the last attempt falls back to HTML `<link rel="alternate">` autodiscovery. The resolved feed URL replaces the input field value. Feed title is auto-populated into the Name field.
- **Real-time type hint (`spHintInput`):** As the user types (debounced 180ms), a small badge appears below the URL input showing the detected input type (e.g. `REDDIT · r/sneakers` or `DOMAIN · Will try /feed, /rss…`). Updates to a green ✓ confirmation or red error after the Detect call resolves.
- **`decodeHtml()` extracted:** Previously defined inline inside `spDetectRss`, now a module-level utility shared across all discovery functions. Handles `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#39;`, `&apos;`.
- **Source health indicators (`spLoadSourceHealth`):** On settings panel open, fetches `all_articles.json` in the background and builds a per-source article count from the most recent run. Each source row in the list now shows a colored dot: green (active — articles appeared in last run) or grey (inactive — source is configured but produced no articles). Tooltip shows exact count. Dots update in place without re-rendering the list.

## [2026-04-12] ROADMAP.md — full rewrite to reflect current state

- Retired all stale "In Progress" and "Major Features" entries — everything listed had already shipped.
- Documented **Shipped** section covering all pipeline, scoring, and frontend work to date.
- **Up Next** section restructured around the core principle: feed quality first, better inputs beat better technology. Aggressive source expansion (8 Reddit subreddits + 3 independent newsletters) listed as the immediate priority before any new infrastructure.
- **Phase 2** section captures the real-time trend pipeline plan with explicit note to decide model via testing, not assumption.
- **Product Decisions — Locked** table captures all resolved product questions: The Edit/Feed naming and roles, landing page headline, feedback loop trigger, story clustering threshold, Zeitgeist and multi-user unlock conditions.
- Stale parked items trimmed.











