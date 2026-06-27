# Blank Platform: Brainstorm / Discovery Notes
Date: 2026-06-27 · Goal: Align on what the Blank platform fundamentally is and what it does

## ★ FINAL CONSOLIDATED DECISIONS (read this first)
- **What it is:** a consumer reading app where the AI is your editor — "Apple News meets an AI editor that scores, de-dupes, and ranks the news for you." (Replaces the old carousel-scout identity entirely.)
- **The job:** help a curious, time-poor person stay on top of THEIR niches without sifting noise.
- **AI editor's role:** SELECTION + ORGANIZATION, not authorship. Rank everything, **hide nothing**; user corrects mis-ranks ("this wasn't noise") = a discovery + feedback loop.
- **Feed content:** real headlines only (NO hooks); on-demand "catch me up" summaries on tap; multi-source clustering.
- **Rhythm:** living/real-time feed; selective push only for big breaks; "since you last opened" catch-up = the daily "you're caught up" CLOSURE moment (the ritual).
- **Onboarding:** "topics to get started, sources to go deep." Pick niches -> instant full feed.
- **Sources:** automated per-niche source discovery WITH founder visibility/oversight; trends (Apify X/Google) ARE in for day 1, routed through the same niche-relevance ranking.
- **Personalization:** global score (once/article) + cheap periodic per-user taste profile + near-free real-time re-rank = "the AI learns ME" WITHOUT per-user LLM cost. Never score per-user.
- **Cost:** volume-driven not user-driven; old engine was $60-80/mo (too high). 3 fixes: fix 89% escalation rate, add prompt caching, kill per-article hook/why output.
- **Form factor:** PWA now, native later. **Pricing:** freemium; free = up to ~3 niches + ranked living feed + daily catch-up; paid $10-15/mo = unlimited niches/sources + instant push + taste-learning + on-demand summaries.
- **Moats (load-bearing):** (1) aggregate collective-intelligence network effect [acquisition + compounding], (2) habit/daily-ritual [retention]; per-user taste graph = retention layer underneath. Business-model wedge + niche depth support. NO existing social audience (audience moat is out).
- **Distribution:** organic curated-story posting + CTA (product output = marketing content, self-feeding loop) + paid media (separate chat). Stay BROAD, test which niches respond, then concentrate.
- **North star (6-12 mo):** MRR as the headline goal; retention as the leading diagnostic for MRR durability.
- **Name:** NOT finalized — finalists **Keen** vs **Caret** (fill-in-the-blank/sharp), with **Blank** as fallback. Founder reflecting.
- **Build sequence:** Phase 1 engine-cleanup/cost-fixes (real headlines, rank-don't-hide, escalation+caching, trends) -> Phase 2 core daily loop (niches, accounts, per-user re-rank + correction + catch-up) -> Phase 3 monetize+grow (paywall/payments, push, summaries, content engine).

## Summary / key decisions
- CLAUDE.md / current codebase description ("culture intelligence platform that scouts articles 3x/day for carousel content") is the OLD version of the brand. There is a NEWER engine the user recently developed that supersedes this. The brainstorm goal is to capture THAT new vision.
- KILL FEATURE: The **hook rewrite** (AI rewriting headlines into punchy hooks) is OUT. That was a Claude suggestion the user tried and dislikes in practice. Headlines should stay authentic; do NOT editorialize/rewrite the title. (The "Atomic Unit = Hook + Why" framing from the design canvas is therefore obsolete.)
- CORE USER INSIGHT (the founder's own itch): User loves staying informed about the **specific niches he's interested in**, but (1) has limited time because of a 9-5 job, and (2) it's hard to sift through noise to find what he should actually know that day. Blank exists to let someone **quickly navigate and educate themselves on what matters in their chosen niches, every day.** This is interest/passion-driven, not work-obligation-driven.
- BEACHHEAD USER: essentially the founder himself — a curious person with specific niche interests, limited time, who wants signal without noise. "For everyone" is the long-term TAM; the v1 archetype is "the curious-but-time-poor niche enthusiast."
- NEW DIRECTION (inferred from "Blank News Reader.dc (1).html" design canvas, to be confirmed): Blank is a **consumer-facing mobile news-reader app** ("blank."), not a carousel backend. Evidence from the design canvas:
  - Three feed concepts explored: "The Wire" (light, editorial list), "The Signal" (light, score-first), "The Signal" (dark, score-first).
  - Feed has tabs: All / Following / Discovery (a.k.a. Explore).
  - Each article shows: source badge, category, time-ago, a rewritten punchy HOOK headline, and a "→" one-line summary. "Hook = punchy rewrite, Why = editor's note" called "The Atomic Unit."
  - Per-article AI relevance SCORE (1-9) — V1/V2 hide it, V3 exposes it ("power-user honesty vs editorial magic" — a design call, not product).
  - Multi-source CLUSTER strips (e.g. BBG/Reuters/WSJ +3 sources) collapse same-story coverage.
  - "Surprise" / Discovery items flagged with amber accent (serendipity beyond your follows).
  - Article detail view has a "Why this story" highlighted box (italic editorial note).
  - ONBOARDING is "the bet": paste any URL -> auto-discover feed; users never touch RSS. Three approaches shown: paste, catalog, terminal.
  - Aesthetic: warm off-white / near-black, Newsreader serif + DM Sans + DM Mono, amber (#C47B2D) accent.

## NOTE ON CODEBASE
- The OLD batch engine = daily_curator.py, daily_curator.yml (3x/day), picks/*.md, GH Pages. Superseded.
- The NEW engine (verified by reading the code) = a continuous cascade pipeline:
  - **blank.yml** — GitHub Actions cron **every 10 minutes** (~144 runs/day), single-concurrency, commits blank.db (SQLite) back to repo each run.
  - **run_pipeline.py** orchestrates: Ingest -> Triage -> Score -> Publish.
  - **ingest.py** — polls active RSS sources (sources.json), dedups new items into blank.db.
  - **triage.py** — **Haiku 4.5**, batches of 20, max_tokens 1024. A RECALL GATE: KILL (safe to discard) vs ESCALATE. Deliberately tuned to over-escalate (cheap to escalate, killing a survivor is the only real failure). Target escalation 40-60%.
  - **score.py** — **Sonnet 4.6**, batches of 12, max_tokens 2048. Scores 1-10 ONLY on escalated items. FEED_THRESHOLD=6.
  - **publish.py** — writes static index.html.
- COST ARCHITECTURE (already smart): two-stage cascade. Cheap Haiku filters everything; expensive Sonnet only touches survivors. Cost currently scales with ARTICLE VOLUME, not users — because it's a SINGLE GLOBAL shared feed scored once. There is NO per-user scoring yet.
- THE CENTRAL COST TENSION: the vision we aligned on (personalized per-niche ranking + per-user correction loop) implies PER-USER scoring, which would make AI cost scale with users × articles instead of just articles. Reconciling "personalized feed" with "score each article once globally" is the key cost-architecture decision.
- TWO DISCREPANCIES between current engine code and the vision aligned in this brainstorm (to revisit):
  1. score.py STILL generates a "hook" (punchy rewrite) per item — user has KILLED the hook feature (see Q4 note). Engine not yet updated.
  2. FEED_THRESHOLD=6 FILTERS/hides items below 6 from the feed — but the vision is RANK, NEVER HIDE (see Q4). Engine currently hides low-scoring items instead of keeping them browsable in a discovery surface.

## Q&A log
### Q2 — Is the shift: consumer reading app, AI as editor? (CONFIRMED)
- Asked: Is Blank now a product people use to READ (AI is their editor), not a creator's content scout?
- Captured: CONFIRMED. Blank is a consumer reading app. Positioning the user endorsed verbatim: "Apple News meets an AI editor that scores, rewrites, and de-duplicates the news for you. The AI is the editor." The carousel/creator use case is no longer the product.
- Flags: none

### Q4 — What is the AI editor's job (post-rewrite)?
- Asked: Is the AI's job selection + organization (filter, rank, de-dupe, orient) rather than authorship? And do you want any AI-generated text per item?
- Captured: Confirmed the AI editor = SELECTION + ORGANIZATION, never authorship/rewriting. BUT one critical correction: the AI must NOT remove/hide "noise." Instead it **ranks everything**, bringing the most important to the top. Lower-ranked items stay fully accessible/browsable. The user wants to scroll through what the AI deemed "noise" and **tell the AI when it was wrong** ("this wasn't noise") — a correction/feedback loop that works like a DISCOVERY feature and personalizes future ranking. So:
  1. Rank everything (important to top) — never delete.
  2. Keep low-ranked items reachable (a discovery/explore surface).
  3. User feedback on mis-ranked items trains/personalizes the AI over time.
  4. De-dupe via clusters (kept).
- KEY DECISION: Blank is a RANKING engine, not a FILTERING engine. Nothing is hidden; everything is ordered. Human-in-the-loop correction is a core feature.
- Flags: Still open — do you want ANY AI-generated text per item (neutral 1-line "why it matters"/summary) or pure curation (real headline only)? -> user (Q4b)

### Q4b — Any AI-generated text per item? (DECIDED)
- Asked: Pure curation, one neutral line, or on-demand summary?
- Captured: DECIDED — **pure curation in the feed (real headline + source + thumbnail; AI output = ranking + clustering only) PLUS on-demand summary on tap** (tap an article -> AI "catch me up" in ~3 bullets / 20 seconds). No generated text in the feed itself. The time-saving summary lives one tap deep, where the user asked for it. Avoids any hook-rewrite smell.
- Flags: none

### Q5 — How are niches defined / where does content come from?
- Asked: Source-first (you add sources, AI ranks within) vs topic-first (you name interests, AI finds sources)?
- Captured: **Source-first foundation + topic-first as the magic on top.** Users CAN hand-select their sources if they want to (source selection is an available power, likely optional rather than mandatory). On top of chosen sources, declaring a topic/niche lets Blank pull in relevant material — including from sources the user doesn't follow — which also feeds the discovery surface.
- Flags: Cold-start / default path for a user who does NOT want to hand-pick sources -> user (Q5b)

### Q5b — Cold-start / new user's first 60 seconds (DECIDED)
- Asked: Default to picking niches (fast, populated feed) with source-picking as opt-in power feature?
- Captured: ALIGNED. Mantra: **"Topics to get started, sources to go deep."** New user taps a few interest chips -> Blank instantly seeds a full, useful feed from a curated source set per niche (no empty state, no setup friction). Hand-picking/adding sources is an opt-in power-user path for tuning/depth. 
- Flags: none

### Q7 — Cost pain, located + unit economics
- Asked: Already wincing now, scared of scale, or a different line item? Rough number?
- Captured: OLD engine cost **$60-80/month** — "way too expensive." The fear is whether the NEW engine will cost the same. Target pricing: **$10-15/user/month**. Requirement: per-user cost must stay LOW for healthy margins at that price.
- KEY ECONOMIC INSIGHT (from architecture): the new engine scores ONE global shared feed ONCE -> AI cost scales with article volume, NOT user count. At $10-15/user with global scoring, each new user is ~pure margin. The threat to this is per-user LLM scoring (personalization) which would reverse it. So the central cost-architecture principle to protect: **keep the expensive LLM work GLOBAL/shared; do personalization cheaply (lightweight per-user re-ranking on top of global scores, ideally without extra LLM calls).**
- Flags: Need an actual measured/estimated monthly cost figure for the NEW engine -> computed below.

### Q7a — Measured volume + cost model of the new engine
- blank.db reality (test scale): 129 items over ~2 days (~65/day); 49 of 55 triaged were ESCALATED = **89% escalation rate** (target is 40-60%). At this tiny volume the bill is a few $/month. The 89% rate means the Haiku gate is barely filtering — almost everything reaches expensive Sonnet. FIRST cost lever.
- Pricing (per 1M tokens): Haiku 4.5 = $1 in / $5 out. Sonnet 4.6 = $3 in / $15 out. Cache read ≈ 0.1×. Batch API = 50% off but async (NOT usable for a real-time feed).
- Cost model at a hypothetical PRODUCTION scale (~150 sources, ~3,000 new articles/day):
  - Haiku triage on all 3,000/day ≈ ~$0.8/day.
  - Sonnet scoring at HEALTHY 50% escalation (~1,500/day) ≈ ~$4.6/day -> **~$165/mo**. At today's 89% escalation it's ~$8/day -> ~$250/mo.
  - Output tokens dominate Sonnet cost ($15/1M out): the per-item "why" + "hook" generation is the single most expensive line.
- COST IS VOLUME-DRIVEN, NOT USER-DRIVEN (global scoring). So the monthly bill tracks article volume, and the lever is reducing per-article AI work, not limiting users.
- THE LEVERS (and how they tie to decisions already made in this brainstorm):
  1. **Fix the 89% escalation rate** -> right-size the Haiku gate so Sonnet only sees real candidates. Could roughly halve Sonnet volume.
  2. **Add prompt caching** (NOT currently used) -> the large static system prompts in triage.py/score.py are re-sent on every batch at full price. Caching makes the repeat ≈0.1×. Direct, easy win.
  3. **Kill the hook + drop per-item "why" from the feed** (already decided: pure curation + on-demand summary) -> slashes Sonnet OUTPUT tokens, the most expensive part. Product decision = cost win.
  4. **On-demand summary instead of summarizing everything** (already decided) -> summary tokens are only spent on items the user actually taps, not all ~3,000/day.
  5. Tune source count / per-source caps / dedup aggressiveness -> fewer junk articles entering the funnel at all.
- TAKEAWAY: With these levers, the per-article cost drops enough that a flat ~$40-80/mo AI bill supports many paying users at $10-15/mo => healthy margin. The danger to avoid is per-user LLM scoring (keep scoring global).

### Q6 — Consumption rhythm: digest vs living feed (DECIDED)
- Asked: Daily Brief (finite, finish line) vs Living Feed (always-fresh, real-time)?
- Captured: DECIDED — **Living feed from day 1.** Real-time. Rationale: big news drops mid-day and the user wants to know ASAP. Implies breaking-news alerting/push notifications for high-importance items. (Connects to existing repo concept: breaking_news_check.py / breaking_news.yml = "live feed.")
- TENSION TO RESOLVE: living feed vs the core "limited time / escape the noise" pain. Need a mechanism so the time-poor user isn't dumped into infinite scroll — likely a "what you missed since last open / catch me up" rail + smart alerting so only TRULY important breaks interrupt. See Q6b.
- Flags: Alerting model + catch-up mechanic -> user (Q6b)

### Q6b — Reconcile living feed with limited time (DECIDED)
- Asked: Selective push + "since you last opened" catch-up so the living feed doesn't become noise?
- Captured: ALIGNED. Final model: (1) FEED = always live — articles arrive & get ranked continuously throughout the day, in real time. (2) PUSH NOTIFICATIONS = rare exception, only for the 1-2 genuinely big stories per day for your niches; everything else appears silently in the feed. (3) "SINCE YOU LAST OPENED" = convenience lens that summarizes what you missed during busy stretches (not a delay on arrival). Feed never sleeps; phone stays quiet unless truly worth it.
- Flags: none

### Q3 — Who is it for?
- Asked: Is the target the information-hungry knowledge worker, or still culture-first? For everyone or a specific person?
- Captured: User says "this is for everyone." Confirmed it is NOT culture-only anymore. BUT Q3b clarified the real beachhead: the founder's own itch — a curious, time-poor person who wants to stay on top of their chosen niches without sifting noise. The job is interest-driven, not job/work-driven. "Everyone" = destination; "curious-but-time-poor niche enthusiast" = the v1 user.
- Flags: none

### Q1 — What is Blank fundamentally?
- Asked: Is Blank a creator's private tool, a media brand, a consumer culture-intelligence feed, or a B2B signal product?
- Captured: Premise was based on the OLD brand. User says they "recently came up with an entirely new engine." Need to capture the new engine before defining what Blank fundamentally is. The repo CLAUDE.md is stale on this.
- Flags: What is the new engine? -> user (next question)

### Q8 — Personalization vs global scoring (THE crux)
- Asked: Shared global quality score + personal re-rank lens, OR the AI learning your taste directly?
- Captured: User's true desire = **the AI learns MY taste directly** (the richer, more personal experience). BUT explicit constraint = must NOT drive costs back up to the old $60-80 level. So the design must DELIVER the felt experience of "it learns me" WITHOUT per-article-per-user LLM scoring.
- RECONCILIATION (proposed): "The AI learns your taste" is the FELT experience; the MECHANISM is a cheap per-user TASTE PROFILE, not per-article LLM calls per user. Three layers:
  1. GLOBAL (expensive, once/article): Sonnet scores + tags each article. Shared by everyone.
  2. PER-USER TASTE PROFILE (cheap, periodic): a compact profile of what THIS user likes — built/updated by an occasional batch job (e.g. one small LLM call per user per day/week that reads their recent engagement + corrections and writes a short taste summary/weights). This is where "the AI learns me" actually lives. Cost scales with users but only ~1 cheap call per user per day, NOT per article.
  3. PER-FEED RE-RANK (near-free, real-time): order the globally-scored articles through the user's taste profile. Pure math, no LLM, runs all day.
- KEY: the learning is real and personal, but it's amortized into a periodic per-user profile rather than re-scoring the whole feed through the LLM for every user. That's how you get "learns my taste" AND keep the bill flat-ish.
- DANGER TO AVOID (named): scoring/ranking every article through an LLM separately for each user = users × articles cost = the explosion. Never do that.
- Q8b CONFIRMED: User: "That absolutely lands!" The 3-layer model is accepted as the personalization architecture — felt as "the AI learns my taste directly," delivered via global score + cheap periodic per-user taste profile + near-free real-time re-rank.
- IMMEDIACY NOTE (both can coexist, low cost): instant correction ("not noise") = an immediate cheap weight nudge to the user's profile (feels instant, no LLM); the periodic per-user profile job = deeper learning. So the feed reacts the moment you correct it AND gets smarter over time.
- Flags: none

### Q9 — Form factor: PWA vs native (DECIDED)
- Asked: Is Blank a native app or a web app?
- Captured: DECIDED — **PWA now, native later.** Validate with the existing PWA (index.html, sw.js, manifest.json, web-push via send_push.py/VAPID) — instant ship, no App Store tax, one codebase, living feed + selective push all work today. Go native once retention proves out and rock-solid notifications + App Store discovery are worth the build + platform cut on the $10-15 subscription.
- Flags: none

### Q10 — Monetization shape (DECIDED) + free/paid line (Q10b open)
- Asked: Paid-only, freemium, or fully free?
- Captured: DECIDED — **Freemium with a generous free tier.** Rationale: global scoring makes extra users nearly free (free users add only cheap re-rank, no scoring cost), so a big free top-of-funnel is cheap growth; convert engaged users to $10-15/mo. Price tier already set at $10-15/mo.
- Q10b CONFIRMED ("This feels exactly right"). The free/paid line:
  - FREE forever: pick up to ~3 niches with the ranked living feed; real headlines + sources + clustering (the core noise-cut); the daily "what you missed" catch-up.
  - PAID ($10-15/mo): unlimited niches / add-your-own sources; INSTANT push for breaking news; the taste-learning + correction loop ("it learns ME"); on-demand "catch me up" summaries.
  - Logic: free proves Blank cuts your noise; you upgrade when you want it FAST (push), DEEP (unlimited/sources), and YOURS (taste-learning) — the three things the founder personally wanted.
- Flags: none

### Q11 — Fate of the old carousel/picks world (DECIDED)
- Asked: Does the consumer reader replace the old carousel scout, or coexist?
- Captured: DECIDED — **Clean replacement / full pivot** of the PRODUCT identity. The consumer reader IS Blank now. Retire the old carousel/picks framing, the 3x/day batch, the "culture intelligence platform" language; CLAUDE.md must be rewritten (it describes the OLD product).
- REFINEMENT (user follow-up): KEEP AI-generated HOOKS for SOCIAL POSTS — but repurposed as a **MARKETING FUNNEL**, not part of the consumer product. The social hooks become a channel that drives signups to the app.
- HOW THIS RECONCILES (no conflict with prior decisions):
  - The CONSUMER FEED still shows real headlines only, NO hooks (Q4 / Q4b stand). Hooks do NOT belong in the reading experience.
  - Hook generation moves OUT of score.py's per-article path and INTO a SEPARATE, low-volume MARKETING tool the founder uses occasionally to turn top picks into social posts. It is founder-facing, not per-user.
  - COST: negligible and unchanged for the consumer product — hooks are generated for a handful of marketing picks, NOT for all ~3,000 articles/day. So the cost finding "stop generating hook+why for every article in score.py" STILL HOLDS for the feed; hook-writing just survives as an occasional marketing action.
  - So: consumer product = clean replacement; a thin marketing funnel (AI social hooks from top picks) survives alongside it as a growth channel.
- Flags: none

### Q12 — Brand / name (OPEN — name not locked)
- Asked: Is the name locked as "Blank," lowercase wordmark, and does "the news, edited for you" capture the one-liner?
- Captured: User is NOT sold on the name "Blank" yet. Naming is OPEN for exploration. (Design canvas used both "blank." lowercase serif and "BLANK" uppercase mono.) Need to understand the hesitation + what the name should evoke before proposing directions.
- Q12b ANSWERS:
  1. HESITATION: "Blank" feels too generic and doesn't excite the founder as much anymore. Origin: handle is "Boymeetsblank" — the "blank" is a FILL-IN-THE-BLANK wildcard ("Boy meets ___") that lets him post about ANY niche without being boxed into one; the blank changes every post.
  2. DESIRED FEELING (one word): **SHARP.**
- KEY INSIGHT: the fill-in-the-blank concept is actually a STRONG conceptual fit for THIS product — the consumer reader is literally "fill in YOUR niches and we curate them." Rare case where the name's origin maps onto the product mechanic (you pick your blanks = your niches). So the CONCEPT is an asset; the problem is the EXECUTION feels generic and doesn't FEEL sharp.
- STRATEGIC FORK for naming: (A) preserve the fill-in-the-blank / any-niche concept but sharpen its expression (riff on Blank, or a sharper name carrying the same "your niches" idea), vs (B) abandon it for a fresh, sharp name.
- Q12c DECISION: Explore **Path B** (sharper word, keep the fill-in-the-blank / your-niches concept) with **Path A** (keep "Blank," sharpen around it) as the fallback if no B candidate lands. Founder independently confirmed the fill-in-the-blank idea was his exact thought process.
- Naming criteria locked: must FEEL SHARP; should carry the "fill in YOUR niches / your chosen thing / signal-over-noise" soul; short; ownable.
- Q12d OUTCOME: Two FINALISTS the founder loved and will sit with to see which hits harder:
  - **Keen** — means both "sharp" (keen edge) and "eager/interested" (keen on something); sharp mind + your interests in one word. (Claude's #1.)
  - **Caret** — the `^` fill-in-the-blank insertion cursor (the spot you add your thing) + homophone of "carat" (sharpness/quality of a gem); keeps the fill-in-the-blank DNA. (Claude's #2.)
  - Fallback: Path A (keep "Blank," sharpen the brand around it) if neither finalist wins on reflection.
- STATUS: name NOT finalized — narrowed to Keen vs Caret (vs Blank fallback). Founder to reflect.
- Flags: Final name pick -> user (later, after reflection). One-liner/tagline still open, depends on final name.

### Q13 — The Moat (most important strategic question)
- Asked: What stops Apple News / Google News / Particle / a newsletter / a funded competitor from doing exactly this?
- Captured:
  - Founder's instinct: the moat = the personalization / taste-learning. Then sharply challenged it himself: "why is that something others can't copy?"
  - CLAUDE'S ANSWER — the critical distinction: the personalization *mechanism/feature* is 100% COPYABLE (anyone can build "AI learns your taste" in a sprint). What is NOT copyable is the **accumulated per-user taste DATA** + the **time each user invested** building it. A competitor can clone the feature but starts every user at ZERO.
  - THEREFORE: personalization is a **RETENTION moat (switching cost)**, NOT an acquisition moat. It keeps users you already have (leaving = re-training a rival from scratch); it does NOT stop a rival from acquiring a fresh user. And it's WEAK at cold-start (a week-1 user has no taste graph yet — nothing to defend).
  - IMPLICATION: personalization alone is insufficient as THE moat. It must be paired with an ACQUISITION defense. Two candidates:
    1. **Business-model wedge** — incumbents (Apple News, Google, X) monetize ATTENTION, so their model REQUIRES infinite scroll / engagement bait / never-"done." Blank monetizes SUBSCRIPTION, so it can honestly cut noise, give a finish line, let you leave. An ad-funded incumbent is structurally disincentivized to build a calm anti-noise reader — it cannibalizes their engagement metrics. This is "why won't Google just do this."
    2. **Niche depth** — go deep on long-tail enthusiast niches mass-market incumbents won't bother with (too small for Apple, perfect for Blank).
  - SHARP FRAME: wedge (gets users incumbents won't serve) + taste graph (keeps them) + niche depth (where incumbents won't go). Personalization is the RETENTION layer of a multi-part moat, not the whole moat.
- Q13b — FULL MOAT MENU (Claude-generated, honestly graded):
  - STRONG / compounding or structural:
    1. **Aggregate collective-intelligence data** — beyond per-user taste, the SUM of all users' corrections/engagement = a proprietary "what's signal vs noise across niches" dataset. NETWORK EFFECT: more users -> better GLOBAL ranking -> better for everyone INCLUDING new day-1 users -> defends ACQUISITION (unlike per-user taste graph which is retention-only). The upgrade to personalization that actually defends getting users.
    2. **Existing audience / distribution (UNIQUE TO THIS FOUNDER)** — @boymeetsblank social presence = built-in, cheap-CAC channel (the marketing-funnel hooks point here). A competitor doesn't have his audience. Real acquisition advantage available to him specifically.
    3. **Business-model wedge** (from Q13) — subscription-funded honesty incumbents structurally can't match.
  - MEDIUM / real but needs work:
    4. **Brand/trust as a curator** — Blank becomes the trusted NAME for "what matters in X"; trust accrues slowly, hard to copy. Acquisition + retention.
    5. **Habit / daily ritual** — becoming the user's morning default; habit is sticky retention.
    6. **Curated source catalog + taxonomy** — opinionated best-sources-per-niche map; editorial judgment in it is hard to replicate.
    7. **Niche depth** (from Q13) — long-tail niches incumbents won't chase.
    8. **Community / social** — shared niches, follow sharp people's feeds; network effects + switching cost. Bigger product bet.
  - WEAK / illusory (copyable, don't lean on these):
    9. Per-user taste graph alone (retention-only, cold-start weak — see Q13b above).
    10. Cheap global-scoring architecture (a margin advantage, NOT a moat — copyable).
    11. Any single AI feature (scoring, clustering, summaries) — copyable in a sprint.
  - CLAUDE'S TOP PICKS TO BUILD STRATEGY AROUND: #1 (collective-intelligence network effect — defends acquisition AND compounds), #2 (existing audience — unique, immediate), #3 (business-model wedge — structural/durable). Personalization (#9) stays as the retention layer underneath.
- Q13c DECISION — load-bearing moats chosen by founder:
  1. **Aggregate collective intelligence** (acquisition + compounding network effect).
  2. **Habit / Daily Ritual** (retention).
  Per-user taste graph remains the retention layer underneath.
- CORRECTION (changes earlier assumptions): founder does NOT have much of a social audience. So:
  - Moat #2 "existing audience / distribution" is OUT — not available.
  - The marketing-funnel social hooks (Q11 refinement) are about BUILDING an audience from scratch, NOT leveraging an existing one — weaker/slower than assumed.
  - NEW GAP: with no audience and no audience-moat, **distribution / how the first users arrive is now an OPEN PROBLEM** worth its own thread.
- COLD-START TENSION: the collective-intelligence network effect needs users to work, but you need a good product to get users, but the product isn't sharp until it has collective data = chicken-and-egg. Bootstrapping the flywheel from zero must be designed.
- Flags: (a) How to bootstrap collective intelligence from zero users? (b) What makes Blank a daily ritual? (c) Distribution/first-users with no audience -> user (Q13d, Q14, Q15)

### Q13d — Collective-intelligence cold-start (RESOLVED, reassuring)
- The collective-intelligence network effect does NOT face a fatal cold-start: the global AI scoring makes Blank useful on DAY ONE with zero users (good-enough signal/noise ranking from the AI alone). Collective intelligence SHARPENS over time; it isn't a prerequisite. Sequencing: ship useful AI-only reader -> users come for that -> their behavior compounds into the moat. The moat is EARNED as you grow, not bootstrapped from nothing. Escapes the classic network-effect chicken-and-egg.

### Q14 — Habit / Daily Ritual moat (CONFIRMED)
- Asked: Is the ritual the morning "am I caught up?" check with a feeling of CLOSURE?
- Captured: CONFIRMED. Blank should be engineered around a daily **"caught up" moment** — open with coffee, see the handful of things that mattered in your niches since yesterday, feel informed + DONE in ~3 min, close it. Reward = CLOSURE (rare "I can stop now" feeling). Delivered by the "since you last opened" catch-up mechanic. Ritual needs trigger + reward + low friction; the "want to be caught up" pain is the trigger, closure is the reward.
- RECONCILES WITH Q6 (living feed) — NOT a contradiction: the FEED is living/continuous underneath (real-time arrival + push for big breaks, for all-day dipping). The "since you last opened" catch-up provides the bounded "you're caught up" CLOSURE beat WITHIN the living feed. So: living feed = the substrate; the daily "caught up" moment = the ritual layered on top via the catch-up lens. Both true. (This is exactly the Q6b resolution.)
- Flags: none

### Q15 — Distribution / first users (no audience)
- Asked: With no audience, how do the first 1,000 users arrive? Which single niche/community to win first?
- Captured: Founder pivoted to distribution TACTICS (didn't pick a single beachhead niche yet):
  1. **Organic curated-story posting + CTA** — post the interesting stories Blank curates across ALL social accounts, each with a CTA to check out the app. NOTE: this is the marketing-funnel hooks (Q11) operationalized as an ongoing content engine.
  2. **Paid media** — create marketing assets to run as paid ads (FOUNDER WILL HANDLE IN A SEPARATE CHAT).
- CLAUDE'S HONEST GRADING:
  - Idea #1 is genuinely strong for a CONTENT product: the product's OUTPUT (curated interesting stories) IS the marketing content -> a SELF-FEEDING loop where the product generates its own marketing, cheaply and on-brand. It's also live proof-of-value. Caveat: with no audience yet, initial reach is low and it compounds slowly; works far better aimed at a niche where content resonates + gets shared than at "everyone."
  - Idea #2 (paid) buys distribution immediately and bypasses the no-audience problem, BUT: costs money (tension with the founder's cost-sensitivity), needs CAC < LTV math (LTV at $10-15/mo — a churny consumer sub can have low LTV, so CAC tolerance may be small), and needs sharp targeting.
  - UPSTREAM POINT: both channels still beg the TARGETING/niche question. Paid especially targets by interest/niche; organic content resonates per-niche. So the beachhead-niche decision is UPSTREAM of both tactics and still unresolved. "For everyone" makes both channels inefficient.
- Flags: (a) Anchor on a beachhead niche (sharpens both channels) vs go broad? -> user. (b) Paid CAC vs LTV economics -> separate chat. (c) Which social platforms + cadence for organic -> later.

### Q15b — Beachhead niche vs broad (DECIDED)
- Asked: Anchor on one beachhead niche, or stay broad and test?
- Captured: DECIDED — **deliberately stay BROAD and test which niches respond** (let the market reveal the beachhead rather than pre-committing). Legitimate "portfolio test / let data pick the winner" approach; pairs well with the multi-niche product and with paid media (cheap A/B across niche audiences).
- GUARDRAIL (Claude) to avoid the "everyone = no one" trap: "broad" must mean **testing several DISCRETE niches in parallel and measuring response** (niche-specific content sets / ad audiences, tracked by install + share + retention), NOT posting generic "interesting stories for everyone." Then **double down on the niches that respond** — concentration matters because the collective-intelligence moat needs signal density per niche. So: broad to DISCOVER the beachhead, concentrate to BUILD it.
- Flags: none

### Q16 — Source catalog + Trends
- Asked: Where do per-niche sources come from, and do X/Google trends carry into the new engine?
- Captured:
  - TRENDS: DECIDED — **trends ARE in for day 1** (founder overrode Claude's "leave out" rec). Rationale: trends are the DIRECT signal on what people are talking about at any given moment — a real-time pulse of attention that complements RSS curation and fits the living-feed ethos (Q6).
  - RECONCILIATION (the one thing it needs): trends must be **routed through the SAME niche-relevance ranking**, NOT dumped in as a raw global firehose. A trend gets tagged + scored for relevance to the user's niches: matches your niche -> ranks high; globally-hot-but-irrelevant-to-you -> ranks low (not hidden, per rank-don't-hide). So trends are another INPUT to the existing triage->score->rank pipeline, not a separate uncurated stream. Preserves "what people are talking about now" without violating "curate MY niches / cut noise."
  - ENGINEERING: new engine currently ingests RSS only (ingest.py). Re-introduce the Apify X/Google trend fetch, feed trend items into the same pipeline tagged as trend-items so re-rank can match them to niches. (The OLD engine already had this pattern — reference daily_curator.py's trend handling.)
  - COST NOTE: Apify trends = a FIXED monthly data cost (not per-user), acceptable; it's a flat line item, not a user-scaling cost.
- STILL OPEN: the per-niche SOURCE CATALOG (niche -> curated sources mapping for instant onboarding). Claude's read: founder seeds it (his editorial taste = the "best sources per niche" map, one of the medium moats), refined over time by collective-intelligence signal. sources.json today is a flat list; needs to become niche-keyed. Who curates it (founder vs automated/crowdsourced) -> still needs founder confirm.
- Q16b DECIDED: niche->source catalog is **AUTOMATED, with founder VISIBILITY/oversight.** The system auto-discovers candidate sources per niche; the founder gets a review surface to SEE what's selected per niche (and approve/remove/add). Automated scale + human quality gate.
  - WHY THIS IS RIGHT (Claude): fully-automated source selection risks pulling in junk/spam sources that pollute feeds AND waste triage/score cycles (cost). The founder-visibility layer is the quality guardrail. v1 pattern: automated discovery PROPOSES -> founder reviews (esp. early) -> engagement + collective-intelligence signal prunes over time (engaged sources rise, dead ones fall) -> manual oversight can relax as it proves out.
  - BUILD IMPLICATION: (1) automated per-niche source discovery (LLM-proposed and/or paste-URL-style feed auto-discovery applied to a topic), (2) sources.json becomes niche-keyed, (3) a founder-facing "sources selected per niche" review/oversight surface.
- Flags: none

### Q17 — Success metric / north star (DECIDED)
- Asked: What does "winning" look like in 6-12 months? (retention / paid conversion / users / MRR)
- Captured: Founder initially agreed retention-as-north-star, then reversed to **MRR first, retention second.** After Claude flagged the leaky-bucket risk (MRR is a lagging indicator; chasing it before the ritual is proven = paying to acquire into a leaky bucket), settled on the RECONCILIATION:
  - **MRR = the headline scoreboard / goal** (proves the business is real and people will actually PAY — the hardest, most honest early test).
  - **Retention = the leading health indicator UNDERNEATH it** (the diagnostic that tells you whether the MRR is durable; weak retention under climbing MRR = hollow growth, caught early).
  - So not either/or: MRR is the goal, retention is the early-warning system on MRR durability.
- Flags: none

### Q18 — Build sequencing for v1 (CONFIRMED)
- Asked: What to build first, ordered to serve MRR (with retention as the signal)?
- Captured: CONFIRMED the 3-phase sequence:
  - **Phase 1 — Make the engine match the vision (also the cost fixes / cleanup):** stop generating hook + per-item "why" -> feed shows REAL HEADLINES ONLY; RANK-DON'T-HIDE (remove the score-6 cutoff, keep low-ranked reachable); fix escalation rate + add prompt caching (cost); re-add TRENDS to the pipeline. Smallest work, fixes cost, makes the existing engine produce the v1 feed.
  - **Phase 2 — The core daily loop:** niche onboarding (topics-to-start) + automated niche->source catalog w/ founder oversight; USER ACCOUNTS (needed for niches, personalization, payments); per-user re-rank + correction loop + "since you last opened" catch-up. This is the sticky ritual you measure retention on.
  - **Phase 3 — Monetize + grow:** freemium paywall + payments ($10-15) = where MRR starts; selective push + on-demand summaries (paid unlocks); curated-story marketing content engine.
  - Logic: engine cleanup -> core daily loop -> monetize. Don't add the paywall until there's a loop worth paying for.
- Flags: none

## ACTION LOG (Phase 1 implementation)
- ✅ DONE — **Kill hook + per-item why (cost fix #3 + presentation half of #4).** 2-file change:
  - score.py: removed hook+why from the scoring prompt + JSON schema + parsing; no longer passed to record_score; max_tokens 2048 -> 1024; __main__ top-10 debug print now shows title only. (Cuts the most expensive line — Sonnet OUTPUT tokens.)
  - db.py: record_score why/hook params now optional (default "") — no schema migration needed (NOT NULL satisfied by "").
  - publish.py: NO change needed — it already falls back to the real title when hook is empty (`item.get("hook") or item.get("title")`), so the feed now leads with REAL HEADLINES automatically. Verified the feed query returns i.title.
  - Both files py_compile clean; no stray hook/why refs in score.py. (Existing pre-change scored rows keep old hooks until they age out / are re-scored — acceptable.)
- ❌ NOT VIABLE — **Prompt caching (cost fix #2).** Measured: triage system prompt ~630 tokens, score ~810 tokens. Minimum cacheable prefix is 4096 tokens (Haiku 4.5) / 2048 (Sonnet 4.6). Both prompts are FAR below their threshold, so cache_control would silently cache nothing (a no-op). DO NOT re-attempt at current prompt sizes. (Claude initially mislabeled this a "safe win" — corrected after measuring.)

## Deferred work (revisit later)
- Remaining Phase 1 cost/engine fixes: (1) fix the 89% escalation rate in triage.py (highest-impact lever; needs careful tuning + validation via --retriage-kills), (4) rank-don't-hide (remove the s.score >= min_score filter in db.py feed query + publish; keep low-ranked reachable in a discovery surface — more a Phase 2 enabler), and re-add TRENDS to ingest.py.
- Rewrite CLAUDE.md to reflect the new consumer-reader vision (do after the engine changes land so it documents reality).
- NOTE: nothing committed yet — edits are in the working tree only (user hasn't asked to commit/push).

## Open flags (pending input)
