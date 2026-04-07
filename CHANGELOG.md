# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-04-06] List mode redesign — glowing borders, always-visible why, clickable rows

- Removed font glow from list mode titles
- Added glowing left-border accent to rare (blue) and legendary (amber) rows, mirroring card view rarity tiers
- Legendary rows get a subtle amber background tint
- "Why" text is now always visible (2-line clamp) — no more hover-to-expand
- Entire row is now an `<a>` tag — click anywhere to open the article (works on mobile)
- Score displayed as pill badge (matching card view) instead of bare number
- Subtle hover background on rows for clear affordance

## [2026-04-06] Lower MIN_SCORE to 6 + add scroll-stopping hook to picks

- Lowered `MIN_SCORE` from 7 to 6 so more picks surface per run
- Claude now generates a scroll-stopping `HOOK` field for each qualifying pick (score ≥ 6), formatted as `[TRIGGER: X] Line / Line / Line` using one of six psychological triggers (Curiosity, FOMO, Disbelief, Defensiveness, Relief, Greed)
- Hook appears in `picks/*.md` files only — not rendered on the website

## [2026-04-04] Fix Breaking News Monitor git add crash (v2)

Replaced incorrect `git add --ignore-missing` (that flag requires `--dry-run`) with a shell conditional: `if [ -f breaking_news.json ]; then git add ...; fi`. If the Python script exits early without writing its output files, the block is skipped and the workflow exits cleanly with no changes to commit.

## [2026-04-04] Add light/dark mode toggle to feed header

Added a ☀/☽ toggle button to the feed header. Dark mode is the default. Theme preference persists in `localStorage` under `blank_theme`. Uses a `[data-theme="dark"]` CSS override block with an inline IIFE before `</head>` to prevent flash of wrong theme on load.

## [2026-04-04] Fix all three GitHub Actions cron schedules for correct Central Time

All three crons were firing 1–2 hours late. The workflow comments referenced CST (UTC-6) but DST (CDT, UTC-5) has been active since March. Updated all three crons to CDT-correct UTC times: `30 12 * * *`, `30 18 * * *`, `30 0 * * *` = 7:30 AM / 1:30 PM / 7:30 PM CDT. During winter (CST), runs will fire at 6:30 AM / 12:30 PM / 6:30 PM. Also updated CLAUDE.md to document accurate run times.

## [2026-04-02] Fix VAPID sub claim to real admin email for Apple APNs

Updated `VAPID_CLAIMS` in `send_push.py` — `sub` was a placeholder (`mailto:bot@daily-curator`), now set to `mailto:mjaffry1@gmail.com`. Apple's push server requires a valid `mailto:` or `https:` contact URI in the VAPID JWT `sub` claim.

## [2026-04-02] Silent push re-subscribe on load + full console logging for push flow

Refactored the Web Push subscription flow in `index.html` for resilience and debuggability.

- Extracted shared subscription logic into `subscribeToPush()` — used by both `enableNotifications()` (user-initiated) and the new `ensurePushSubscription()` (automatic on load).
- `ensurePushSubscription()` runs on every page load: if `Notification.permission` is already `'granted'` but the browser's `pushManager` has no active subscription (e.g. after clearing site data), it silently re-subscribes and saves to `subscriptions.json`.
- Added `console.log` statements throughout the full subscription flow: permission check, VAPID key injection status (first 12 chars), SW scope, existing subscription check, `pushManager.subscribe()` call, and all GitHub API GET/PUT steps in `saveSubscription()` including response status codes and error bodies.

## [2026-04-02] Browser push notifications on run completion via VAPID Web Push

Added end-to-end Web Push notification delivery triggered by GitHub Actions after each daily curator run.

**New files:**
- `generate_vapid_keys.py` — one-time local script to generate a VAPID EC P-256 key pair. Outputs `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` values to add as GitHub Actions secrets.
- `send_push.py` — called by the workflow after each run. Detects which scheduled run it is from the UTC hour, picks the appropriate message, and sends a Web Push to all entries in `subscriptions.json`. Prunes expired/unsubscribed endpoints (HTTP 404/410) automatically.
- `subscriptions.json` — initial empty array; populated by the frontend when a user enables notifications.

**Notification messages by run:**
- 8:30 AM CT: "Your morning briefing is ready. See what's worth your time today."
- 1:30 PM CT: "Your afternoon picks are in. Take a break and catch up."
- 7:30 PM CT: "Your evening briefing is ready. End the day informed."

