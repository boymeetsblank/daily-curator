# CHANGELOG

All notable changes to the daily-curator project are documented here. Newest entries at the top.

---

## [2026-05-20] Live feed: cluster-based escalation to main feed

When multiple live feed items converge on the same story, they now automatically cluster and escalate as one unified main feed pick. How it works: after each quality gate pass, a Haiku clustering call assigns new items to existing clusters or creates new ones (e.g., "Knicks win Game 1 of NBA Eastern Conference Finals" groups Knicks, Josh Hart, Harden, and Mike Breen signals together). When a cluster hits 3 items, Sonnet synthesizes all signals into one editorial story — headline, Why It Matters, and hook — and writes it to the main feed. Re-escalates every 3 additional items so evolving stories stay current. Cluster state persists in `breaking_news_state.json` with a 24-hour TTL.

## [2026-05-20] Live feed: tighter Haiku scoring gate + escalation threshold restored to 9

Rewrote the Haiku scoring prompt to fix junk flowing into the main feed after the May 19 overhaul. Four changes: (1) replaced "score generously" with "be strict — when in doubt, score lower"; (2) added explicit auto-1 list covering political content, generic social posts (good morning/lifestyle/emoji filler), local/trade niche articles, and bare trending topic names with no news context; (3) tightened Bluesky guidance — viral engagement alone is not enough, post must contain actual news or a genuine cultural flashpoint; (4) tightened the 8-anchor to require broad audience significance, not just niche relevance. Escalation threshold raised 8→9 so only "you have to tell someone right now" items reach the main feed.

## [2026-05-20] Cut Apify YouTube actor — replaced with free RSS

`fetch_youtube_trends()` in `daily_curator.py` now uses the free public YouTube trending RSS feed instead of the `streamers~youtube-trending-videos` Apify actor. Same data, zero Apify compute cost. Saves 3 actor runs/day. The live feed was already using this free RSS endpoint — the main curator now does the same.

## [2026-05-19] Live feed overhaul — more active, more social, smarter scoring

Raised live feed quality gate from 6→5 and Sonnet escalation threshold from 9→8, so more content surfaces and more reaches the main picks feed. Added Reddit 6-hour age filter (hot.json can return stale posts). Added Bluesky What's Hot as a source (free public API, no auth). Updated Haiku prompt with velocity/recency signal and Bluesky context. Added pip caching to breaking_news.yml to reduce run latency. Lowered Reddit upvote threshold 200→150. Fixed 3 broken Reddit RSS URLs (missing .rss suffix on r/InterestingAsFuck, r/NotTheOnion, r/Damnthatsinteresting). Added r/nextfuckinglevel, r/BeAmazed, r/PublicFreakout, r/streetwear to sources. Added Reddit first-mover signal to main curator scoring prompt. Fixed main feed auto-opening archive when today only has live picks.

## [2026-05-10] Main feed: stronger cross-source signal + any-topic scoring philosophy + MMA sources

Three changes to catch high-value stories that were slipping through. (1) Cross-source threshold lowered 3→2: stories covered by 2+ sources now trigger the TRENDING flag, giving more stories the benefit of the doubt. (2) Cross-source bonus upgraded to hard score floors: 2+ sources → minimum 7, 3+ sources → minimum 8, applied regardless of topic. (3) Haiku prompt rewritten from category-list framing ("sneakers, music, sports...") to audience-first framing ("well-connected, culturally aware person") — anything genuinely significant has a fair shot regardless of topic bucket. (4) Added MMA Fighting, MMA Junkie, and r/MMA as sources so major fight events surface reliably.

## [2026-05-07] Live feed: purely reverse-chronological, no score pinning

Removed the two-tier sort that pinned 9+ items to the top of the Live feed. The Live section is now strictly newest-first. Score-based pinning belongs in the main feed only.

## [2026-05-07] Live feed: MAX_FEED_SIZE raised 20→40

Increased the live feed display cap from 20 to 40 items. With the pipeline now generating 5–12 new items/hour during peak hours, the old cap was filling up within 2–4 hours and blocking new entries until older items expired.

## [2026-05-07] Live feed volume: social candidates restored, 6 new RSS sources, 5 subreddits, free Google Trends refresh, 4h failed-item window, wider article window

Six changes to restore and grow live feed candidate volume after the May 6 overhaul thinned the pipeline: (1) restored `build_social_candidates()` call so X/Google/TikTok topics re-enter as Haiku-scored candidates; (2) added 6 RSS sources — Pitchfork, Billboard, Rolling Stone, The Ringer, Deadline, Bleacher Report; (3) breaking news monitor now tops up Google Trends data from the free unofficial daily endpoint when `social_trends.json` is >60 minutes old — no Apify cost; (4) added 5 subreddits — r/hiphopheads, r/sneakers, r/soccer, r/movies, r/music; (5) failed items (score 1–5) are now suppressed for only 4 hours instead of permanently, so slow-burn stories can resurface; (6) `FEED_WINDOW_MINUTES` widened 60→90 to reduce misses from delayed GitHub Actions runs.

