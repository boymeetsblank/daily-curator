# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-04-01] Fix cron schedule to correct CST run times

Updated cron times in `daily_curator.yml` to run at 8:30 AM, 1:30 PM, and 7:30 PM CST (UTC-6): `30 14`, `30 19`, `30 1`. Also updated `RUN_TIMES_UTC` in `index.html` to match so the countdown timer counts down to the correct times.

## [2026-03-31] Convert timestamps to CT in web feed

Pick card timestamps were showing raw UTC times, making them appear several hours in the future for CT users.

- **`deploy-pages.yml`**: Switched from naive UTC datetime to `zoneinfo.ZoneInfo('America/Chicago')` conversion. `display_time` now shows CT time with a "CT" suffix (e.g. "8:00 AM CT"). `display_date` and `label` (Morning/Afternoon/Evening) are also derived from the CT hour, so the 9 PM CT run (02:00 UTC next day) now correctly shows as Evening, not Morning. Added `ct_date` field to each run (the CT calendar date) for grouping.
- **`index.html`**: Run grouping logic ("today vs. earlier") now uses `run.ct_date` instead of `run.date` (UTC filename date), so the 9 PM CT run groups with the correct CT day rather than the next UTC day.
## [2026-03-30] Fix X logo in trending ticker

Replaced the styled `<span>` letter "X" in the ticker strip with the official X (Twitter) inline SVG mark (`viewBox="0 0 24 24"`). Updated CSS class from `.ticker-x` to `.ticker-x-logo` with proper `width`/`height`/`color` sizing.

## [2026-03-30] Introduce "Blank" wordmark in header

Replaced `@boymeetsblank_` handle with the product name **Blank** and redesigned the wordmark typographically:

- **Wordmark**: `Blank` rendered in all-caps via `text-transform: uppercase`, `letter-spacing: 0.22em`, `font-weight: 400`, `font-size: 13px` — tracked sans-serif in regular weight. The architectural spacing makes five letters feel like a designed mark rather than typed text. Regular (not bold) weight is intentional: confidence through restraint.
- **Tagline**: Retained as italic Georgia `font-size: 10.5px`, `color: var(--ink-4)` — the warm humanist serif beneath the cold geometric wordmark creates deliberate typographic contrast that mirrors the product's identity (sharp curation + cultural depth)
- **Brand-block gap**: increased from `3px` to `5px` to give the tracked wordmark proper breathing room above the tagline
- **`<title>`** and **`og:title`** updated to `Blank — Daily Picks`

## [2026-03-30] Remove time-of-day filter pills — flat reverse-chronological feed

Replaced the Morning/Afternoon/Evening filter system with a simple reverse-chronological stream:

- **Removed from HTML**: the three `.filter-btn` pill buttons (`Morning`, `Afternoon`, `Evening`) from the filter bar
- **Removed from CSS**: `.filter-pills` and `.filter-pills .pill-btn` rules; `.filter-hidden` utility class; `.sb-jump-btn` / `.sb-jump-arrow` sidebar styles
- **Removed from JS**: `filterLabel` variable; `applyFilters()` function; filter-btn click listeners; `renderRunGroup()` function; `jumpToLabel()` function; sidebar Jump-to section
- **Updated `render()`**: today's picks are now flattened into a single `#section-latest` container — runs iterate newest-first (already sorted that way), picks within each run render in order, producing a reverse-chronological stream with no grouping dividers
- **Updated `updateCount()`**: now queries `#section-latest .pick-card` directly (no filter-hidden logic needed)
- **Updated stagger selectors**: `#section-latest .pick-card:nth-child(n)` replaces the old `.run-group .pick-card:nth-child(n)` — stagger now applies across the full flat stream
- **Kept**: date label, pick count, Today/Archive scroll buttons, timer, all card rendering logic

## [2026-03-30] Fix thumbnail cropping permanently — variable height at natural aspect ratio

Replaced the fixed-height `object-fit: cover` image container with a variable-height approach that displays images at their natural aspect ratio:

- **`.card-image-wrap`**: Removed `height: 220px`. Now uses `max-height: 360px` + `overflow: hidden` as the only size constraint. The container grows to fit the image rather than forcing the image to fill a fixed box.
- **`.card-thumbnail`**: Changed `height: 100%` → `height: auto` so images render at natural proportions. `max-height: 360px` matches the container cap; `object-fit: cover` + `object-position: center 25%` only activates as a fallback when a portrait image exceeds the cap.
- **Reasoning**: 360px was chosen because the most common og:image format (1200×628, ≈1.91:1) renders at ~366px at 700px container width — meaning standard article images display completely uncropped. Wide images display shorter; portrait images are capped and covered from the top 25%.
- **`object-fit: contain` rejected**: Creates letterboxing bars of varying widths depending on image aspect ratio — inconsistent and harder to make look intentional than variable-height natural display.
- Removed mobile `height: 185px` override — no longer needed since there is no fixed height to override.