Push is skipped silently if secrets are missing, there are no picks today, or there are no subscribers.

**`daily_curator.yml`:** Two steps added after the picks commit — `send_push.py` runs, then a second commit prunes any expired subscriptions from `subscriptions.json` if any were removed.

**`index.html`:**
- `const VAPID_PUBLIC_KEY = '__VAPID_PUBLIC_KEY__'` constant added (injected at build time).
- `urlBase64ToUint8Array()` helper added for converting the VAPID public key to the format required by `pushManager.subscribe()`.
- `saveSubscription()` added — uses the same GitHub API pattern as vote saving to append the browser's push subscription object to `subscriptions.json` in the repo.
- `enableNotifications()` expanded: after permission is granted, calls `pushManager.subscribe()` with the VAPID key and saves the resulting subscription. Skips subscription if VAPID key isn't injected (local dev).

**`deploy-pages.yml`:** `__VAPID_PUBLIC_KEY__` placeholder injected into `site/index.html` alongside the existing `VOTE_TOKEN` injection step.

**`sw.js`:** Notification `tag` is now read from the push payload (`data.tag`) instead of hardcoded to `'breaking-news'`, allowing briefing and breaking news notifications to coexist with distinct tags.

**`requirements.txt`:** Added `pywebpush>=2.0.0`.

**Setup required:** Run `generate_vapid_keys.py` locally and add `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` as GitHub Actions secrets. VSCode GitHub Actions extension will show warnings for these secrets until they exist in the repo.

## [2026-04-02] Always-visible notification button with live permission state

The 🔔 button in the header now renders unconditionally on page load instead of only appearing when breaking news content is detected. `initNotifBtn()` reads `Notification.permission` on load and sets the button label/title accordingly: 🔔 "Enable breaking news notifications" (default), 🔔 "Notifications enabled" (granted), 🔕 "Notifications blocked" (denied). Browsers that don't support the Notification API hide the button entirely. The `checkBreakingNews()` poller no longer controls button visibility.

## [2026-04-02] Score rarity tiers, Breaking News Mode, trend velocity scoring

**Score-based rarity tiers (`index.html`):**
- Three visual card tiers based on article score: Common (7, default treatment), Rare (8, steel/slate left-edge accent bar), Legendary (9–10, amber left-edge accent with warm pulse glow)
- Score badge color shifts to match tier: dark pill for Common, steel `#64748b` for Rare, amber for Legendary
- The amber pulse animation for Legendary cards is upgraded to preserve the inset left bar during the keyframe animation
- Sidebar "Best this week" badge also respects the new tier system
- Design language: editorial left-rule accent (newspaper column marker style), not gamey/chromatic

**Breaking News Mode:**
- New `breaking_news_check.py` script — fetches Google Trends RSS directly every 15 minutes (no Apify). Detects velocity spikes: topics newly entering the top 5 that were not in the previous check's known set. Qualifying topics bypass Claude scoring entirely — velocity is the qualification.
- New `.github/workflows/breaking_news.yml` — cron `*/15 * * * *`. Commits `breaking_news.json` and `breaking_news_state.json` to main on each spike; push triggers the existing deploy-pages workflow.
- `breaking_news.json` items expire after 6 hours (TTL pruned each run).
- New `sw.js` service worker and `manifest.json` web manifest added for PWA support (iOS 16.4+ home-screen Add to Home Screen).
- Feed polls `breaking_news.json` every 2 minutes. When a new spike is detected: renders a "Breaking now" section at the top of the feed with red left-accent cards and a pulsing BREAKING badge, shows a browser push notification via the service worker (works on iOS PWA), logs an activity feed event.
- Notification permission requested on user gesture (🔔 button in header) — shown only when breaking news exists. Compatible with iOS PWA and desktop browsers.
- `deploy-pages.yml` updated to copy `sw.js`, `manifest.json`, and `breaking_news.json` into the deployed site on every build.

**Trend velocity as scoring signal (`daily_curator.py`):**
- `evaluate_articles_with_claude()` accepts a new `trending_topics` list parameter.
- Up to 30 live topic names (combined from X Trending + Google Trends) are injected into the Claude scoring prompt as a "CULTURAL VELOCITY SIGNALS" block.
- Prompt instructs Claude to use topic matches as additional evidence for TRENDING and CULTURAL criteria — explicitly framed as editorial judgment, not mechanical score addition.
- `main()` extracts topic names from the already-fetched `twitter_trends` + `google_trends` lists and passes them to the scoring call (no extra API calls).