## [2026-05-06] Live feed scoring overhaul — tighter quality gate, no bare social trends

Rewrote the Haiku scoring prompt in `breaking_news_check.py` to match the main curator's scoring anchors (10: cultural moment, 9: tell someone now, 8: bring up today, 7: worth surfacing, 6: minimum bar). Tightened the politics filter to cover routine political/geopolitical/economic policy content while preserving a carve-out for genuinely historic moments. Removed bare X/Google/TikTok trend topic names as live feed candidates — social context signal is preserved in the scoring prompt but bare names no longer enter the pipeline. Dropped Reddit hot post threshold from 500 → 200 upvotes and raised per-source cap from 3 → 5 to increase candidate volume.

## [2026-05-06] Remove Reddit and Instagram Apify actors to stay within free tier

Reddit Trending was redundant (r/popular and r/all already covered by direct RSS). Instagram scraping requires browser automation — too expensive for the free plan. Apify stack is now 4 lightweight actors: X, Google, YouTube, TikTok.

## [2026-05-06] Raise per-subreddit article cap to 25

Reddit sources (any source name starting with "r/") now get a cap of 25 articles per run instead of the default 15. All other sources remain at 15. The overall 200-article hard cap still applies.

## [2026-05-06] Add r/popular and r/all as wide net sources

Added r/popular and r/all to sources.json as direct RSS feeds under the "wide net" category.

## [2026-05-02] Fix: Live section disappears overnight — extend TTL, commit social trends

Extended `BREAKING_NEWS_TTL_HOURS` from 6 → 12 so items from the previous evening survive the overnight dead zone (US feeds go quiet ~11 PM CT, next curator run at 7:30 AM CT). Fixed `social_trends.json` never being committed: added it to `git add` in `daily_curator.yml` so X, Google, and TikTok trending candidates are available to the breaking news monitor after each 3×/day curator run. Both issues were causing the Live section to show nothing for 8+ hours overnight.

## [2026-05-01] Digest slides: sentence-aware body copy + substack text on image slides

Body copy on story slides now stops at complete sentence boundaries instead of truncating mid-sentence with "...". Added `_wrap_sentences` helper that accumulates sentences until adding another would overflow the line limit, then stops clean. Also switched the image path to use the Substack copy field (already used by text-only slides) instead of the shorter "why" field, matching the more analytical tone.

---

## [2026-05-01] Hook prompt: natural punctuation guidance

Replaced the blunt "no period at the end of every line" rule with nuanced guidance: punctuate naturally based on rhythm — complete standalone thoughts get a period, fragments flowing as one sentence don't. Fixes hooks like "TIM COOK IS OUT / APPLE JUST HAD ITS BEST QUARTER EVER..." where the first line is a distinct beat that needs its own punctuation.

---

## [2026-04-30] Fix: live feed not updating after breaking news commits

GitHub blocks workflow-triggered pushes (via default GITHUB_TOKEN) from re-triggering other workflows, so breaking_news.yml commits to main were never firing deploy-pages.yml. Fixed by tracking whether a push actually happened (GITHUB_OUTPUT) and explicitly calling `gh workflow run deploy-pages.yml` only when new items were committed.

## [2026-04-30] Digest slide polish: remove borders, widen dividers, anchor text-only layout

Removed the outer border from all slides (cover and story). Widened the divider rule from 60px to 160px on both image and text-only story slides. On text-only slides, switched the content block from vertically centered to bottom-anchored (matching the image-path layout) and added a bottom gradient overlay starting at y=600 to ground the text zone instead of letting it float.

## [2026-04-30] Hook prompt: drop TRIGGER mechanic, break three-sentence pattern

Removed the `[TRIGGER: X]` emotional-label requirement — it was forcing Claude into a formulaic "emotion → three parallel sentences with periods" structure. Replaced with guidance to write like a text to a friend: fragments OK, lines can flow together as one broken thought, no period at the end of every line, vary between 2 and 3 lines. Updated the JSON example to show a natural-sounding hook instead of the old "Nobody saw this coming. / Not even the insiders. / It changes everything." pattern.

---

## [2026-04-30] Fix: digest slide headline text no longer clips at right edge

`_wrap_text` and `_truncate_lines` were using `draw.textlength()` (advance-width metric) to check if text fits within the content area. For Bebas Neue at 100px, actual rendered glyph extents exceed the advance width, so long hook lines appeared to fit but overflowed the canvas. Switched both functions to `draw.textbbox()` which returns real pixel bounds (including sidebearings), extracted into a shared `_text_width()` helper.

---

## [2026-05-01] Live feed: lower quality gate to 6, add MAX_FEED_SIZE cap

Lowered Haiku quality gate from `>= 7` to `>= 6` so the live feed consistently accumulates 5–10+ items per hour instead of going sparse during off-peak periods. Updated scoring prompt to define 6 as "the minimum for the live feed" rather than "could wait for the main daily feed." Added `MAX_FEED_SIZE = 20` to cap the total live feed size so active-hour volume doesn't overflow the section.

---

