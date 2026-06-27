# Blank UI/UX Redesign: Brainstorm / Discovery Notes
Date: 2026-06-27 · Goal: Figure out what Blank should actually look and feel like (the user dislikes the recently-shipped design), then implement it.

## Summary / key decisions

### THE DIRECTION (locked)
1. **Feel:** escape "generic AI news app." True north = **Apple News** — consumer-premium, image-forward where possible, high polish, generous whitespace, low chrome. Polish comes from typography/spacing/hierarchy, not gimmicks.
2. **Image reality:** only ~29% of items (and ~40% of even top-scored) have images — that's near the real ceiling. So NOT purely image-forward. Big image LEAD card + premium **thumbnail-right rows** that look intentional with or without an image.
3. **Typography:** **serif gone.** One neutral safe sans for headlines + UI (lead candidate **Inter**). Drop DM Mono costume.
4. **Palette:** cool-neutral, but a **whisper of warmth** (~1–2% warm near-white, NOT cream) so the green has a home. Near-black text. (Option C.)
5. **Signature color:** **Aimé Leon Dore forest green** (deep muted pine, ≈#1E3A2B-ish — tune visually), used sparingly.
6. **Score:** no numbers, no multi-color loot glows. **Quiet-luxury rarity tiers** — ~3 near-monochrome tiers; top tier gets the green treatment / "Editor's Pick" mark / slight elevation; maybe one reserved restrained gold *hairline* for true-top. Gamer structure, premium paint.
7. **Headlines:** **real source titles only** (matches CLAUDE.md). No AI hook, no "why" blurb on cards.
8. **Structure:** **two card types** — 1 big lead + 1 uniform thumbnail-right row. Mini-grid killed. Optional occasional break card. Calm via repetition.
9. **Clustering:** quiet inline line ("Reuters, BBC +4 more") + expand on tap. No boxed strip.
10. **Nav:** **5-tab bottom bar** (Feed / Niches / Catch-up / Search / Profile) — reads "real native app." v1 depth: Feed full, Niches + Search real-but-simple, Catch-up + Profile honest stubs. **Top-of-feed All/Top/Live removed** → single ranked river.
11. **Theme:** light + dark from day one via CSS variables.
12. **App bar:** near-empty, name-agnostic (name not final), swappable sans wordmark, drop "N picks" counter.

### Also in scope for this build (from Q16)
- Card actions: quiet **save/bookmark + share**.
- **Correction loop** ("this wasn't noise / less like this") — build now; wire to existing VOTE_TOKEN/engagement infra.
- Bottom-tab **iconography**: Apple-clean.
- **Micro-interactions**: pull-to-refresh, card-tap animation, polished loading state, tasteful motion.
- **Niches/Catch-up/Profile** tabs = stubs (Niches = real-but-simple picker; onboarding flow is a separate future session).

### Open items / flags
- "Live"/trending signal lost its home when top nav was removed → find a home later (section, marker, or re-add). Non-blocking.
- Exact ALD green hex + warm-white value → tune on screen.
- Rarity tier cutoffs (which scores map to which tier) → define in design.
- Break-card cadence (every ~15 rows?) → decide in design.
- Onboarding / niche-picker flow → separate grill session.

---
_(original starting-point notes below)_

- Starting point: current `index.html` is a warm-neutral editorial layout — Newsreader serif headlines, DM Sans body, DM Mono wordmark ("blank."), single orange accent (#C47B2D), cream surfaces. Structure per feed: one hero card → "More Stories" 2-up mini grid → list cards with 72px thumbnails + score pills + cluster strips ("Also covering this story"). Filter pills: All / Top Picks / Live. Infinite scroll.
- NOTE/tension to resolve: the live UI still renders AI hooks (`firstHook(p.angle)`) and `p.why` italic blurbs, which contradicts CLAUDE.md's "real headlines only, AI hook/why generation removed."

## Current-design inventory (from reading index.html)
- **Type:** Newsreader (serif, headlines), DM Sans (UI/body), DM Mono (wordmark, meta, timestamps)
- **Palette:** cream/white surfaces (#FFF, #F9F8F5), warm grays for ink, single orange accent (#C47B2D / #A86820 text / #FEF8EF bg)
- **Components:** app bar w/ wordmark + "N picks" meta; horizontal filter pills; hero card (268–334px, image + gradient + score + "Top Story"); 2-up mini grid; list cards (thumb + score pill + source + time + why blurb); cluster strip w/ expandable "perspectives" drawer; warm deterministic placeholder colors when no image.
- **Score pills everywhere** (the editorial-scoring signal is front and center)

## Q&A log
_(checkpointed one answer at a time)_

### Q1 — The gut reaction / what's the wince
- Asked: When you open Blank, what's the first thing that makes you wince?
- Captured: It's **the feel** — "feels like a generic AI news app." The **visual language doesn't speak to him** either. Agrees the **hero + mini grid is busy and cluttered**. The **scoring "might have to be a little more discrete"** (less in-your-face than the current pills-everywhere treatment).
- Decisions seeded: (1) escape the generic-AI-news-app feel, (2) replace the visual language entirely, (3) simplify/de-clutter the hero+grid structure, (4) make the editorial score quieter/more subtle.
- Flags: none

### Q2 — The feeling / aesthetic target + real references
- Asked: What should it feel like in the first 2 seconds, and name 1–2 real apps/sites you love and would steal from.
- Captured: Not sure about the emotional adjective yet. BUT named three concrete references he likes: **Apple News, Feedly, Inoreader**.
- **Key inference (big deal):** all three are clean, content-forward, **sans-serif**, neutral, modern reader UIs with image support and high scannability. None use a warm-cream + serif "editorial magazine" costume. → The current design's whole visual language (Newsreader serif on cream, orange accent, editorial-cosplay) is likely the *opposite* of his actual taste. The redesign should lean **clean / neutral / sans-serif / content-forward reader**, not print-magazine.
- Decisions seeded: visual direction = modern clean reader (Apple News / Feedly / Inoreader family), not editorial-serif.
- Flags: need to pin down *which specific qualities* of each reference he likes (layout density? typography? cards vs list? color/chrome?) → next question.

### Q3 — Which reference is true north + what to steal
- Asked: If you could keep only one visual anchor (Apple News vs Feedly/Inoreader), which IS Blank, and what's the one thing you'd steal?
- Captured: **Apple News is true north.** Loves its **image-forward cards** and **how polished it feels** — "truly a beautiful app." (Feedly/Inoreader value = scannability/density, not their visual style.)
- Decisions: Visual anchor = **Apple News** — consumer-premium, image-forward cards, high polish, generous whitespace, low chrome, big bold sans headlines.
- Flags: Blank's RSS feed frequently has NO good image (currently falls back to warm placeholder colors). Apple News works *because* publishers supply great images. If we go fully image-forward, the no-image case is make-or-break → must resolve.

### DATA CHECK — image coverage in blank.db (grounding for Q4)
- `items` table: 5,390 rows. `image_url` non-empty on **1,595 → only ~29%**. **~71% of items have no image.**
- Implication: a *purely* image-forward Apple-News layout would show a placeholder/colored block on ~7 of every 10 cards. The no-image treatment isn't an edge case — it's the majority state. Whatever we design has to look *intentional and premium* when there's no image, not "broken card." This is the single biggest design constraint.

### Q4 — The image problem (29% coverage) — A/B/C paths
- Asked: Accept Blank can't be purely image-forward (make text premium, B+C), or invest in fixing image supply (A)?
- Captured: Mo pushed back — **"the old Blank almost always had a picture attached though."** He believes high image coverage IS achievable because the previous product had it. → Don't accept the 29% as fixed. Investigate WHY old Blank had images and whether it's replicable in the engine.
- Hypothesis to test: old Blank (daily_curator.py, Inoreader, 3x/day) curated a SMALL set of top picks, so it could (a) cherry-pick items that had images, and/or (b) Inoreader/scraping supplied them. The new engine scores a GLOBAL feed of thousands → 29% average. A *curated* view (top-scored subset) may have much higher image coverage than the raw 29%.
- ACTION: read old curator for image logic; check whether high-scoring items correlate with having images.
- Flags: resolve image-coverage reality before locking layout.

### INVESTIGATION RESULT — why old Blank had images & whether it's replicable
- **Image coverage by score tier (scored items):** 9→30%, 8→43%, 7→40%, 6→33%, 5→25%, 4→19%, 3→4%, 2→7%, 1→0%.
  - Feed (score≥6): **37%** with image. Top picks (score≥8): **41%**. Even the *very best* content tops out ~40%.
  - → **Curating to top picks does NOT yield near-100% images** (29% raw → only ~40% at the top). Hypothesis busted.
- **Engine already OG-enriches every fresh item** (`ingest.enrich_og_images`: items <15min old with no image get an og:image fetch). So the ~70% gap is largely the *real ceiling* — RSS had no image AND og:image fetch found nothing. Not a fixable throttle. (Many Google-News aggregator links / text blogs genuinely have no og:image.)
- **Why old Blank "almost always had a picture":** it curated a TINY set (3x/day, ~10–30 picks), so it could afford full og-enrichment on every pick AND it preferred the image-having version when merging duplicates (`daily_curator.py:569` ranks `bool(image)` first). It showed few items and effectively favored image-rich ones. The new engine shows HUNDREDS from a global feed → ~40% is the honest ceiling.
- **The real tension:** Apple-News image-forward look vs. the "rank everything, never hide / living feed" vision. You can't have near-100% images AND show the full ranked feed — unless you drop/deprioritize the 60% image-less items (conflicts with the product principle) or synthesize images.
- **Reconciliation (key insight):** Apple News itself is NOT all big image cards — it's a few big image LEAD cards + many clean compact list rows. Apple-News *polish* comes from typography/spacing/hierarchy/restraint, not from every card being a photo. So we CAN get the Apple-News feel at ~40% coverage via: big image cards for image-rich top items → premium text-forward list rows for the rest. (This is path C, and it's literally Apple News's own structure.)

### Q4 RESOLVED — image strategy
- **DECISION: Accept the ~40% image ceiling and chase Apple-News *polish* (typography/spacing/hierarchy), not universal photos.** Structure = big image lead cards for image-rich top stories → premium text-forward rows for the rest. Keep the comprehensive ranked feed (don't shrink back to a tiny curated set). Images are delight where available, not a requirement. This is a locked foundation for the layout.

### Q6 — Palette & accent
- Asked: Cool-neutral white/gray over warm cream? No-color vs one signature color?
- Captured: (1) **Cool-neutral white/gray — agreed** (drop the cream). (2) **One signature color = GREEN**, specifically **Aimé Leon Dore's green** — ALD's deep, muted **forest/hunter green** (≈ deep pine, roughly #1E3A2B / #213D2E range — CONFIRM exact hex visually).
- Decisions: Accent = a deep ALD-style forest green, used sparingly (active filter, links, Live signal, score?). Near-black text on white.
- **TENSION surfaced (→ Q7):** ALD's actual brand world is WARM — ecru/cream + forest green + tan, quiet-luxury vintage-prep. We just chose *cool* white. So: does Mo want ALD's *green only* on a cool Apple-News canvas, or ALD's *whole palette* (warm ecru + green)? Resolve before locking surfaces.

### Q7 — Cool vs warm canvas (the ALD-green coherence tension)
- Asked: A (cool white + green accent), B (full warm ALD ecru world), or C (mostly-cool near-white with a whisper of warmth + green signature)?
- Captured: **C — try it, adjust live if not good.** Near-white that's *barely* warm (reads clean white, not cream) + near-black text + ALD forest green signature. Keeps Apple-News crispness while giving the green a home. Not precious about it — iterate on screen.
- Decisions: Surface = ~1–2% warm near-white (NOT the old cream). Locked pending visual tuning.

### Q8 — Score treatment (how the editorial score expresses itself)
- Asked: A (kill number, order+size only), B (kill number, quiet mark on top tier), C (keep tiny whispered number)?
- Mo's counter-proposal: **gaming RARITY TIERS** — color-coded by score like loot rarity: Gray=common, Blue=rare, Purple=epic, Orange/Gold=legendary. Previous Blank iteration had **tiles glow** these colors by score. Mo is a gamer; has affection for this; wants honest thoughts.
- Claude's honest assessment:
  - **Strong kernel:** tiered, color-coded, NON-numeric, instantly scannable, adds collectible/dopamine pull. The *instinct* (tiers not digits) aligns with option B and is genuinely good. Score becomes pre-attentive (spot a "legendary" at a glance).
  - **But the literal 4-color glow conflicts with everything just locked:** we chose Apple-News restraint, ONE signature color (ALD green), minimal chrome, quiet-luxury. A gray/blue/purple/gold glow ladder is maximalist gamer-RGB — the OPPOSITE of restraint, and colored glows read as crypto/web3/gamer-dashboard = arguably MORE "generic tech app," risking the exact wince. ALD would never glow purple.
  - **Brand conflict:** orange/gold=legendary but we moved OFF orange; green is the brand but isn't in the rarity ladder → muddies the signature.
  - **Semantic risk:** loot rarity = power/drop-rate; news score = editorial importance. A tragedy scored 9 glowing "legendary gold" feels tonally off / trivializing.
  - **Genuine tension named:** Mo's two loves — gamer loot aesthetic vs ALD quiet-luxury — fight on the surface. Pick which wins.
- Claude's synthesis proposal: **keep the rarity *structure* (discrete quality tiers, no number), drop the RGB glow.** Express tiers in the ALD/Apple-News language — e.g. 2–3 tiers, near-monochromatic: top tier gets the green accent + a subtle elevated treatment; lower tiers stay neutral. "Quiet-luxury rarity."
- **RESOLVED: Quiet-luxury tier version wins.** Keep rarity *logic* (discrete tiers, no number, scannable), render in ALD/Apple-News language. Direction: ~3 near-monochrome tiers — ordinary = plain; top tier = green treatment (keyline / "Editor's Pick" mark / slight elevation); optionally one reserved restrained flourish (warm-foil/gold *hairline*, NOT a glow) for the rare true-top item. No numeric pills, no multi-color glows. Gamer *structure*, premium *paint*. (Exact tier cutoffs + visual spec TBD in design.)

### Q9 — Headlines: real titles vs AI hooks
- Asked: Real source headlines only (A, matches CLAUDE.md) vs keep AI hook + "why" blurb (B)?
- Captured: **A — match CLAUDE.md. Real source headlines only.** Remove `firstHook(angle)` hook + `why` blurb from cards. AI voice = selection/ranking/clustering only, never rewritten words. (Live `index.html` currently violates this at line 809/810/864 — fix in implementation.) On-tap "catch me up" summary is the future home for AI text.
- Decisions: Card content simplifies to → real title + source + time + tier treatment. No hook, no why.

### Q10 — Card types & rhythm (de-cluttering)
- Asked: Two-card-type discipline (1 lead + uniform repeating row), and thumbnail-right rows vs image-on-top cards?
- Captured: (1) **Agree — two card types total:** one big image-forward LEAD card at top (degrades to large text lead if #1 has no image; ~40% coverage means the single top slot can almost always find an image), then ONE consistent repeating row all the way down. **Kill the 2-up mini-grid.** Optional: one larger "break" card every ~15 rows for rhythm (TBD). (2) **Repeating row = thumbnail-RIGHT rows** (Apple News/Inoreader pattern): headline + source + time + tier cue, small thumb on the right when an image exists, clean text-only row (same layout) when it doesn't. Dense + scannable; survives the 71%-no-image reality.
- Decisions: Calm comes from repetition, not variety. Lead + uniform thumbnail-right row. Mini-grid removed.

### Q11 — Clustering treatment  [CORRECTED — Mo initially said B, then clarified A]
- Asked: Quiet inline line + tap (A), keep visible restyled cluster strip (B), or move to detail view (C)?
- Captured: **A — quiet inline line + expand on tap.** (Mo first said B, then corrected: he misread the question.) Clustering = a quiet convenience, NOT a boxed shown-off feature. On a clustered row, add ONE subtle muted line (e.g. *"Reuters, BBC +4 more"*) under the headline; reveal full perspectives on tap, not inline boxes. No separate cluster strip box. Keeps the uniform-row discipline and the calm feed.
- Decisions: Drop the boxed cluster strip + inline perspectives drawer. Replace with a single muted source line per clustered row + on-tap expand.

### Q12 — Navigation & niche dimension
- Asked: (a) Bottom tab bar now vs single page w/ top pills; (b) niche pills now vs keep All/Top/Live.
- Captured: **Bottom tab bar — emphatic YES** ("so so so much better"). Reads as real native app; core to the polish. Part (b) not yet explicitly answered → confirming tab set + top-nav next.
- Decisions: Introduce a **bottom tab bar now** (PWA→native shell). Tabs likely Feed / Niches / Catch-up / Profile (some may be stubs initially — CONFIRM). Top-of-feed nav: lean = keep simple All/Top/Live until niches wired (CONFIRM).

### Q13 — Tab set + top-of-feed nav
- Asked: Tab set = Feed/Niches/Catch-up/Profile (+Search where?); keep All/Top/Live top nav?
- Captured: (1) **Search goes in the bottom bar too → 5 tabs.** Set = **Feed / Niches / Catch-up / Search / Profile** (order TBD; likely Feed first). (2) **Remove the top-of-feed nav (All / Top / Live) entirely** — Feed becomes a single clean ranked river (very Apple-News "Today"). No filter chips at top.
- Implication to note: removing All/Top/Live drops those as explicit filters. "Top Picks" is largely redundant (ranking already floats the best up). "Live"/trending may need a future home (a section, a marker, or re-add later) — flag, don't block. v1 build depth: Feed = full; Niches = real-but-simple picker; Search = real-but-simple; Catch-up/Profile = honest stubs.
- Decisions: 5-tab bottom bar; single ranked-river Feed with no top filter pills.

### Q14 — Dark mode
- Asked: Light-only for v1 (A) or build light+dark now via CSS variables (B)?
- Captured: **B — build both now.** Bake light + dark into CSS variables from the start (cheaper during a from-scratch rebuild than retrofitting). ALD forest green on near-black is a strong dark-mode look. Must be done well (half-done dark mode looks cheap).
- Decisions: Theme tokens from day one; ship light + dark.

### Q15 — Wordmark / app bar
- Asked: Near-empty, name-agnostic top bar?
- Captured: **Totally agree.** Top bar near-empty + name-agnostic (name isn't final: Keen/Caret/Blank). Simple text wordmark in the new sans (easy to swap), optional search affordance, **drop the "N picks" counter**. No date/greeting/logo clutter for now.
- Decisions: Minimal, swappable wordmark; no meta counter.

### Q16 — Completeness backstop (deferred items)
- 1. **Card actions** → aligned: quiet **save/bookmark + share** on cards, default otherwise.
- 2. **Correction loop ("this wasn't noise / less like this")** → **BUILD NOW** (in scope for this redesign). Cards need a subtle correction affordance. (Infra exists: `VOTE_TOKEN` in index.html + `engagement` table in blank.db.)
- 3. **Onboarding / niche picker** → aligned: stub the Niches tab now, grill onboarding as a SEPARATE session later.
- 4. **Micro-interactions** → **implement all**: pull-to-refresh, card-tap animation, polished loading state, tasteful motion/haptic-ish polish.
- 5. **Iconography** → aligned: Apple-clean tab icons (Claude picks).
- Decision: proceed to BUILD. Read `~/.claude/skills/frontend-design/SKILL.md` first (per CLAUDE.md), then mock Feed + 5-tab shell in light & dark.

### Q5 — Typography
- Asked: Sans-first w/ serif gone? Personality vs safe-neutral?
- Captured: (1) **Serif gone — agreed.** (2) **Safe-neutral for now** (Inter-style: clean, ubiquitous, Apple-News-adjacent; not flashy/distinctive). Single high-quality neutral sans for headlines + UI. Can revisit personality later.
- Decisions: Drop Newsreader serif entirely. Type system = one neutral sans (lead candidate **Inter**). Drop DM Mono "blank." wordmark treatment too (mono was part of the costume) — revisit wordmark separately.

## Open flags (pending input)
_(none open)_
