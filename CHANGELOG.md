# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

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