## [2026-03-30] Fix article thumbnail image cropping

Two targeted CSS fixes to make card images look editorial rather than awkwardly cropped:

- **`object-position: center 25%`** on `.card-thumbnail` — anchors the visible crop to the upper portion of the image rather than the default `center center`. Editorial article photography places subjects, faces, and action in the upper half of frame; `25%` vertical position captures them without risk of clipping header text that sometimes sits at the very top edge of og:images
- **Bottom-fade gradient overlay** via `.card-image-wrap::after` — a `transparent → rgba(255,255,255,0.18)` gradient over the bottom 52px of the image eliminates the harsh hard-cut between image and card body. Requires `position: relative` on `.card-image-wrap`, which was added

## [2026-03-30] Redesign index.html — Contemporary Editorial aesthetic (frontend-design skill)

Full redesign using the frontend-design skill with a committed aesthetic direction: **Contemporary Print Editorial** — the visual language of a premium culture magazine's digital presence, not a social app.

**Aesthetic decisions:**
- **Georgia serif for all article headlines** — the single most distinctive choice; gives editorial authority without importing any external font; also applied to archive titles, trend source labels, tagline, sidebar stats, and the loading state — creating a unified reading surface throughout
- **CSS custom properties** (`--serif`, `--sans`, `--ink`, `--amber`, etc.) as the design system backbone
- **Warm off-white page** (`#fafaf8`), pure white cards, near-black ink (`#1c1917`), amber `#d97706` for high scores (9–10)
- **Tagline set in italic Georgia** — small, understated, but immediately signals editorial intent
- **Sidebar stats in Georgia numerals** — large, quiet 26px figures that feel like a masthead rather than a dashboard

**Motion:**
- Staggered `fadeUp` entry animation on all cards: 60ms offset per child, `cubic-bezier(0.16, 1, 0.3, 1)` spring curve — cards populate with rhythm
- Card hover: `translateY(-2px)` lift + soft shadow + image scales 1.04×
- Read link uses a growing `::after` underline on hover (width 0→100%) — print-native feel, not a color change
- Arrow on read link translates right 3px on hover

**Ticker:** Dark `#1c1917` strip with italic serif `X` label, scrolling pills, fade gradients at both edges, animation pauses on hover

**Removed:** Carousel hook / angle / psychological trigger labels entirely

**Preserved:** Score badge, source (small-caps), headline, why it matters, read link, feedback arrows, sidebar, filter bar, mobile timer, all filtering logic

## [2026-03-30] OG image fallback via concurrent HTTP fetch

Added `enrich_articles_with_og_images()` as a post-processing step after `fetch_articles_from_inoreader()`. For any article that has no image URL from the three existing RSS sources (Inoreader `visual.url`, first `<img>` in summary HTML, `enclosure.href`), the function fetches the article's URL and parses the `<meta property="og:image">` tag as a fallback.

Implementation details:
- **Concurrent:** uses `ThreadPoolExecutor` (up to 10 workers) so all missing-image articles are fetched in parallel — wall-clock cost is approximately one 5-second timeout, not N×5 seconds
- **Timeout:** hard 5-second timeout per request via `requests.get(..., timeout=5)`; any slow or unresponsive site is simply skipped
- **Graceful failure:** all exceptions are caught and suppressed; on failure the article's `image` field stays `None`
- **Attribute-order safe:** regex matches `og:image` meta tags with either attribute order (`property` before `content` or vice versa), handles both single and double quotes
- **Efficient:** reads only the first 50 KB of each response since `<meta>` tags are always in `<head>`
- **Fallback only:** skips articles that already have an image from the RSS feed, so existing image sources are unaffected
- Added `import re` and `from concurrent.futures import ThreadPoolExecutor, as_completed` to top-level imports

## [2026-03-30] Redesign index.html — light editorial theme with X trending ticker

Complete visual redesign of the web feed:

