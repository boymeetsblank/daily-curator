# Feed Cohesiveness: Brainstorm / Discovery Notes
Date: 2026-06-29 · Goal: Define what "cohesive / calm" should mean for the Blank feed, diagnose why it currently feels overwhelming ("a lot all at once"), and decide the design principles + changes that fix it.

## Summary / key decisions

**The problem (diagnosed):** the live flat ranked river causes **macro topic-whiplash** — unrelated stories back-to-back (politics → sneakers → finance → reddit). That's the overwhelm, NOT too much content and NOT per-row visual noise. So "cohesive" ≈ *stories flow by theme*; "calm" ≈ *clear hierarchy + a bottom*.

**Decisions (settled):**
1. **Cohere by default** (the product organizes it); user sort/filter is at most a secondary escape hatch.
2. **Top Stories block** leads: **hero (#1 overall) + 5–7 more = a deduped, cross-niche spread** ("the most important thing + the biggest thing in each part of my world"). Needs dedup so one event can't take two slots.
3. **Bounded by default** — feed ends with a **"You're all caught up"** beat; the endless discovery river is an **opt-in tail** ("Keep reading"). (Ties to the catch-up ritual.)
4. **Single calm column, NO boxes/carousels** — boxes are what made the abandoned rails attempt look bad.
5. **Below Top Stories = prototype 3 variants** (decide by seeing, not on paper):
   - **A** soft-smoothed river (topic runs via ordering only, no labels)
   - **B** quiet hairline topic labels (calm sections, no boxes)
   - **C** bounded niche previews: top news per niche + a **"Read more"** drill-down (current row layout, NOT swipeable cards)
6. **Method:** change *structure only*, leave rows untouched (clean signal on what ordering does); row-calming is later polish.
7. **Enablers already in place:** the shipped `sections` payload (top_stories + category groupings) feeds all 3 prototypes; "niche" = `primary_category` proxy until onboarding.
8. **Variant C is depth-gated:** big niches (Sports/Entertainment/Business/Tech, 100+ each) are rich; ~6 niches (Science/Health/Climate/World) are too thin for "read more" → prototype C with stocked niches; broad ship depends on niche→source coverage.

**Suggested next step:** hand A/B/C to the UI agent to build behind a toggle on real data (rows untouched); Mo compares and picks. Engine may formalize the Top Stories deduped-spread selection in the payload.

---
_(running synthesis — updated as we go)_

- Starting point: Mo feels the feed is NOT cohesive and is overwhelming.
- **IMPORTANT CORRECTION (Mo, live):** the **Moment + Category rails were NEVER implemented in the UI.** The engine emits the `sections` payload, but `index.html` still renders only the **flat ranked single river** (hero lead card + uniform rows). The UI agent *attempted* the rails but "it wasn't looking good," so it was abandoned. → So the overwhelm Mo feels is with the **CURRENT FLAT FEED**, not with rails. And the rails direction has one failed visual attempt behind it.
- Image coverage is ~88%; favicons + uniform headline weight shipped. Apple News research doc (`2026-06-29-apple-news-research.md`) flags "revisit whether the sectioned feed is the right call at all."

## Q&A log
_(one entry per answer, appended live)_

### Q1 — What makes the current flat feed feel overwhelming?
- Asked: Is the overwhelm mostly (a) topic whiplash, (b) flatness, (c) density, (d) endlessness?
- Captured: **It's (a) — TOPIC WHIPLASH.** Unrelated stories jammed back-to-back (politics → sneakers → finance → reddit), no thematic flow → feels scattered + "a lot all at once." So "cohesive" for Mo ≈ **things hang together / flow by theme.**
- Mo adds: **"maybe having the ability to SORT the feed would help also"** → user-facing sort/filter control is on the table as part of the fix.
- Implication: the category-rails instinct (group by topic) was the RIGHT idea; execution looked bad. Resolution likely = a short cross-topic "best" head + topic-grouped sections (Apple-News IA), and/or a user sort/filter control.
- Flags: none

### Q2 — Cohesion by default (A) vs flat feed + user controls (B)?
- Asked: Should cohesion come from the product (auto topic-grouping) or from user sort/filter controls?
- Captured: **Mo leans A (cohere by default)** but **acknowledges the tension**: grouping by topic can bury the single most-important story (the feed is supposed to surface what-matters-most first, cross-topic). Unresolved → needs a resolution that keeps importance-first AND topic flow.
- Flags: none

### Q3 — Resolve the importance-vs-cohesion tension: hard sections vs soft topic-smoothing?
- Asked: Single soft-smoothed river (topics flow in runs, no boxes) vs hard sections (Top Stories head + labeled topic rails)?
- Captured: **Not sold on either option yet** — left open. BUT a firm conviction surfaced: **the "Top Stories" section must hold MORE than 1.** The single most-important story gets the **hero slot**; then **several more top stories *across all niches*** compete for the slots directly under it within the Top Stories section. (So Mo IS thinking in terms of a real cross-topic "Top Stories" block at the top — a multi-item head, not just a hero.)
- Still open: what the feed looks like BELOW Top Stories (soft-smoothed river vs topic rails vs something else).
- Flags: none

### Q4 — Top Stories composition: pure top-scored vs deduped cross-niche spread?
- Asked: Fill the under-hero slots by pure score, or a deduped spread of the top story from different niches?
- Captured: **Mo leans B — the deduped cross-niche spread.** Hero = #1 overall; the slots below = the biggest story from different corners of the world, de-duplicated (same event never takes two slots). **Count: 5–7 total** in the Top Stories block. Reads as "the most important thing + the biggest thing in each part of my world" = a strong, calm "caught up" hit. (Leans on clustering/dedup.)
- Flags: none

### Q5 — Bounded ("you're caught up") vs endless feed?
- Asked: Should the default feed be finite and end (discovery tail opt-in), or stay a continuous living river?
- Captured: **Tentative: bounded by default, endless on request.** Default = Top Stories → bounded "rest that matters" → a "You're all caught up" beat; the endless discovery river becomes an **opt-in tail** ("Keep reading / More to explore"). Ties to the vision's "closure" ritual + the catch-up mechanic.
- **META-SIGNAL (important):** Mo: *"the only way to figure this out is by trying a few different things."* → He wants to **PROTOTYPE / compare real variants**, not fully decide the look in the abstract. The grill should converge toward a small set of concrete things to build & react to (esp. the still-open "what's below Top Stories" treatment).
- Flags: none

### Q6 — What variants to prototype for the "below Top Stories" region?
- Asked: Build & compare Variant A (soft-smoothed river) vs B (quiet topic labels)? Add a third?
- Captured: **Build & compare THREE variants** (Mo wants to try real renders, not decide on paper). All share: Top Stories block at top (hero + 5–7 deduped cross-niche spread), single calm column, **no boxes/carousels** (boxes are what killed the last rails attempt), ends with a "You're caught up" beat; endless discovery is an opt-in tail.
  - **Variant A — Soft-smoothed river:** one continuous feed; topics flow in little runs via *ordering only*, NO labels.
  - **Variant B — Quiet topic labels:** same river, but a hairline topic label introduces each run (calm "sections" without boxes).
  - **Variant C — Bounded niche previews + "Read more":** uses the CURRENT row layout (not swipeable cards). Below Top Stories, each niche shows its **top news (a few stories)** followed by a **"Read more" button** that lets the user go deeper *within that niche* on demand. (Apple-News "section + More" pattern, vertical, bounded-then-drill-down. Mo explicitly: NOT swipeable cards — laid out like we have it now.)
- Build note: the **`sections` payload we already shipped** (top_stories + category groupings) is enough data for the UI agent to mock all three. "Niche" = `primary_category` proxy until onboarding exists.
- Flags: Top Stories deduped-spread selection logic + true cross-source dedup (clustering is parked) — prototype can use existing content_hash dedup; perfect dedup later. → owner: engine (me) when we build for real.

### Q6b — Does the pipeline pull enough stories per niche for Variant C? (measured)
- Asked by Mo: if we break the feed out by niche (Variant C), is there enough depth per niche?
- **Measured (live blank.db, last 48h, score>=6):** Tag coverage recovered to **66%** (965/1453; was ~0% last night — backfill + scoring-stall fix worked; 488 still untagged).
  - **Deep (preview + read-more works):** Sports 172, Entertainment 132, Business 113, Technology & AI 107.
  - **Solid:** Money/Finance 44, Politics 39, Lifestyle 33, Crime 27, Gaming 22, Arts/Books 21.
  - **Too thin for read-more:** World 17, Science 12, Climate 9, Internet Culture 8, Health 5, Other 5.
- **Answer: YES for the big niches, NO for ~6 thin ones** → Variant C exposes the sourcing gap (Science/Health/Climate/World). It's the MOST depth-dependent variant (A/B just flow whatever exists).
- Softeners: (1) "Read more" can dip below score-6 (rank-don't-hide) for more depth (e.g. Lifestyle 88 total vs 33 at >=6); (2) these are the 15 fixed categories, not user niches — real niches could be thinner, OR ensure-sources-first.
- → Reinforces the parked "ensure every niche gets enough scored items" + niche→source catalog work as a prerequisite to shipping C broadly (prototype C now with well-stocked niches only).

### Q7 — Macro topic-jumble vs micro per-row visual noise?
- Asked: Is the overwhelm partly per-row busyness (thumbnail+headline+source+favicon+gem+time+cluster line), or almost entirely the macro topic-jumble?
- Captured: **Mostly MACRO topic-jumble**, not per-row noise. → Per-row visual density is a secondary factor; the fix is primarily structural (ordering/grouping), confirming the whole direction of this session.
- Implication for the experiment: isolate the variable → do the **A/B/C structure test with rows untouched** first (clean read on what ordering alone does), then a row-calming pass later if still needed.
- Flags: none

### Q7b — Experiment method: structure-first, rows untouched?
- Asked: Build A/B/C changing only ordering/grouping, leaving rows as-is (clean signal), row-calming later?
- Captured: **Confirmed — "that's right for now."** Isolate structure; rows untouched; row-calming is a later polish only if needed.
- Completeness backstop: nothing else rattling around for now (hero treatment, "caught up" visual, refresh cadence left for the build/later).
- Flags: none

### Q8 — Does Variant C require per-niche "siloed" scoring, and would that drive up cost?
- Asked by Mo: to give each niche depth, do we need to score each niche in a silo? Cost impact?
- Captured: **No silo needed; not a cost multiplier.** (1) Scoring stays **global-score-once**; every item *already gets its `primary_category` niche tag inside the single Sonnet score call* (no extra pass/tokens). Per-niche grouping is a free `GROUP BY` on existing data. (2) The thin-niche problem is **SOURCING, not scoring** — we barely ingest Science/Health/Climate/World. Fix = add a few sources per thin niche (the niche→source catalog work). (3) Cost of that = only the incremental triage/score of the extra articles: scales **with article volume** (allowed by the cost rule), NOT with niches/users (the forbidden multiplier); bounded by `PER_SOURCE_CAP=15` + the cheap Haiku triage gate. Est. ~10–20% volume bump to fill 4 thin niches — modest, linear, moat intact.
- Mo's read so far: **likes Variant C** (UI agent is building it).
- Flags: none

### Q9 — Can the niche "Read more" drill-down include sub-6 items?
- Asked by Mo: when going deeper into a niche, can we add items that scored < 6?
- Captured: **Yes — and it's free.** Every triage survivor already gets a full 1–10 Sonnet score; sub-6 items are already scored + stored, just filtered out by `FEED_THRESHOLD=6` / `get_feed` `min_score`. "Read more" simply queries that niche with a lower/no threshold → **zero new LLM cost.** This is the **"rank, don't hide"** discovery surface finally getting a home: graceful descent (niche top = 8s/9s → deeper = 6s/7s → deepest = 4s/5s).
- **Boundary:** surface scored-but-low items, NOT the triage **KILL** pile (junk Haiku discarded pre-score).
- Helps **medium** niches a lot (Lifestyle 33 at >=6 but 88 total scored → ~3x depth); barely helps **truly thin** niches (Science only 12 total) → still need sourcing. Complement, not replacement.
- Flags: none

## Open flags (pending input)
- Top Stories selection logic (one-per-niche vs deduped-best-few) → finalize at build time (me).
- True cross-source clustering for Top Stories dedup → parked engine work.
- Per-niche source depth (Science/Health/Climate/World starved) → gates Variant C broad ship; ties to niche→source catalog.
