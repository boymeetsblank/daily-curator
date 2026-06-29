# Apple News Research — Design / UX / What We're Missing
Date: 2026-06-29 · 5 parallel research agents (feed IA, moment/big-event, visual language, card patterns, engagement/retention)

> Goal: study Apple News to sharpen Blank's sectioned-feed direction and find gaps. Synthesis first, then per-agent detail.

---

## TOP CROSS-CUTTING TAKEAWAYS (the signal)

### 1. Clustering is Blank's single biggest *unearned* advantage — Apple can't do it
Apple News **does NOT cross-source de-duplicate** — it shows the same event from each publisher (like Feedly/Flipboard). Their "More Coverage" is a flat list. **Blank already de-dups + clusters.** → Elevate the cluster from a quiet "Covered by Reuters, BBC +4 more" *label* into a **navigable multi-source mini-list** (real alternate headlines + source wordmarks + timestamps). This is the moat. Theme across agents: **"out-curate Apple, don't out-feature it."**

### 2. Typography is our biggest *visual* gap ("app" vs "publication")
Apple splits type by **role**: **New York (serif)** for the *reading experience* / headlines, **SF Pro (sans)** for *UI/chrome*. Blank splits two grotesks by *scale* — subtler, less editorial. → Consider a **high-contrast display or serif for hero/Moment headlines**, keep Schibsted/Hanken grotesk for metadata/UI. Plus: optical sizing, strict type scale (tight tracking on display, loose on body), 8pt grid, concentric corner radii (child radius = parent − padding).

