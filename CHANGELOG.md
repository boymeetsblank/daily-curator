# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-04-11] Fix: The Feed — source label standardization, fixed column width, card view

- **Source label standardization:** All source names in The Feed now render identically regardless of length or content — 10px / weight 600 / 0.09em tracking / uppercase. "Artificial Intelligence", "popculturechat", "The Atlantic" and "WIRED", "ESPN", "CNBC" are visually identical in format.
- **Fixed source column width:** `.feed-source-cell` is now a strict 140px column (`width/min-width/max-width: 140px`) with `text-overflow: ellipsis` for truncation. Every article title in The Feed now starts at exactly the same horizontal position regardless of source name length. The Feed list-header was updated to match (`140px 1fr 32px`).
- **Card view in The Feed:** The List/Card toggle now applies to The Feed as well as The Edit. Added `renderFeedCard()` — a source-first card layout with thumbnail, source badge, timestamp, headline, and summary — rendered consistently with The Edit's card view. `buildFeedView()` conditionally renders cards or rows based on `currentView`. `setView()` now rebuilds The Feed when the view changes. `filterFeed()` updated to cover `.feed-card` elements in addition to `.feed-row`.

## [2026-04-11] Polish: The Feed view — source labels, title wrapping, sidebar, NL bar

- **Source label casing:** Removed `text-transform: uppercase` from `.feed-source-cell`. Sources now render in their native casing — "Hypebeast", "r/nba", "WIRED", "The Atlantic" — so Reddit subreddits (`r/nba`, `r/artificial`) are no longer rendered as `R/NBA`. Font adjusted to 11px / weight 500 / tight tracking for legibility at mixed case.
- **Multi-line title wrapping:** Added `align-self: start` to `.feed-source-cell`, `.feed-row .art-title-cell`, and `.feed-row .expand-btn`. When a title wraps to 2+ lines the source name and expand button now pin to the top of the row instead of floating awkwardly to the vertical midpoint.
- **Sidebar header:** Removed the redundant `/ SOURCES` section label from the Feed sidebar. "All Sources" as the first item is self-explanatory; the label added noise without adding meaning.
- **NL filter placeholders:** Replaced wordy "filter by source or category…" / "filter by source, score, or category…" with example-driven copy: `e.g. sneakers, tech, reddit` (Feed) and `e.g. sneakers, 9s & 10s, tech` (Edit). The `/` prefix already implies filtering; the placeholder shows what to type, not how to use it.

## [2026-04-11] Fix: JS syntax error in renderCard — stray backtick breaking all functionality

