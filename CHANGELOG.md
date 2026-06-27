# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-06-27] Refactor: move time-decayed feed ranking into the engine (one source of truth)

The "ranked living feed" ordering (rank = score − ageHours / `DECAY_HOURS_PER_POINT`, recency as tiebreak) was computed client-side in `index.html`, so surfaces could drift. Centralized it: `DECAY_HOURS_PER_POINT = 12` plus `decayed_rank()` / `rank_timestamp()` now live in `db.py` as the single tunable source of truth. `db.get_feed()` orders its candidate pool by decayed rank before source-balancing. `deploy-pages.yml` imports `db` and — after assembling all runs — flattens, dedups, and sorts every pick by decayed rank, emitting one ranked run so `picks_data.json` arrives already in final order. `index.html`'s client-side sort and its `DECAY_HOURS_PER_POINT` / `rankScore` / `ageHours` / `itemDate` helpers were removed; the page now renders the order it's given. Age basis is `published_at`, falling back to `scored_at` / run time, with no date → age 0 (graceful). The 48h retention window is unchanged.

## [2026-06-27] Tune: feed retention window tightened 72h → 48h

The live feed (`deploy-pages.yml`, `s.scored_at >= -48 hours`) and the `db.py` `get_feed()` candidate window (`timedelta(hours=48)`) were narrowed from 72h to 48h, matching the ingest freshness cutoff (`BACKLOG_CUTOFF_HOURS = 48`). Stories now drop off the feed ~48h after scoring instead of 72h, for a punchier "last ~2 days" feel. Both are single constants if a different feel is wanted later.

## [2026-06-27] Redesign: rebuilt the feed UI as an Apple-News-style reading app

Full ground-up rewrite of `index.html` after a `/grill-me` discovery session (captured in `brainstorms/2026-06-27-blank-ui-redesign.md`). The old warm-cream + serif "editorial costume" read as a generic AI news app; this replaces it with a clean, premium, consumer reader inspired by Apple News, designed honestly around the fact that only ~40% of even top-scored items have an image. Changes: (1) **type** — dropped Newsreader serif + DM Mono for Schibsted Grotesk (display) + Hanken Grotesk (text); (2) **palette** — cool whisper-warm near-white + near-black, single Aimé Leon Dore forest-green signature, full **light + dark** theme via CSS variables; (3) **structure** — killed the busy hero + 2-up mini-grid; now one big lead card + a uniform thumbnail-right row repeated down (calm via repetition, rows look intentional with or without an image); (4) **score** — replaced the numeric pills with a quiet rarity-gem system: a small colored diamond keyed to score (blue = 8 Rare, purple = 9 Epic, gold = 10 Legendary), with 6–7 left unmarked; no numbers, no labels, and no glowing card borders; (5) **headlines** — real source titles only (drops the `angle`/`why` rendering, matching the stated product principle); (6) **clustering** — demoted the boxed strip to a quiet "Covered by Reuters, BBC +4 more" line that expands on tap; (7) **shell** — added a 5-tab bottom bar (Feed / Niches / Catch-up / Search / Profile) for a native-app feel, removed the All/Top/Live top filters (single ranked river; trending now shows as a quiet inline chip); (8) **interactions** — pull-to-refresh, card-tap/haptic feedback, skeleton loading, staggered reveal, save/share, and the "Not for me" correction loop (local hide + Undo, best-effort POST to `/api/vote` when `VOTE_TOKEN` is wired). Niches/Catch-up/Search/Profile are real-but-simple (onboarding flow deferred to its own session). Data contract with `picks_data.json` is unchanged; `__VAPID_PUBLIC_KEY__`/`__VOTE_TOKEN__` placeholders preserved.

## [2026-06-27] Feat: X + Google trends re-added to the continuous engine

Lifted the Apify trend-fetching from the legacy `daily_curator.py` into `ingest.py` (`_run_apify_actor`, `_twitter_trend_topics`, `_google_trend_topics`, `fetch_trends`) and added a "Fetch Trends" stage in `run_pipeline.py` after Ingest. Trend topics are inserted as normal items — with a clickable search URL and a date-stamped description — so they flow through the same triage → score → rank pipeline as articles (and later, niche matching). Three safeguards: (1) **throttled** to `TREND_REFRESH_MINUTES = 180` (~3h) per trend source via `last_polled_at`, so the every-10-min engine doesn't pay Apify each run — ~8 refreshes/day keeps estimated spend under Apify's free $5/mo tier (hourly would overrun it; Google Trends is pay-per-result + platform usage and is the cost driver); (2) **date-bucketed** URL/dedup hash so a topic resurfaces at most once per day and never re-scores within a day; (3) **graceful no-op** if `APIFY_API_TOKEN` is unset. Only the top `PER_SOURCE_CAP` topics per source are inserted. Added `APIFY_API_TOKEN` to `blank.yml`'s pipeline env.

## [2026-06-27] Perf: cap triage/scoring to 15 newest items per source