- **Color scheme:** Warm off-white page background (#f5f4f0), clean white cards and header — replaces dark theme
- **Prominent images:** Card-image-wrap (216px desktop / 180px mobile) is the first element on each card; images scale subtly on card hover; broken images hide gracefully via onerror handler
- **X Trending ticker:** Dark (#111) sticky strip pinned below the header shows today's X trending topics as scrolling pills with a CSS `@keyframes` animation. Animation pauses on hover. Duration scales with topic count. Strip auto-hides if no X trends are available
- **Removed:** Carousel hook angle box and psychological trigger label entirely from all card displays
- **Kept:** Score badge (amber tint for 9–10), source in small-caps, headline, "why it matters", read link with animated arrow gap, up/down feedback buttons
- **Score badge:** `#1a1a1a` default; `#c2410c` amber-orange for scores 9–10
- **Card hover:** Subtle lift (`translateY(-2px)`) and soft shadow; thumbnail scales 1.025x
- **Sidebar (≥1100px):** Updated to match new palette — Today stats, Jump to, Top pick this week, Sources today
- **Typography:** System font stack throughout, tighter letter-spacing on titles, muted gray secondary text
- **Mobile:** 520px breakpoint, reduced image height, mobile-timer-row preserved
- **OG meta tags:** Added `og:title`, `og:description`, `og:type` for clean social sharing
- **positionSticky():** Now accounts for optional ticker height when positioning filter bar and sidebar

## [2026-03-30] Add APIFY_API_TOKEN to daily_curator.yml env

Added `APIFY_API_TOKEN: ${{ secrets.APIFY_API_TOKEN }}` to the "Run Daily Curator" step env block so Apify trend fetching works in GitHub Actions.

## [2026-03-30] Update CLAUDE.md with Platform Vision, Git Workflow, and Feature Roadmap

Added three new sections to CLAUDE.md:
- **Platform Vision** — documents the core mission (daily briefing tool, not a content creator tool), unique angle (natural language setup, AI editorial judgment, cross-platform signals, intentionally finite), and long-term goal of a no-code public curation platform
- **Git Workflow** — explicit rule to always commit and push to `main`, never to other branches unless instructed
- **Planned phases** — Phase 5 Platform (natural language feed controls, dynamic source library, public platform), Breaking News Mode (30–60 min watchdog, one pick, $15–30/month), and always-show X trending topics section in the feed

## [2026-03-26] Fix three crash bugs in fetch_articles_from_inoreader and evaluate_articles_with_claude

Three AttributeError/KeyError bugs found and fixed during end-to-end code review:

1. **`origin` None crash** — `item.get("origin", {})` returns `None` when the key exists but its value is null (the default only fires for absent keys). Changed to `item.get("origin") or {}` so a null origin safely falls back to an empty dict.
2. **`summary_obj` type crash** — `summary_obj.get("content", "")` assumed the field is always a dict, but Inoreader can return it as a plain string. Changed the guard from `if summary_obj` to `if isinstance(summary_obj, dict)` to prevent AttributeError on string values.
3. **`eval_by_number` KeyError** — The dict comprehension `{e["article_number"]: e for e in evaluations}` would crash if Claude returned an evaluation missing the `article_number` key. Added a `.get()` check to skip malformed entries.

## [2026-03-26] Fix enclosure AttributeError in fetch_articles_from_inoreader
Inoreader's `enclosure` field can be a list instead of a dict. Calling `.get("href")` on a list throws an `AttributeError`. Fixed to handle all cases: if enclosure is a list, take the first item; if it's a dict, call `.get("href")` directly; otherwise set image to `None`.

## [2026-03-26] Fix duplicate timer on mobile
`#next-run` was not included in the mobile hide rule, so the countdown appeared twice — once in the filter bar and once in the compact mobile row. Added `#next-run` to the `display: none` rule at ≤520px so only the `.mobile-timer-row` shows on mobile.

## [2026-03-25] Show timer on mobile
Added a compact `.mobile-timer-row` div inside the sticky filter-bar that shows only on screens ≤520px. It displays "Updated Xm ago · Next in Xh Xm" on a single line in small muted text, populated by the same `tickCountdown` function that drives the desktop timer. The desktop filter-bar elements (`#last-updated`, `.run-meta-sep`) remain hidden on mobile as before.

## [2026-03-25] Update cron schedule to correct run times
Updated `.github/workflows/daily_curator.yml` and `RUN_TIMES_UTC` in `index.html` to the correct schedule: 13:00 UTC (8:00 AM CT), 18:00 UTC (1:00 PM CT), 02:00 UTC (9:00 PM CT). The "Next in Xh Xm" countdown in the feed header now counts to these times.

## [2026-03-25] Fix cron schedule and improve header timer display
**Cron fix:** Updated `.github/workflows/daily_curator.yml` run times to match actual schedule — 11:30 UTC (6:30 AM CT), 21:30 UTC (4:30 PM CT), 03:30 UTC (10:30 PM CT). Previous times were wrong.

**Timer redesign:** Replaced the single next-run countdown in the filter bar with two pieces of information shown side by side: "Updated Xm ago" (derived from the most recent run's timestamp in `picks_data.json`) and "Next in Xh Xm" (countdown to the next scheduled run using the corrected UTC times). Both hide on mobile (≤520px) to preserve space. The `lastRunTime` is parsed from `runs[0].date` + `runs[0].time` (UTC) after the feed loads and refreshes every minute alongside the countdown.

## [2026-03-25] Recency boost in Claude scoring prompt
Updated the TIMELY criterion in `evaluate_articles_with_claude()` to instruct Claude to apply explicit recency weighting using the Published timestamp already included in each article: articles published within the last 12 hours get a +1 boost; articles 12–24 hours old score normally; articles 24–48 hours old get a -1 penalty unless the story is still actively developing or trending.

## [2026-03-25] Pre-scoring topic deduplication
Moved same-topic deduplication from after Claude scoring to before it. New `deduplicate_articles_pre_scoring()` runs after the source cap and before `detect_cross_source_trends()`. Claude clusters the full article list by topic and keeps the single most culturally relevant representative per cluster (chosen by source quality, not score, since no scores exist yet). Removed the post-scoring `deduplicate_within_run()` step — it's no longer needed since topics are already unique before scoring. Cross-run URL filtering (`filter_already_picked_today()`) is unchanged. Net effect: Claude always receives the maximum number of unique topics to evaluate, which produces more diverse picks.

## [2026-03-25] Article thumbnail images on pick cards
Extracts a thumbnail image URL from each Inoreader article and displays it at the top of pick cards in the web feed. Extraction checks three sources in order: (1) Inoreader's `visual.url` field, (2) the first `<img>` src tag in the summary HTML, (3) the RSS `enclosure.href`. The URL is saved to the picks markdown file as `**Image:** url`. `deploy-pages.yml` parses the field into `picks_data.json`. In the feed, cards with an image show a full-width thumbnail (max 200px tall, `object-fit: cover`, rounded top corners) that bleeds to the card edges. Trend items (X/Google) have no image and render unchanged. Images that fail to load are hidden silently.

## [2026-03-25] Fix deploy-pages not triggering after Daily Curator runs
Added a `workflow_run` trigger to `deploy-pages.yml` so the feed deploys automatically whenever the "Daily Curator" workflow completes successfully on `main`. The job is conditional (`conclusion == 'success'`) so failed curator runs don't trigger a deploy. Push and `workflow_dispatch` triggers are preserved.

## [2026-03-24] Fix countdown timer visibility on mobile
Moved the next-run countdown from the header (where it was hidden on mobile via `display: none` to prevent overflow) into the filter bar right side. It now sits in a `.filter-right` flex group alongside the pick count, visible at all screen sizes. On mobile (≤520px) the pick count is hidden to save space, keeping the countdown readable. The header-actions now contains only the Today/Archive pill buttons.

## [2026-03-24] Fix sidebar "Top pick of the week" rendering
Fixed two visual bugs in the sidebar top pick card: (1) the `<a>` wrapper tag defaulted to `display: inline`, causing a stray left-border artifact below the date — fixed by adding `display: block` to `.sb-top-pick`; (2) the score badge was a block-level `div` — replaced with an inline `<span class="score-badge">` matching the card badges exactly. Also added `overflow-wrap: break-word` to the title and removed the redundant `style="text-decoration:none"` inline attribute.

## [2026-03-24] Fixed right sidebar on wide screens
Added a sticky 240px sidebar to `index.html` that appears on screens ≥ 1100px. The page layout becomes a flex row (944px max-width) so the main feed and sidebar sit side by side. The header and filter bar inner containers expand to match. Sidebar sections populated from picks data via JS:
- **Today's stats** — total picks, top score, and run count for the day
- **Quick jump** — Morning / Afternoon / Evening scroll buttons (grayed out if that run hasn't happened yet)
- **Trending now** — X and Google trending topics from today's picks, grouped by platform
- **Top pick of the week** — highest-scored pick from the last 7 days with headline, score, and date
- **Source breakdown** — per-source pick counts for today, sorted by volume

## [2026-03-24] Dark mode + countdown timer
Reverted the web feed to a dark color scheme (#0a0a0a background, light text) while keeping the new clean layout. Also added a next-run countdown timer in the header showing hours and minutes until the next scheduled curation run (8:30 AM, 3:30 PM, 8:30 PM CT). The countdown updates every minute and is hidden on small screens.

## [2026-03-24] White canvas redesign of index.html
Complete visual redesign of the web feed. Key changes:
- White background, light mode only (no dark mode)
- System sans-serif font replacing Inter from Google Fonts
- Max-width narrowed to 680px centered
- Sticky header with brand + tagline stacked on left, Today/Archive pill buttons on right
- Filter bar (sticky below header): date label, Morning/Afternoon/Evening pills, pick count
- Pick cards: 0.5px border, score badge (black pill, number only), source + optional "3+ sources" badge, timestamp, 2px black left-border angle box, "Read article →" link, up/down feedback buttons
- Trending items show "Trending on X right now" or "Trending on Google right now" instead of a link
- Archive section replaced with a simple "Earlier" list of rows (title, score + date)
- Removed sidebar, next-run countdown widget, and dark color scheme entirely

## [2026-03-24] Next-run countdown timer in header
Added a live countdown to the header showing time until the next scheduled curation run. Counts down to the nearest of the three daily UTC run times (14:30, 21:30, 02:30). Displays as `Xh XXm` when hours remain, `Xm XXs` when under an hour. The dot pulses green when under 5 minutes. On small screens the "Next run" label is hidden to save space, leaving just the dot and time.

## [2026-03-23] Fix X (Twitter) trends — country must be numeric ID
The `karamelo/twitter-trends-scraper` actor's `country` field takes a numeric string ID, not a name. Changed input to `{"country": "2", "live": true}` (`"2"` = United States). This resolved the 400 Bad Request errors.

## [2026-03-23] Sidebar navigation and filtering for the web feed
Added a sticky sidebar to `index.html` with five controls:
- **Jump to Today / Yesterday** — smooth-scrolls to the latest section or the most recent archived date
- **Time of Day filter** — toggles to show only Morning, Afternoon, or Evening runs (across both the latest and archive sections)
- **Score filter** — toggles to show only 9+ or 7+ picks
- **Show All** — resets all active filters
On desktop (>820px) the sidebar sits to the left of the feed as a sticky column. On mobile it collapses into a horizontally-scrollable filter bar pinned below the header. Filtering works by tagging rendered elements with `data-label` and `data-score` attributes and toggling a `filter-hidden` class.

## [2026-03-23] GitHub Pages feed — index.html + deploy-pages.yml
Added a dark-mode editorial web feed hosted on GitHub Pages:
- **`index.html`** — fetches `picks_data.json` and renders a scrollable feed. Today's (most recent date's) picks appear as full cards with score badge, source, headline, why it scored, carousel angle, and article link. Older picks are grouped by date in a condensed archive list. Score badges are green for 9–10, amber for 7–8. The new `[TRIGGER: X]` angle format renders as stacked hook lines; old angle format renders as plain text.
- **`.github/workflows/deploy-pages.yml`** — triggers on every push to `main`. Inline Python parses all `picks/*.md` files into `picks_data.json`, copies both files to a `site/` folder, then deploys to GitHub Pages using `actions/upload-pages-artifact` and `actions/deploy-pages`. The feed auto-updates after every curation run.

## [2026-03-23] Improved Carousel Hook Quality in Claude Scoring Prompt

Updated the `ANGLE` instruction in the Claude evaluation prompt to produce structured, scroll-stopping hooks instead of generic angles.

- The ANGLE field now requires Claude to identify the psychological trigger driving the hook (Curiosity, FOMO, Disbelief, Defensiveness, Relief, or Greed)
- Hooks must be written with intentional line breaks using "/" to indicate slide breaks
- Each line is capped at 7 words; maximum 3 lines total
- Output format: `"[TRIGGER: Disbelief] The last Laker to score 60 / was Kobe. / In his final game."`

## [2026-03-22] Apify integrations — X (Twitter) Trends and Google Trends
Added two new content streams that are scored by Claude alongside Inoreader articles:
- **`fetch_twitter_trends()`** — calls Apify actor `karamelo/twitter-trends-scraper` for live US trending topics. Source: "X (Twitter) Trending".
- **`fetch_google_trends()`** — calls Apify actor `apify/google-trends-scraper` for US trending searches. Source: "Google Trends".
Both use a two-step Apify pattern (start run → poll until done → fetch dataset). Both fail gracefully if Apify is unavailable. Added `APIFY_API_TOKEN` to required credentials. In the picks file, trend items display "Trending on X right now" or "Trending on Google right now" instead of an article link.

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
