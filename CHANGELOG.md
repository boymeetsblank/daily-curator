# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

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

## [2026-04-25] Perf: daily_curator.py — swap detect_cross_source_trends to Haiku (~10x cheaper)

Grouping/clustering task doesn't require Sonnet reasoning. Saves ~$0.27/day (~$0.09/call × 3 runs), extending $10 token budget from ~7 days to ~10 days with no editorial quality impact.

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