## [2026-04-02] Split 7 and 8 scoring anchors for better score separation

Updated scoring anchors in the Claude prompt to give 7 and 8 distinct definitions: 9–10 = "you have to tell someone about this today", 8 = "you'd bring this up in conversation today", 7 = "worth your time", 5–6 = forgettable, 1–4 = noise. Previously 7 and 8 shared the same anchor, causing most qualifying articles to cluster at 7.

## [2026-04-02] Tighten scoring logic, add category diversity, fix "why" display

**Scoring prompt overhaul (`daily_curator.py`):**
- Replaced vague "be ruthlessly selective" guidance with concrete score anchors: 9–10 = "you have to tell someone about this today", 7–8 = "you'd be glad you saw it — it says something real about where culture is right now", 5–6 = forgettable, 1–4 = noise
- Added "when in doubt between 6 and 7, score it 6" tiebreaker to reduce score inflation
- Added CATEGORY DIVERSITY RULE: Claude now caps high scores within any single category unless the news genuinely warrants it, preventing one topic from flooding the picks
- Reduced cross-source bonus from "+1–2 points" to "+1 point only" to stop borderline articles being pushed over the 7 threshold purely by repetition

**"Why it matters" fix (`deploy-pages.yml`):**
- The picks markdown was writing `**Why it matters:**` but the parser was looking for `**Why it scored high:**` — a mismatch from an earlier prompt rewrite. Updated regex to match both headings so the editorial note now shows correctly on pick cards in the web feed.

## [2026-04-02] Raise MAX_PICKS from 10 to 30

Increased the maximum picks per run from 10 to 30. The scoring call already evaluates ~125 articles per run — this change simply surfaces more of the qualifying results (score ≥ 7) instead of capping at 10.

## [2026-04-02] Raise max_tokens for all Claude calls to handle larger article pools

After raising article caps to 150/15, the scoring call was crashing because `max_tokens=4096` was too small to fit JSON evaluations for 125 articles. Also raised the other two calls for the same reason.

- `evaluate_articles_with_claude`: 4096 → 8192
- `detect_cross_source_trends`: 2048 → 4096
- `deduplicate_articles_pre_scoring`: 2048 → 4096

## [2026-04-02] Switch Claude model to Sonnet; raise article caps

Switched all three Claude API calls (cross-source trend detection, scoring, pre-scoring dedup) from `claude-opus-4-6` to `claude-sonnet-4-6` for faster, cheaper runs. Also raised `MAX_ARTICLES_TO_SEND` from 60 → 150 and `MAX_ARTICLES_PER_SOURCE` from 5 → 15 to significantly increase the candidate pool per run and surface more diverse picks.

## [2026-04-01] Fix X trends ticker — write all trends to picks file

## [2026-04-01] Live feed enhancements — timestamps, animations, polling, activity

Seven enhancements to index.html making the feed feel alive:

1. **Live relative timestamps** — card timestamps now show "2 hours ago" / "just now" computed from the run's UTC time, refreshing every 60 seconds via the existing countdown tick without page reload.
2. **Staggered fade-in already present; read-state transition** — improved `opacity` transition on the `.pick-card` base rule to include opacity for smoother mark-as-read fade.
3. **Score pulse** — cards with score ≥ 9 get class `score-elite`. After their entry `fadeUp` animation completes (detected via `animationend`), a `.pulsing` class applies a subtle amber glow heartbeat (`scorePulse` keyframe, 4s loop). Clean separation avoids animation-delay conflicts.
4. **Real-time X trend updates** — `checkForNewPicksAndTrends()` runs every 5 minutes, silently refetches `picks_data.json`, and patches the trends grid in-place. A "updated X mins ago" label appears on the trends card header.
5. **New picks available banner** — polls every 5 minutes using a run fingerprint (`date + time`). If a new run has dropped since page load, a fixed banner slides in at the top: "New picks available — click to refresh." Dismissible.
6. **Reading progress bar** — 2px amber bar fixed at the very top of the viewport, fills as the user scrolls, updates on every scroll event (passive listener).
7. **Live activity feed** — "Live" section added to sidebar. Logs `localStorage`-persisted events: "Mo read an article" on each mark-read, "New picks dropped at X" on polling detection, "Latest picks: X" on initial load (guarded to avoid duplication on rapid refreshes). Shows last 8 events with live relative timestamps.

## [2026-04-01] Reframe Claude scoring prompt to editorial language

