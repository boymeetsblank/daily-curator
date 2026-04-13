# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

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

## [2026-04-12] Cross-run deduplication via persistent seen_urls.json

- **`seen_urls.json`** — new persistent registry stored in the repo root. Tracks every article URL that has passed through the scoring pipeline, keyed by normalized URL with an ISO timestamp of when it was first seen.
- **Rolling 7-day window** — `prune_seen_urls()` removes entries older than 7 days on every run. Prevents unbounded file growth; allows genuinely evergreen content to resurface after a week.
- **Pre-scoring filter** — `filter_seen_urls()` runs after `dedup_articles_by_url()` and before both Claude calls (pre-scoring topic clustering and main scoring). Articles already in the registry are skipped entirely, saving API calls on already-seen stories.
- **Registry update after scoring** — `update_seen_urls()` adds all scored article URLs (real articles only, no trend items) to the registry after each run. `save_seen_urls()` writes the updated file to disk.
- **Workflow updated** — `daily_curator.yml` `git add` step now includes `seen_urls.json` so the registry persists across all 3 daily runs and across days.
- **`filter_already_picked_today()` retained** — the existing same-day picks guard remains as a last-mile check specifically on top picks, complementing the broader seen registry.

## [2026-04-12] Fix: deduplication hardening + The Feed excludes Edit stories

- **`normalize_url()` helper:** Strips tracking parameters (UTM, fbclid, gclid, ref, mc_cid, and 15+ others) and URL fragments before any URL comparison. Prevents the same article with different tracking params from appearing twice.
- **`dedup_articles_by_url()`:** New fast URL-normalization dedup runs immediately after the source cap, before Claude clustering. Removes articles whose normalized URLs are identical — catches exact duplicates and tracking-param variants at zero cost.
- **`filter_already_picked_today()` upgraded:** Cross-run dedup now normalizes both stored URLs (from today's picks files) and candidate URLs before comparing. A story with `?utm_source=newsletter` no longer slips past an already-picked `?utm_source=twitter` variant.
- **Claude pre-scoring dedup unchanged:** The existing `deduplicate_articles_pre_scoring()` Claude clustering already handles near-identical titles and same-story articles from different source URLs — no changes needed there.
- **The Feed is now a true discovery layer:** `write_all_articles_json()` accepts an `exclude_urls` set. In `main()`, the set of normalized pick URLs is built after `filter_already_picked_today()`, then passed to `write_all_articles_json()` so any article that made The Edit is excluded from `all_articles/*.json`. The Feed (`all_articles.json`) now only contains stories that did not make the cut — not a superset of The Edit.

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


## [2026-04-09] Direct RSS parallel fetch + vote persistence

- **Direct RSS (sources.json):** Added `fetch_articles_from_direct_rss()` which reads `sources.json` and fetches all feeds in parallel (10 workers, 10s timeout per feed). Failed fetches are logged and skipped — the pipeline continues.
- **Auto-generate sources.json:** On first run, if `sources.json` is absent, `generate_sources_json()` fetches the Inoreader subscription list and writes the file automatically.
- **Parallel fetch in main():** Inoreader and Direct RSS now run concurrently via `ThreadPoolExecutor(max_workers=2)`. Article pools are combined before deduplication, OG enrichment, and Claude scoring.
- **`feedparser>=6.0.0`** added to `requirements.txt`.
- **Vote persistence:** Vote state (up/down) is now saved to `localStorage` under key `blank_votes` (keyed by article URL). `applyVoteState()` restores classes after every render — votes survive page refresh.