### 3. The Moment rail (our bespoke piece) is under-spec'd vs Apple's playbook
Apple's dominant-story treatment = **banner ("Follow the 2024 election live") + dedicated hub + Live Activities + a structured status object** (bracket / electoral tally / scoreline). Gaps in our Moment rail:
- **No liveness signal** — add a "Live/Updating" pill + "Updated Xm ago"; surface the event's number (score, tally, count). This is the #1 missing piece that makes a Moment *feel* like a moment.
- **A distinct Moment label** separate from the lead headline (verb/time-driven), keeping our real-headline rule for the story title itself.
- **Branch by type:** *sustained* (World Cup/Olympics/election → structured status object + sub-nav) vs *breaking* (→ reverse-chron clustered "latest" stream). Don't treat them as one shape.
- **Explicit promotion/demotion/absence rules + rarity** — gate on cross-source cluster breadth (we already cluster); render NO moment when nothing dominates. Restraint = credibility (Apple's "accuracy over speed").
- Make the Moment a **destination/hub**, not just a feed snippet.

### 4. Text-only rows must be first-class (they're ~60% of our feed)
Apple composes cards from **typed slots on a shared grid**, so image and text variants are the *same* card degrading gracefully. Our text rows risk reading as "row minus thumbnail." → Give them deliberate typographic hierarchy + a source wordmark anchor; enforce a **fixed image crop ratio** (e.g. 16:9/4:3) so image rows don't jitter against text rows.

### 5. Show source identity as branded wordmarks/favicons everywhere
Apple always renders the publisher as a **one-line wordmark near the headline**. For a "real headlines / AI is the editor" product, **provenance is core trust** — add source wordmarks/favicons on the meta line and inside clusters. (We likely render plain text today.)

### 6. IA: explicit bands, short curated head, infinite tail, reserve the "For You" slot
Apple's order: **editorial Top Stories (same for everyone) → For You (personalized) → Trending (social proof) → topic sections → endless tail.** Lessons:
- Keep the **curated head SHORT** (hero + ~5–7), push everything else to Category rails + the infinite tail (we already do the tail — good).
- **Reserve a "For You" band now** (between Top Stories and Categories) so Phase-2 personalization is a fill-in, not a re-architecture.
- Add a cheap **"Trending / what others are reading" rail** — non-LLM social-proof signal (read/click velocity), a *different axis* from our Sonnet score. Respects the cost rule.
- **Signal freshness** (timestamps, "new since last visit", gentle re-rank) to counter the 10-min batch feel.

### 7. Engagement/retention scaffolding we lack (habit loops)
- **Audio Catch-up = the biggest lever.** Apple News Today is a *human-hosted weekday morning briefing* — a time-of-day ritual. Make Catch-up a timestamped "today's edition"; FREE = text digest, PAID = **audio briefing + Up-Next queue + offline**. On-strategy (organizing real stories, not authoring).
- **Gradient correction loop.** Replace our binary "not for me" with Apple's set: **Suggest Less (soft down-rank) vs Block Source vs Mute Topic/Niche vs "More like this."** Fits our per-user re-rank-on-global-score model.
- **Granular per-niche notifications** as the core PAID hook; give FREE users one curated **"Big Story" alert** (highest-scored cluster/day) as a retention magnet + upsell.
- **Saved + History + "continue reading"**, synced — table-stakes return reason, likely under-built in our shell.
- **A daily-ritual hook** (Apple's data-backed retention play = daily games/streaks). Cheapest version: a **streak counter on Catch-up**.
- **Freemium boundary** mirrors Apple; copy the **upsell mechanic**: end the free digest with a teaser of a paid feature.

### 8. Caution: the glass tab bar (NN/g critique)
NN/g found Liquid Glass translucency **hurts legibility** ("text over text is an illegible mess," minimize-on-scroll "spectacle over usability"). Blank is a *reading* app → enforce a **contrast floor/scrim** on the glass bar, no text-over-text, keep it legible. (We already removed the shrink-on-scroll — good.)

### What Blank already does BETTER (keep / lean in)
- **Single disciplined accent** (ALD forest-green) vs Apple's publisher-brand color sprawl.
- **Transparent ranking via rarity gems** — Apple *hides* its ranking; our quiet gems are a genuine differentiator.
- **Cross-publisher de-dup/clustering** — the actual moat.
- **Cleaner single-feed IA** vs Apple's busier multi-section sprawl.

---

## AGENT 1 — Feed structure & IA
- Tabs: Today / News+ / Sports / Audio / Following (Search lives *in* Following, not its own tab). Our 5 tabs map cleanly (Feed≈Today, Niches≈Following, Catch-up≈Audio, Profile≈Following mgmt).
- Today order: **Top Stories (human-curated, identical for everyone, rolling one-at-a-time refresh) → Apple News Today audio → For You (personalized) → Trending (algorithmic) → topic/Spotlight sections → endless suggested tail.**
- Editorial vs algorithmic is an **explicit layered split**. Source concentration is heavy even with editors (UK: 6 publishers = 77%; US: 10 = 55.7%). Trending skews soft/celebrity.
- Grouping is shallow ("More" at a group's foot); **no cross-source dedup**.
- Recs: visible-cluster Moment; explicit 3-band hierarchy + reserve For-You slot; short head / infinite tail; cheap Trending rail; labeled sections w/ consistent rail length + "More"; freshness signals.
- Sources: Apple Support (Today feed), AppleInsider, Jack Bandy "Editors vs Algorithms (4,000 stories)", CJR source-concentration studies, Readless (dedup behavior).

## AGENT 2 — Moment / big-event / breaking
- Four coordinated mechanisms: **(a) top-of-feed "Follow … live" banner**, **(b) Special Coverage hubs** (lead + structured supporting + sub-nav: candidate streams, region drill-down), **(c) Live Activities** (Lock Screen / Dynamic Island real-time tally — the "alive" signal), **(d) Sports hubs** (bracket/standings/score — minimalist status object). Breaking = "accuracy over speed," ≤5 alerts/day.
- Quiet days: no Moment — ordinary Top Stories. The Moment is a rare, editor-triggered overlay, then retired (demoted to a slim persistent strip before removal).
- Recs: full-bleed lead + distinct Moment label; **liveness affordance (highest-leverage)**; branch sustained vs breaking; explicit promotion/demotion/rarity rules; Moment as a destination/hub; multi-source confirmation gate (use cluster breadth).
- Sources: AppleInsider (election Live Activities), Gizmodo, Apple Newsroom (Apple Sports/World Cup), Slate (World Cup teardown), Apple notification guidelines.

## AGENT 3 — Visual design language
- **New York (serif, variable optical sizing — reading face small, display face large) for reading; SF Pro for UI.** Text↔Display crossover at 20pt. Dynamic Type scale (Headline 17 semibold, Body 17, etc.).
- Near-white/near-black + restrained grays; color via **publisher brand + imagery**, not chrome. 8pt grid, 44pt tap targets, **concentric corner radii**, whitespace-over-borders. iOS 26 = rounder/roomier, sentence-case left-aligned list titles.
- Publisher logo spec: text-only PNG, one horizontal line, exact channel name, ≥256px, transparent.
- NN/g: Liquid Glass translucency harms legibility.
- Recs: **serif/high-contrast display for hero headlines** (biggest "publication" lever); optical sizing + strict scale; 8pt grid + concentric corners; protect glass-bar legibility; keep chrome near-monochrome; consistent source wordmarks.
- Full brief: `~/.claude/plans/task-render-the-new-hashed-diffie-agent-a9c64c78a44449674.md`.

## AGENT 4 — Card & list patterns
- **Apple News Format** = typed slots on a 7-column grid: title/heading/body/intro/quote/pullquote/caption; **byline/author/photographer as first-class attribution**; photo/image/gallery/mosaic/video; container/section/chapter/header/aside/divider; **link_button** ("Read full story/More"). Side-by-side via HorizontalStack/CollectionDisplay (carousels/grids).
- Consumer cards: lead/hero, standard story cards, **grouped story-group cards w/ "More" expander**, "More Coverage" (same story, multiple publishers), audio cards, sports cards, photo galleries/mosaics, **branded publisher wordmark near headline**. Per-card: Save, Share, **Suggest More/Less**, Report, go-to-channel. Thumbnails ≥300×300, aspect 1:2–3:1.
- Recs: **text-only rows as first-class card type**; source wordmarks/favicons everywhere; **cluster → navigable mini-list** (the moat); fixed image crop ratio; lightweight grouping/"more" primitive; standardized meta line (source wordmark · time · read-time) with the gem as the distinctive trailing element.
- Sources: developer.apple.com ANF Component/Components docs, Apple Support image/logo specs.

## AGENT 5 — Engagement / retention / personalization
- **Apple News Today** = free human-hosted weekday audio briefing (CarPlay; ends with a News+ teaser). Audio "Up Next" queue; News+ narrated articles (paid).
- Notifications: per-channel opt-in + Apple "Top Stories"/"Spotlight" streams; Focus filtering; publisher guidelines.
- Personalization (rich correction loop): Follow/Unfollow, Suggest More/Less, Block Channel/Topic, "Stop Suggesting", "Restrict Stories in Today", Siri Suggestions; improves with ratings.
- Saved + History synced cross-device; widgets/Lock Screen/Spotlight/Watch.
- News+ ($12.99/mo): 500+ magazines, narrated audio, **Offline Mode**, **daily games** (Quartiles — explicit retention play per Nieman Lab), News+ Food. Habit loops = morning audio + daily games.
- Recs: **audio Catch-up as a timestamped daily appointment** (free text / paid audio+offline); **gradient correction loop**; **granular per-niche push + a free "Big Story" alert**; **Saved/History/continue-reading**; **a daily streak hook**; freemium boundary + teaser-upsell mechanic.
- Caveat: "out-curate, don't out-feature" — these are habit scaffolding around the real differentiator (cross-publisher ranking + clustering).
- Sources: Apple Newsroom (audio 2020, Quartiles/Offline 2024), Apple Support (News Today, Up Next, Suggest/Block, Save), Nieman Lab (games-as-retention).

---

## Suggested next moves (not yet decided)
- **Cheapest high-impact UI wins:** serif/high-contrast hero headlines · source wordmarks/favicons · cluster line → tappable multi-source mini-list · fixed image crop ratio · text-row first-class treatment.
- **Moment rail v2:** liveness pill + "updated Xm ago" + distinct label + promotion/rarity rules (needs engine support for the "live number" / type detection).
- **Retention:** gradient correction loop · timestamped Catch-up + streak · "Big Story" free alert.
- Revisit whether the **sectioned feed** is the right call at all (it's currently shelved) — these findings can inform that decision.