- **Bug:** `renderCard()` had a stray backtick at the end of the `return` statement's first line (`...data-source="...">\``). This prematurely closed the template literal after just the opening `<div>` tag. The remaining 22 lines of HTML inside the template were left as raw invalid JavaScript, causing `Uncaught SyntaxError: Unexpected token '{'` on every page load.
- **Impact:** The syntax error prevented the entire script block from executing, which is why both The Edit (no articles) and The Feed pill toggle (no mode switch) were completely broken.
- **Fix:** Removed the stray closing backtick from line 1661 so the template literal correctly spans from the opening `<div>` to the closing `</div>` on line 1684 — matching the same pattern as `renderRow()`.

## [2026-04-11] Fix: The Feed pill still not switching — display override bug

- **Root cause:** `feedPage.style.display = ''` clears the inline style, which lets the CSS rule `#feed-page { display: none }` win — so The Feed page was never actually becoming visible, even after the previous selector fix.
- **Fix:** Changed all visibility toggles to use explicit `'block'` / `'none'` values. `display = ''` is ambiguous when CSS has a `display: none` rule on the element.
- **Session flag:** Added `feedLoaded` flag so `all_articles.json` is only fetched once per session. Repeat pill switches instantly restore the rendered view without a new network request.
- **No-ops guarded:** Pill and page elements are null-checked before use so clicking a pill before the DOM is fully ready cannot throw.

## [2026-04-10] Fix: The Feed pill click handler and empty state

- **Root cause:** `document.querySelector('.page-outer')` in `switchMode()` was selecting the first `.page-outer` in the DOM — the one inside `#feed-page` — instead of the edit page's wrapper. This meant clicking "The Feed" pill was hiding the feed's own container rather than the edit page.
- **Fix:** Added `id="edit-page"` to the edit page's `.page-outer` and updated `switchMode()` to reference both pages by ID (`getElementById`), not class selector.
- **Empty state:** Replaced inline `<small>` loading/error text with a `.feed-empty-state` component — a centered editorial message ("The Feed populates after the next scheduled run.") with a small-caps schedule line ("Runs daily at 7:30 AM · 1:30 PM · 7:30 PM CT"). Applied consistently across all empty/error paths in `switchMode()` and `buildFeedView()`.

## [2026-04-10] NL filter bar — natural language filtering in The Edit and The Feed

- **Both modes** now have a subtle `/` filter bar above the article list, dormant by default (activates on `:focus-within` with a 1px border reveal).
- **Natural language parsing** — pressing Enter on phrases like "only sneakers", "just 9s and 10s", "high scores", "reddit only", "tech", "watches" maps to existing filters. Clear-typed inputs ("clear", "reset") reset all filters.
- **The Edit** — score phrases activate the sidebar score filter (`applyFilter`); source phrases set `data-nl-hidden` on matching rows. Both can coexist.
- **The Feed** — source phrases filter by `data-nl-hidden`; score phrases filter feed rows by `data-score` attribute.
- **Status chip** — shows active filter label (e.g. "9s & 10s", "42 articles") or "no filters matched" if no rule fires.
- **× button** — appears on input and on status; clears input and resets all filters. Escape key also resets and blurs.
- **Graceful fallback** — unrecognized queries show a subtle "no filters matched" message without affecting the current view.

## [2026-04-10] The Feed — wired to its own all_articles.json data source

- **`daily_curator.py`** — new `write_all_articles_json()` saves every scored real article (before `MIN_SCORE` filter and `MAX_PICKS` cap) to `all_articles/all-YYYY-MM-DD-HHMM.json` after each run. Trend items (no URL) are excluded. Fields: title, source, link, score, why, hook, image, published.
- **`daily_curator.yml`** — added `all_articles/` to the `git add` step so each run's file is committed alongside its picks markdown.
- **`deploy-pages.yml`** — build step now aggregates all `all_articles/*.json` files into `site/all_articles.json` (newest run first), mirroring how `picks_data.json` is built from markdown files.
- **`index.html`** — The Feed now fetches `all_articles.json` directly (`loadFeedData()` with in-session cache) instead of reading from `cachedRuns`. `buildFeedView()` updated to consume the `runs[].articles[]` format. The Edit continues to use `picks_data.json` / `cachedRuns` unchanged. Graceful "feed populates after next run" message shown if `all_articles.json` is absent.

## [2026-04-10] The Feed mode — full chronological stream with source navigator

- **The Feed** is now a fully functional view activated by the "The Feed" pill in the top nav.
- **Chronological stream** — all picks across all runs, newest first, grouped by date with date dividers. No score minimum, no score filtering.
- **Clean rows** — source name replaces the score badge in col 1. No rarity badges, no font glow, no colored left-border effects. Score data exists on articles but is never displayed in this mode.
- **Expand panel** — still available per-row (Why it matters, Hook, Read button) without score information.
- **Source navigator sidebar** — lists every source with an article count badge (e.g. "Hypebeast · 4"). Clicking any source filters The Feed to that source only. "All Sources" resets the stream. Sidebar is exclusive to The Feed — The Edit sidebar is unchanged.
- **The Edit unchanged** — all existing scored/filtered behavior, rarity system, sidebar filters, and trends panel remain exactly as they were.

## [2026-04-10] Nav redesign — The Edit / The Feed pill + settings panel consolidation

- **Top nav simplified** to: Logo wordmark | The Edit / The Feed pill toggle | Gear icon. Today/Archive/Trends nav links removed.
- **The Edit / The Feed pill** — thin 1px border, rounded pill style; "The Edit" is the default active state (scored/filtered view). "The Feed" shows a Coming Soon placeholder (full chronological feed, coming soon).
- **Light/dark mode toggle** moved from topbar into the settings panel under a new "/ Appearance" section. Button label reflects current state (☽ Dark / ☀ Light).
- **Notification bell** moved from topbar into the settings panel under a new "/ Notifications" section. Button reflects permission state (🔔 On / 🔕 Off / 🔔 Enable).

## [2026-04-09] Restore full source list in settings panel

- **Root cause:** A prior settings-panel bug overwrote `sources.json` with a single Reddit entry, hiding all 19 Inoreader subscriptions from the "Current Sources" panel.
- **Fix:** Rebuilt `sources.json` with all 19 Inoreader subscriptions (Hypebeast, Sneaker News, GQ, Complex, Variety, The Atlantic, Vox, Adweek, ESPN, The Verge, WIRED, TechCrunch, Engadget, Ars Technica, CNBC, r/popculturechat, r/sports, r/nba, r/artificial) + Reddit (r/popular), each with correct `category` and `enabled: true`.
- **`fetch_articles_from_direct_rss()`** now filters out entries where `enabled` is `false` (previously fetched everything regardless of paused state).
- **`generate_sources_json()`** now preserves existing `enabled` and `category` metadata when re-seeding from Inoreader, and re-adds any extra sources (e.g. Reddit r/popular) that aren't in the Inoreader subscription list.

## [2026-04-09] Score filter sidebar — split into individual rarity tiers

- Replaced combined "Score 9–10" filter with three independent toggle buttons: **10 — Legendary** (orange), **9 — Epic** (purple), **8 — Rare** (blue).
- Filters now work as multi-select: each tier toggles independently; "All picks" clears all active filters.
- Rarity dot indicators (colored circles) added to each tier button, matching the existing badge and card glow color system.
- Active rarity filters glow in their tier color (blue/purple/orange) using `text-shadow`.

## [2026-04-09] Fix: settings panel sources list now loads full sources.json on open

- **Root cause:** `spLoadSources()` guarded on `VOTE_TOKEN` and called `spGetSources()` (GitHub API, auth required) for the read path. When the token was absent or unsubstituted, it returned an empty list — and any subsequent add overwrote `sources.json` with a single entry.
- **Fix:** Added `spFetchSources()` which reads `sources.json` via the raw GitHub URL (no token required for public repos). `spLoadSources()` now calls this unconditionally, so the full source list always renders on panel open. Authenticated `spGetSources()` is retained for write operations (add/pause/remove) where the GitHub API SHA is required.

## [2026-04-09] Settings panel — gear icon, feed view toggle, source management

- **Gear icon** added to right side of topbar (SVG, consistent with existing button style). List/Cards toggle removed from topbar — it now lives inside the settings panel.
- **Settings panel** slides in from the right (340px desktop, full-width mobile). Sections: Feed View and Sources. Matches Blank editorial aesthetic — same border, type, and surface variables throughout.
- **Feed View section** — List / Cards toggle moved here from the topbar. Existing `setView()` logic and localStorage persistence unchanged.
- **Sources section** — URL input with auto-detect RSS (fetches via allorigins.win CORS proxy, parses RSS link tags and feed content); name field (auto-populated from page `<title>`); category dropdown (culture, tech, sports, fashion, sneakers, watches, other); Add Source button writes to `sources.json` via GitHub API (same pattern as `votes.json`). Duplicate URL check before writing.
- **Current Sources list** — shows all sources from `sources.json` with Pause/Resume and Remove buttons, each writing back to GitHub. Paused sources render at reduced opacity. Changes take effect on the next scheduled pipeline run.

## [2026-04-09] Fix Claude scoring failure on large article pools

- **Root cause:** With Inoreader + Direct RSS combined, pools of 200+ articles require ~20k output tokens — more than double the 8,192 `max_tokens` limit. Claude's response was truncated mid-JSON, causing the parse failure.
- **Chunked scoring:** `evaluate_articles_with_claude()` now splits large pools into batches of 50 (`CLAUDE_SCORING_BATCH_SIZE`) via a private `_score_batch()` helper. Each batch is scored independently and results are reassembled in order.
- **Graceful batch failure:** If a batch fails to parse after one retry, it logs a warning and assigns score 0 to that batch — the pipeline continues rather than terminating.
- **Improved JSON parsing:** Strip markdown code fences (` ```json `) before parsing, catching another common edge case.

## [2026-04-09] Direct RSS parallel fetch + vote persistence

- **Direct RSS (sources.json):** Added `fetch_articles_from_direct_rss()` which reads `sources.json` and fetches all feeds in parallel (10 workers, 10s timeout per feed). Failed fetches are logged and skipped — the pipeline continues.
- **Auto-generate sources.json:** On first run, if `sources.json` is absent, `generate_sources_json()` fetches the Inoreader subscription list and writes the file automatically.
- **Parallel fetch in main():** Inoreader and Direct RSS now run concurrently via `ThreadPoolExecutor(max_workers=2)`. Article pools are combined before deduplication, OG enrichment, and Claude scoring.
- **`feedparser>=6.0.0`** added to `requirements.txt`.
- **Vote persistence:** Vote state (up/down) is now saved to `localStorage` under key `blank_votes` (keyed by article URL). `applyVoteState()` restores classes after every render — votes survive page refresh.

## [2026-04-09] List view: fix right border start position

- Moved `border-right` off `.content` onto `.list-header` + `#feed-container` — border now starts at the column header row instead of the top of the full content column.

## [2026-04-09] List view: right border on content area

- Added `border-right: 1px solid var(--border)` to `.content` — closes the list container on the right side with the same neutral 1px divider used for row borders. Rarity color remains exclusive to the left border.

## [2026-04-08] Add ROADMAP.md

- Created ROADMAP.md in project root with full product roadmap organized by category (In Progress, Visual/Frontend, Scoring, Feedback Loop, Major Features, Parked).

## [2026-04-08] List view: rarity left border + remove date column

- **Permanent rarity left border on rows:** Score 8 gets a 2px blue (`#3b82f6`) left border, score 9 gets purple (`#a855f7`), score 10 gets orange (`#f59e0b`). Score 7 has no border. Border is always visible (not only on expand).
- **Date column removed from list view:** The `/ Date` header and per-row date text are gone. The relative timestamp ("6h ago") beneath the score badge is preserved as-is.

## [2026-04-08] Rarity tier overhaul, font glow, accordion + trends UX

- **Scoring tiers split to 4 levels:** 7 = outlined badge only (no fill), 8 = blue filled badge, 9 = purple filled badge (`score-epic`), 10 = orange filled badge. Previously 9 and 10 were both "legendary" orange.
- **Font glow on title text:** Blue glow for score 8, medium purple glow for 9, strong orange glow for 10 — applied in both list and card view. Existing card box-shadow/border glow is preserved.
- **10/10 rarity rule:** Added to Claude scoring prompt — a 10 should be genuinely rare (roughly once every 1–3 runs), never awarded just to fill the tier.
- **Accordion "SUMMARY" → "WHY IT MATTERS":** Renamed the expand panel field label in list view.
- **Accordion left border replaces grey box:** `exp-inner` background removed; replaced with a thin 2px vertical left border tinted to the story's rarity color (grey for 7, blue for 8, purple for 9, orange for 10).
- **X Trends hidden by default on desktop:** Trends module is now `display: none` globally and only shown when the user clicks the "Trends" topbar button (unified with existing mobile behavior, using `trends-visible` class instead of `mobile-open`).
- **CLAUDE.md:** Added instruction to always read the frontend design skill before writing UI code.