Added `PER_SOURCE_CAP = 15` in `db.py`. `get_untriaged_items()` and `get_unscored_escalated_items()` now rank items per source by recency (a window function over ALL items per source, so the cap doesn't refill as items move through the pipeline across runs) and only process the newest 15 per source. The feed already balances each source to a small display share, so triaging/scoring more than this per source was wasted spend — the Haiku gate kills ~0% of mainstream-news items, so almost everything was reaching Sonnet. On the current corpus this cuts processed volume from 5,259 to 661 items (~87% fewer triage/score calls) and bounds the existing escalated backlog from ~5,000 to ~600 unscored items, with no change to what the feed can display.

## [2026-06-27] Feat: feed leads with real headlines (drop AI hook/why generation)

Scoring no longer generates a rewritten "hook" or per-item "why". `score.py` now asks Sonnet for score + criteria + soft-floor flags only, and `max_tokens` drops 2048 → 1024 — cutting the most expensive line, Sonnet output tokens. `record_score()` in `db.py` makes `why`/`hook` optional (default `""`) so no schema migration is needed. `publish.py` is unchanged: it already falls back to the real article title when the hook is empty, so the feed now leads with authentic headlines and the editorialized hook is removed from the reading experience.

## [2026-06-25] Feat: OG image enrichment for blank engine items

`ingest.py` only extracted inline RSS images, leaving 76% of items without thumbnails (TechCrunch: 0%, Google News: 0%, Hypebeast: 0%). Added `_fetch_og_image()` and `enrich_og_images()` to `ingest.py` — after ingestion, items with no `image_url` from the last 15 minutes are enriched by concurrently fetching `og:image` from their article pages (10 workers, 5s timeout each). Added as a new "Enrich OG" stage in `run_pipeline.py` between Ingest and Triage. Also adds `requests` to blank.yml's pip install line.

## [2026-06-25] Fix: blank.db articles show actual publish date, not scored_at time

Articles from blank.db were displaying "1h ago" based on when the engine processed them (`scored_at`), not when they were actually published. For example, a Jun 23 article scored today was showing "1h ago" instead of "2d ago". Fix: `published_at` is now included in the pick object written to picks_data.json. `index.html` uses a new `agoFromISO()` helper and prefers `published_at` over `runDate`/`runTime` when it's available. picks/*.md items are unaffected (no `published_at` field).

## [2026-06-25] Fix: feed section labels (Morning/Afternoon/Evening) now use CT

In `parse_file()` in `deploy-pages.yml`, the Morning/Afternoon/Evening label was being calculated from the raw UTC hour in the filename before the timezone conversion to CT. Moved the label block to after the `dt_ct` conversion so it uses the CT hour, matching the behavior already used in the blank.db merge section of the same file.

## [2026-06-25] Fix: deploy-pages.yml now triggers after Blank Engine runs

`deploy-pages.yml` triggers on `push` to main, but GitHub's security rule blocks bot pushes (via `GITHUB_TOKEN`) from triggering other workflows. So every time `blank.yml` committed and pushed `blank.db`, `deploy-pages.yml` never fired and the feed never rebuilt. Fix: added "Blank Engine" to the `workflow_run` list so `deploy-pages.yml` triggers on completion of `blank.yml` directly, regardless of who made the push.

## [2026-06-25] Fix: publish stage removed; push retry hardened; ingest typo fixed

Three bugs found during end-to-end code review. (1) **`run_pipeline.py` publish stage removed**: `publish.run_publish(no_push=True)` still writes `index.html` to the repo root even though `blank.yml` no longer commits it. An uncommitted change to a tracked file (`index.html`) causes `git pull --rebase` to abort with "Cannot rebase: You have unstaged changes" — silently preventing `blank.db` from ever being pushed. Removed the publish stage call entirely; `deploy-pages.yml` builds the feed from `blank.db` directly and the Canvas `index.html` is never generated by the pipeline. (2) **`blank.yml` push retry now fails loudly**: the retry loop exited 0 even when all 4 attempts failed (`sleep` returns 0), making GitHub Actions show the step as green on total failure. Added a `PUSH_OK` flag and `exit 1` if it's never set. (3) **`ingest.py` `__main__` typo**: `_sqlite3.Row` → `sqlite3.Row` (does not affect the pipeline, only direct `python ingest.py` invocations).

## [2026-06-25] Fix: blank engine feed staleness — 72h window + push retry

Two fixes for the blank engine's stale data problem. (1) **`db.py` `get_feed()` window 48h→72h**: the feed query filtered by `fetched_at >= 48h ago`, but all 55 items in `blank.db` were from June 23 (~49h old), leaving only 4 items visible. Widened to 72h to match the `deploy-pages.yml` query window (`scored_at >= 72h`). (2) **`blank.yml` git push retry loop**: `blank.yml` commits `blank.db` and does `git pull --rebase + push`, but `breaking_news.yml` and `daily_curator.yml` also push to main constantly — a rebase conflict silently aborts the commit step (the workflow shows "success" via the "nothing to commit" exit-0 path). Added a retry loop matching the pattern used in other workflows: up to 4 attempts with exponential backoff (10s, 20s, 30s, 40s). Also adds HTTP status code checking to `ingest.py`'s `poll_source()`: feedparser silently returns an empty entries list on 403/404 without raising, causing sources to appear as "new=0, errors=0" when they're actually blocked.

## [2026-06-25] Fix: cluster strip fully clickable; perspectives show source names

Clicking anywhere on the cluster strip banner now expands it (not just the arrow). Added `cursor: pointer` and a hover tint to make the strip feel interactive. Fixed the empty-drawer problem: picks files don't have "Other angles" URLs, so `related_articles` is always null. Expanded drawer now falls back to showing each cluster source name as a "Also covering this story" entry. Static source rows are non-clickable but visually informative. Picks that do have `related_articles` URLs continue to show clickable article links.

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