Removed all social media, carousel, and content creation framing from the Claude scoring prompt. The AI persona is now a senior editor curating an intelligence briefing. Criterion 4 changed from "CAROUSEL" to "SIGNIFICANCE". The WHY field is now written as a brief editor's note explaining why the story matters to the reader. The ANGLE/carousel hook field has been removed entirely from the prompt, the JSON schema, and the picks markdown output.

## [2026-04-01] Add "Direct RSS feed ingestion" to Phase 5 roadmap

Added direct RSS feed ingestion as a planned feature item under the Phase 5 platform section in CLAUDE.md.

## [2026-04-01] Limit archive to last 7 days

The "Earlier" archive section now only displays picks from the previous 7 days. Older picks files remain in the repo unchanged — this is a display-only filter.

## [2026-04-01] Remove X Trending from sidebar

Removed the X Trending list from the right sidebar — it duplicated the X Trending card already visible in the main feed.

## [2026-04-01] Reading stats in sidebar

Added a "Reading" section to the right sidebar with three persistent counters stored in `localStorage`: **Read Today** (resets at midnight CT), **All Time** (never resets), and **Day Streak** (consecutive days with at least one article read). All three update live when a card is marked read. Duplicate clicks on an already-read card are ignored so counts stay accurate.

## [2026-04-01] Article title is now a clickable link

The card title on each pick card is now an `<a>` tag opening in a new tab. Article cards link to the full article (same URL as "Read article") and clicking also triggers the read-state treatment. Trend items link to the relevant X or Google search page, matching the behavior of the X Trending card.

## [2026-04-01] Read state persistence on pick cards

Clicking "Read article" on a pick card now marks it as read: opacity drops to 0.55, the link label changes to "✓ Read". Read state is stored in `localStorage` under `blank_read` (keyed by article URL) so the treatment persists across page refreshes. Hovering a read card partially restores opacity for easy re-reading.

## [2026-04-01] Rename Intel to Stats, sidebar open by default

Renamed the "Intel" header button to "Stats". Sidebar now opens by default on all screen sizes. The Stats button toggles it closed and open. Cleaned up dead ticker reference in `positionSticky`.

## [2026-04-01] Remove X trending ticker, restyle trends card, make trends clickable

Removed the scrolling X trending ticker strip from the top of the feed. Restyled the X trends card to match Blank's editorial design system — white background, light borders, ink-based text colors, consistent with article cards. Made all X trending topics (feed card and sidebar) clickable links to `x.com/search?q=` in a new tab.

## [2026-04-01] Fix HTML entities in article titles

Applied `html.unescape()` to Inoreader article titles at the point of extraction in `daily_curator.py`. Prevents encoded entities like `&amp;`, `&#8217;`, and `&ldquo;` from appearing literally in feed cards and pick files.

## [2026-03-31] Add rank numbers to X trending ticker

Each pill in the scrolling ticker now shows the trend's rank number before the name (e.g. `1. Virgil Abloh · 2. NBA Playoffs`). The doubled array for seamless looping keeps rank numbers correct by using `i % topics.length + 1`.

- Replaced `.ticker-pill::before { content: '#' }` with a `.ticker-pill-rank` inline span — italic Georgia, 9px, 40% opacity, matching the editorial rank treatment in the full trending module
- The `#` pseudo-element is removed; rank numbers are data, not decoration

## [2026-03-31] Move INTEL toggle into header nav — always accessible at top of page

The INTEL section-divider toggle was inside `<aside class="sidebar">` at the bottom of the DOM, so on mobile it appeared after all the article cards — nowhere near reachable without scrolling.

**Fix:** Moved INTEL into the sticky header alongside Today and Archive as a third navigation pill. The sidebar section-divider toggle and its CSS are removed entirely.

- **`index.html` header**: Added `<button class="pill-btn" id="btn-intel">Intel</button>` to `.header-actions`
- **`wireButtons()`**: Now wires `#btn-intel` to toggle `.open` on `#sidebar-body` and the `.active` class on the button itself
- **Removed**: `.sidebar-toggle`, `.sidebar-toggle::before/after`, `.sidebar-toggle-label`, `.sidebar-toggle-chevron` CSS rules and the corresponding `<button>` in the HTML
- The sidebar body (`#sidebar-body`) remains collapsed by default and revealed on click, at all screen sizes

## [2026-03-31] INTEL toggle visible and active on all screen sizes

