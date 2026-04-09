# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-04-08] Rarity tier overhaul, font glow, accordion + trends UX

- **Scoring tiers split to 4 levels:** 7 = outlined badge only (no fill), 8 = blue filled badge, 9 = purple filled badge (`score-epic`), 10 = orange filled badge. Previously 9 and 10 were both "legendary" orange.
- **Font glow on title text:** Blue glow for score 8, medium purple glow for 9, strong orange glow for 10 — applied in both list and card view. Existing card box-shadow/border glow is preserved.
- **10/10 rarity rule:** Added to Claude scoring prompt — a 10 should be genuinely rare (roughly once every 1–3 runs), never awarded just to fill the tier.
- **Accordion "SUMMARY" → "WHY IT MATTERS":** Renamed the expand panel field label in list view.
- **Accordion left border replaces grey box:** `exp-inner` background removed; replaced with a thin 2px vertical left border tinted to the story's rarity color (grey for 7, blue for 8, purple for 9, orange for 10).
- **X Trends hidden by default on desktop:** Trends module is now `display: none` globally and only shown when the user clicks the "Trends" topbar button (unified with existing mobile behavior, using `trends-visible` class instead of `mobile-open`).
- **CLAUDE.md:** Added instruction to always read the frontend design skill before writing UI code.

## [2026-04-07] Score badge on article cards

Added score badge to the date column of each article card (below the date, above the title area). Uses the same color coding as the expanded detail panel: lime/accent for 9+, dark ink for 8, bordered muted for 7.

## [2026-04-07] Stripe Dev Blog-style redesign v2 — true clone with expand/collapse

Rebuilt index.html to faithfully replicate the Stripe Dev Blog layout:
- Two-column layout: left sidebar (/ Scores filter + / Sources + / Trending) and right article list
- Thin topbar with brand + nav links (Today / Archive / Trends) + action buttons
- Large "Blank" page heading with total pick count as inline superscript
- "/ Date" and "/ Title" column headers in Stripe's slash-prefix style
- Date formatted as "YYYY · MM · DD" with middle-dot separators, shown per row
- Clean collapsed rows: date | title | "+" circle expand button on far right
- Expanded rows: Summary + Source (right), Hook + Score (right), footer with Read → and vote buttons
- Carousel angle trigger shown as lime accent badge inside the expanded Hook field
- Score filter sidebar: All / Score 9–10 / Score 8 / Score 7 with pick counts
- Sources breakdown sidebar with per-source counts
- X Trending in sidebar + inline panel above the article list
- Dark mode, breaking news, push notifications all preserved

## [2026-04-07] Stripe Dev Blog-style redesign of web feed

Complete visual redesign of `index.html` to match Stripe Dev Blog aesthetic:
- Light gray background (#E8E8E8), lime green accent (#C4E817), near-black text (#1E1E1E)
- sohne-var / Helvetica Neue / Arial sans-serif font stack throughout (no more Georgia/serif)
- New sticky header: BLANK wordmark + Today/Archive/Trends nav tabs + action buttons
- Full-width single-column layout (max 860px, no sidebar)
- Picks rendered as a three-column grid table (score | title | source/time)
- Date-grouped sections with sticky headers and pick counts
- Expandable rows: click any row to reveal "Why it matters" + carousel hook angle
- Carousel angle parsed into trigger label badge + formatted hook lines
- Flat score badges: grey (7), dark (8), lime accent (9–10) — no glows
- Vote buttons moved inside the expand panel
- X Trends module kept as a flat card at the top of today's section
- Dark mode preserved with same lime accent
- Mobile: two-column at ≤479px (meta column hidden), tablet at 480–859px
- Removed: card view, sidebar, filter bar, rarity glows, serif headlines

## [2026-04-07] Fix HOOK bleeding into website "Why" field

The `why` regex in `deploy-pages.yml` didn't know to stop at `**Hook:**`, so the hook text was being captured as part of the `why` value and rendered on the site. Added `\n\n\*\*Hook` as a stop condition in the regex.

## [2026-04-07] Fix daily curator push rejection from race condition

Added `git pull --rebase origin main` before both push steps in `daily_curator.yml`. The breaking news monitor commits every 15 minutes, so it frequently lands between the curator's commit and push, causing a rejected push. The rebase pulls in any new commits before pushing.

## [2026-04-06] List mode: terminal/editorial aesthetic + hook removed from web views

- Monospace font stack (SF Mono / JetBrains Mono / Consolas) for all metadata in list mode
- Score displayed as zero-padded `09` in mono, color-coded by tier
- `›` arrow indicator animates in on hover (mono, tier-colored)
- Source line above title in all-caps tight mono
- Editor's note always visible in italic serif, 2-line clamp
- Glow on left-border intensifies on hover
- Hook field confirmed absent from card and list views (only in picks/*.md files)

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

