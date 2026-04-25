# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-04-24] Feat: daily_curator.py — cross-run cluster persistence via today_clusters.json

Three new functions: `load_today_clusters()` (midnight CST reset), `save_today_clusters()`, and `merge_cross_run_clusters()` (keyword-overlap matching, ≥3 words). Articles matched to prior-run clusters inherit their cluster_id; updated clusters emit `**Updated:** true` in the markdown output. Resets daily at midnight CST via pytz/zoneinfo.

## [2026-04-24] Refactor: daily_curator.py — rank The Edit by cluster score, not individual score

`select_top_picks()` now sorts by cluster score (average of all member scores, rounded to 1dp) so a multi-source cluster outranks a solo article with a slightly higher individual score. Tie-break: cluster size desc, then individual score desc. Displayed scores in output are unchanged.

## [2026-04-24] Update: digest_publisher.py — text-only slide: remove rarity badge, use Substack copy

For imageless slides (Reddit posts, etc.): removed LEGENDARY/EPIC/TOP PICK rarity badge from top-right; replaced short "why it matters" sentence with the Claude-generated Substack paragraph (6-line max) for richer editorial body copy.

## [2026-04-24] Update: digest_publisher.py — full-day picks, bigger fonts, richer text-only slide

Three improvements: (1) digest now collects all picks files for today (`picks-YYYY-MM-DD-*.md`) and selects the top 5 by score across all runs instead of only the latest file. (2) Headline fonts bumped +20%: image slide Bebas 84px→100px, body Inter 19px→23px; text-only Bebas 76px→91px, body Inter 16px→19px. (3) Text-only fallback slide background replaced — dark vertical gradient (#1c1c1c→#080808) + 4% film grain + subtle score-color wash at bottom instead of flat #111111.

## [2026-04-24] Fix: index.html — show list mode thumbnails on mobile

Restored thumbnail column on mobile (≤680px): updated `.art-row` and `.list-header` grid templates to `auto 1fr auto 32px`, replaced `display: none` on `.art-thumb-cell` with 52×52px dimensions for compact mobile sizing.

## [2026-04-23] Feat: index.html — 72×72 thumbnail in List mode story rows

Added a square `object-fit: cover` thumbnail (2px border-radius) in grid column 3 of each `.art-row`, sourced from `pick.image`. Gracefully absent when no image exists; hidden on mobile via `display: none`.

## [2026-04-23] Fix: index.html — add bottom margin to expanded cluster groups in List mode

Added `margin-bottom: 24px` to `.cluster-group.expanded` so perspective rows don't crowd the next story card when a cluster is open.

## [2026-04-22] Fix: digest_publisher.py — styled text-only fallback slide for imageless stories

When `img_data is None`, `render_story_slide()` now renders a purpose-built dark editorial layout instead of a broken gradient-over-black screen. Text block (headline + divider + why) is vertically centered; outer 1px border at 20% opacity; Bebas 76px / Inter 16px; source pinned 72px from bottom; Editor's Pick badges and accent bar preserved.

## [2026-04-22] Update: digest_publisher.py — larger hook and body copy fonts for social readability

Increased hook headline font from Bebas Neue 76px → 84px and "Why it matters" body copy from Inter 16px → 19px to improve legibility when uploaded to social media.

## [2026-04-22] Update: digest_publisher.py — full-bleed editorial redesign + font fix + face-safe crop

**Font loading** — Google Fonts now serves only woff2 for all UAs, which Pillow/FreeType cannot read. Replaced CSS-parsing approach with direct GitHub raw URL downloads (`_fetch_font_direct`). Bebas Neue from `dharmatype/Bebas-Neue` repo; Inter from `google/fonts` repo as variable font (`Inter[opsz,wght].ttf`). Added `_is_valid_font()` validation (checks magic bytes) that auto-deletes and re-downloads corrupted cached files on next run. `_load_inter_medium` now delegates to `_load_inter` (same variable font file). Fixed `&amp;` HTML entity in source attribution via `html.unescape()`.

**Full-bleed editorial layout** — story slides redesigned from split image/white-box to full-bleed image (1080×1350) with a dual gradient overlay: top-bar fade (40%→transparent over 120px) for badge readability, bottom ease-in gradient (GRAD_START_Y=500 → 92% dark at bottom) for text legibility. All text is white at varying opacities over the gradient. Removed `IMAGE_H`, `TEXT_Y` constants; added `GRAD_START_Y`, `TEXT_BOTTOM_PAD`. New `_gradient_overlay()` helper draws the overlay as a pre-composited RGBA layer.

**Story slide text zone** — rebuilt bottom-up: source (VIA ..., Inter 12px, white 55%, y=bottom−72) → why-it-matters (Inter 16px, white 80%, 1.55 lh, 3 lines max) → 60px divider (white 25%, 2px) → headline (Bebas 76px, white, 2 lines max). Category badge (white 70%) top-left; rarity badge in rarity color top-right. Left accent bar (4px, full height) for Editor's Pick.

**Cover slide** — added "BLANK" wordmark (Inter 13px, white 55%) top-left. Overlay increased to 55%. Thin centered rule (80px, white 30%) between date and subline. Subline tracked at +6px (was +4px).

**Face-safe cropping** — `_smart_crop()` gains `prefer_top: bool = False` parameter. When `True`, vertical crop anchors to the top of the image (offset=0) instead of entropy-seeking. All story and cover slides now pass `prefer_top=True`, ensuring portrait photos show faces/heads rather than entropically-selected mid-sections.

**Hook headlines** — slides now use the `**Hook:**` field from the picks file as the headline instead of the raw article title. The `[TRIGGER: ...]` prefix is stripped; ` / ` delimiters become explicit line breaks. Falls back to word-wrapped article title when no hook is present. `parse_picks()` now extracts `hook_lines: list[str]`.

**Why it matters body copy** — slide body text is now sourced directly from `pick["why"]` (the picks file "Why it matters" section) rather than the Claude-generated `why_slide`. Provides more substantive editorial context per slide.

## [2026-04-21] Update: digest_publisher.py — WSJ Magazine slide redesign + Google Fonts fix

**Font downloading** — replaced broken GitHub raw URLs with a Google Fonts API approach. `_fetch_gfont()` hits `fonts.googleapis.com/css2` with a desktop User-Agent (which forces TTF response), parses the `url()` from the CSS, and downloads the file. Added Inter Medium (wght 500) alongside Inter Regular. Fonts cached locally after first download; failed downloads fall back to PIL default silently.

**Cover slide redesign** — full-bleed Editor's Pick image (entropy-cropped to 1080×1350), 45% black overlay for legibility, Bebas Neue date at 180px centered with +200 tracking (36px/char), Inter Medium subline at 18px in white 80% opacity with 4px letter tracking, 1px white border at 60% opacity inset 20px. Dark background fallback when no image.

**Story slide redesign (WSJ Magazine standard)** — image area is now 1080×620px (was half of 1350); text area 730px. 1px separator rule at image/text boundary. Text area layout: category tag (Inter Medium 11px, #888888, all caps, 6px tracking) → 8px gap → Bebas 72px headline leading 1.0, max 3 lines with ellipsis → 20px gap → 40px editorial divider rule #DDDDDD → 20px gap → why it matters (Inter Regular 15px, #444444, leading 1.6, max 2 lines) → source attribution pinned 40px from bottom ("VIA SOURCE", Inter Medium 12px, 4px tracking). 1px text-area border inset 20px. No centered text, no shadows, no gradients.

**Editor's Pick** — 3px flush-left accent border in rarity color spanning full text area height. Rarity label top-right (Inter Medium 10px, 6px tracking). All other slides strictly B&W.

**Letter spacing** — new `_draw_tracked()` renders each character individually with configurable per-character spacing. New `_truncate_lines()` clips overflow with ellipsis.

**Cover sourcing** — images now sourced for all 5 stories before any slide renders; cover passes Editor's Pick image directly to `render_cover()`.

## [2026-04-21] Update: digest_publisher.py — entropy-based smart image cropping

**`digest_publisher.py`**
- Replaced center-crop with entropy-based smart cropping (`_smart_crop` + `_entropy_offset`).
- Images are first scaled to cover the 1080×675 target, then the excess dimension is cropped by finding the contiguous 32px-block window with the highest total entropy — keeping the most visually significant region in frame rather than blindly centering.
- No change to output dimensions or JPEG quality.

## [2026-04-21] New: digest_publisher.py — Daily Digest with Auto-Sourced Images

**`digest_publisher.py`** (new standalone module)
- Runs automatically after the 7:30PM CT (00:30 UTC) pipeline via a new GitHub Actions step.
- Selects the top 5 stories from the latest `picks/*.md` (cluster primaries, ranked by score).
- **Editor's Pick** — highest-rarity story (score 10=Legendary/#3B82F6, 9=Epic/#8B5CF6, otherwise Top Pick/#F97316). Ties broken by Claude Sonnet on cultural weight.
- **Claude Sonnet copy** — one API call generates: cover subline (≤5 words), per-story category tag, Instagram/TikTok/Threads/Substack copy, and a one-line slide caption.
- **Image sourcing** per slide: pre-scraped og:image from picks file → BeautifulSoup re-scrape → Unsplash API → Pexels API → placeholder.
- **6 slides** output to `digests/YYYY-MM-DD/`:
  - `slide_00_cover.jpg`: white canvas, Bebas Neue date ("APR 21"), Claude-generated subline, 1px border.
  - `slide_01–05.jpg`: top 1080×675 sourced image; bottom 1080×675 text area (category, Bebas headline, source, why-it-matters, 1px bottom rule). Editor's Pick slide adds 3px left accent in rarity color + rarity label top-right.
- **`digest.md`**: full platform copy for all 5 stories in markdown.
- Canvas: 1080×1350px, JPEG quality 95. Fonts: Bebas Neue + Inter (auto-downloaded to `fonts/`).

**`.github/workflows/daily_curator.yml`** — added two steps (digest publish + digest commit) gated to the 7:30PM CT (00:30 UTC) run. Digest step uses `|| echo` to skip gracefully on failure without blocking the workflow.

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

