Removed the two desktop overrides that were hiding the toggle and force-expanding the sidebar body at ≥1100px. The INTEL toggle and collapsed-by-default behavior now apply universally — click to reveal on all screen sizes.

## [2026-03-31] Make sidebar accessible on mobile and narrow screens — collapsible Intel panel

The sidebar was `display: none` below 1100px, making all its content (Today stats, Best this week, Sources, X Trending) invisible on mobile and tablet.

**Solution:** Mobile-first collapsible panel with an editorial section-divider toggle.

- **Toggle button** — a full-width `<button>` with hairline rules extending left and right and "INTEL" in 9px tracked uppercase centered between them. The same typographic register as `.archive-label`. A small chevron rotates 180° when expanded. No button chrome — just the editorial section break.
- **Collapse/expand** — `sidebar-body` gets `display: none` by default; `display: block` (or `grid`) when `.open` class is toggled. `aria-expanded` updates on each click.
- **2-column grid at 521–1099px** — when open, `.sidebar-body` uses `grid-template-columns: 1fr 1fr; column-gap: 40px` so the four sections pair side-by-side rather than stacking vertically on medium screens.
- **Desktop (≥1100px)** — toggle is hidden, body is always visible (`display: block !important`). Existing sticky sidebar layout unchanged.
- **HTML** — `<aside id="sidebar">` now contains the toggle button and `<div id="sidebar-body">`. `renderSidebar()` targets `#sidebar-body`. `positionSticky()` still references `#sidebar` (the outer element) — no change needed.

## [2026-03-31] Restore ticker + fix sidebar X Trending placement

- **Ticker fallback**: `buildTicker()` was hiding the strip for all existing picks files because they pre-date the `x_trends` field. Added a fallback: if `x_trends` is empty, extract topics from X-source scored picks (the original behavior). Ticker is now always visible when X trend data is available in either form.
- **Sidebar order**: X Trending section moved to after "Sources Today" as intended.

## [2026-03-31] Add full X trending topics list to feed — inline module + sidebar section

Two persistent surfaces for the full ranked trending list (all 10–20 topics from the latest run):

**Inline dark module** — appears at the top of the feed (all screen sizes), before the pick cards. Uses the same `var(--ink)` dark background as the ticker strip, creating a visual bracket: ticker scrolls at the top, full ranked list anchors the feed entry. Layout is a 2-column grid of ranked topics; collapses to 1 column on mobile (≤520px).

**Right sidebar section** — "X Trending" section at ≥1100px, rendered between "Today" stats and "Best this week". Uses the existing sidebar row pattern.

**Rank heat system** applied to both surfaces:
- Ranks 1–3 (`rank-hot`): amber rank number + near-white bold topic name — peak cultural heat
- Ranks 4–7 (`rank-warm`): softened rank number + mid-brightness name
- Ranks 8+: default dim treatment

**Rank numbers** rendered as zero-padded italic Georgia (01, 02 … 20) — the same typeface used for editorial headlines. Small and quiet beside the topic name, but unmistakably intentional.

**Implementation:**
- New `buildTrendsModule(topics)` helper renders the dark inline panel
- New `trendRankClass(i)` helper returns the appropriate CSS class for a given rank
- `renderSidebar()` now reads `latestRuns[0].x_trends` to render the sidebar section
- `render()` prepends the trends module before `#section-latest`

## [2026-03-31] Fix VOTE_TOKEN guard check — sed was replacing comparison string too

`sed -i "s|__VOTE_TOKEN__|...|g"` replaces every occurrence of `__VOTE_TOKEN__` in the file, including the comparison strings in the guard check and console.log. After injection, the check became `VOTE_TOKEN === 'github_pat_...'` which was always `true`, causing the function to abort every time.

- Removed `VOTE_TOKEN === '__VOTE_TOKEN__'` from the if-guard — the only check needed is `!VOTE_TOKEN` (empty string is falsy when the secret isn't set; a real token is truthy)
- Removed `VOTE_TOKEN !== '__VOTE_TOKEN__'` from the console.log for the same reason
- The declaration `const VOTE_TOKEN = '__VOTE_TOKEN__'` remains as the sole placeholder; sed replaces just that one occurrence with the real token at deploy time

## [2026-03-31] Fix VOTE_TOKEN injection — dedicated sed step instead of Python heredoc

The token was not being injected because the replacement ran inside `python3 - << 'PYEOF'`, where `os.environ.get('VOTE_TOKEN')` doesn't reliably see the step-level `env:` in all GitHub Actions runner environments.

- **Removed** the `vote_token` injection code from the Python build heredoc
- **Removed** `env: VOTE_TOKEN` from the "Build picks_data.json" step
- **Added** a new dedicated step "Inject VOTE_TOKEN into site/index.html" that runs after the Python build:
  ```yaml
  env:
    VOTE_TOKEN: ${{ secrets.VOTE_TOKEN }}
  run: sed -i "s|__VOTE_TOKEN__|${VOTE_TOKEN}|g" site/index.html
  ```
  The shell expands `${VOTE_TOKEN}` directly before passing to `sed`, which is simple and reliable.

## [2026-03-31] Add console logging to vote function for debugging

Silent `catch {}` blocks were hiding all errors from the GET and PUT calls, making it impossible to diagnose why votes weren't being written.

- Split each `catch {}` into `catch (e) { console.error(...) }` with the step name, HTTP status, and response body
- Added `console.log` at entry showing `dir`, token length/prefix, and the full record being written
- Added explicit guard log when `VOTE_TOKEN` placeholder was not replaced at deploy time

## [2026-03-31] Wire up ↑ ↓ vote buttons — write to votes.json via GitHub API

Clicking a vote arrow now records the vote to `votes.json` in the repo via the GitHub Contents API. No user authentication required.

**How it works:**
- `vote()` in `index.html` is now `async`. On a new vote it GETs `votes.json`, appends the record, and PUTs the updated file back via the GitHub Contents API.
- Each record includes: `timestamp` (CT, ISO-format), `direction` (`up`/`down`), `title`, `source`, `score`, and `url`.
- Un-votes (clicking the same arrow again to deselect) only toggle the visual state — they don't write to the repo.
- `VOTE_TOKEN` (a fine-grained PAT with `Contents: write` on this repo) is injected into `site/index.html` at deploy time by `deploy-pages.yml`. The placeholder `__VOTE_TOKEN__` in source is never a real token, so the repo is safe.

**Files changed:**
- **`votes.json`** — created with `[]` as the initial state.
- **`index.html`** — `vote()` rewritten to async; `.feedback-btns` now carries `data-title`, `data-source`, `data-score`, `data-url` attributes so vote records have full context.
- **`deploy-pages.yml`** — added `VOTE_TOKEN: ${{ secrets.VOTE_TOKEN }}` env to the build step; Python block replaces `__VOTE_TOKEN__` in `site/index.html` before deploy.

**Setup required:** Create a fine-grained GitHub PAT (Settings → Developer settings → Fine-grained tokens) with **Contents: Read and Write** scoped to only this repo. Add it as secret `VOTE_TOKEN` in repo Settings → Secrets → Actions.

## [2026-03-31] Fix X trending ticker — show all raw trends, not just scored picks

The ticker was sourcing topics from picks that survived Claude scoring and the top-10 cut. Since X trends compete with articles for the MAX_PICKS=10 slots, usually only 1–2 trend topics made it through — giving the ticker almost nothing to scroll.

- **`daily_curator.py`** — `write_markdown_output()` now accepts a `twitter_trends` argument. If trends are present, it appends a `> **X Trends:** Topic1 · Topic2 · …` line to the picks file header, storing all raw trend names before scoring discards them.
- **`deploy-pages.yml`** — parses the `**X Trends:**` line via regex and adds an `x_trends: [...]` array to each run object in `picks_data.json`.
- **`index.html`** — `buildTicker()` now reads `latestRuns[0].x_trends` (the full raw list from the most recent run) instead of filtering scored picks. Ticker now shows the full 10–20 X trending topics every run.

## [2026-03-31] Fix "Next in" countdown to use CT run times — DST-safe

`getNextRunMs()` was using hardcoded UTC times `[[13,0],[18,0],[2,0]]` (correct only during CDT). During CST (UTC-6, Nov–Mar), the real UTC run times are 14:00, 19:00, 03:00 — causing the countdown to be off by one hour half the year.

- **Replaced** `RUN_TIMES_UTC` with `RUN_TIMES_CT = [[8,0],[13,0],[21,0]]` (8 AM, 1 PM, 9 PM CT)
- **Rewrote** `getNextRunMs()` to get the current CT hour/minute via `Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago' })`, then compute the delta to the next CT run time in local minutes. Since this is a time-delta calculation, it is inherently DST-safe — no UTC offset arithmetic needed.
- **"Updated X ago"** was already correct (both sides are epoch ms, so timezone is irrelevant).

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
