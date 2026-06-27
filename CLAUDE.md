# CLAUDE.md — Project Briefing for Claude Code

This file briefs Claude Code on the Blank project. Read this before making any changes.

> Deeper product context (the full vision, decisions, and rationale) lives in
> [`brainstorms/2026-06-27-blank-platform-vision.md`](brainstorms/2026-06-27-blank-platform-vision.md).
> Read it before any product/strategy work.

---

## What Blank Is

**Blank is a consumer reading app where the AI is your editor.** Think "Apple News
meets an AI editor that scores, de-duplicates, and ranks the news for you." It helps
a curious, time-poor person stay on top of *their* niches without sifting through noise.

The AI's job is **selection and organization, not authorship**: it ranks what matters,
clusters multi-source stories, and surfaces what you should know — using the *real*
headlines, never rewritten ones.

This **replaces** the old product entirely. Blank used to be a 3x/day carousel-scouting
tool ("culture intelligence platform"). That is retired — see *Legacy / Retired* below.

Delivery: a **PWA now, native later**. Business model: **freemium** (free tier =
a few niches + the ranked living feed + daily catch-up; paid ~$10–15/mo = unlimited
niches/sources, instant push, taste-learning, on-demand summaries).

---

## The Engine (the new continuous pipeline)

A continuous cascade orchestrated by `run_pipeline.py`, run every 10 minutes by
`.github/workflows/blank.yml`. State lives in `blank.db` (SQLite), committed back to
the repo each run. The live feed is built from `blank.db` by `deploy-pages.yml`.

Pipeline stages (`run_pipeline.py`):
1. **Ingest** (`ingest.py`) — poll active RSS sources from `sources.json`, dedup new items into `blank.db`.
2. **Enrich OG** (`ingest.py`) — fetch `og:image` for recent items missing a thumbnail.
3. **Triage** (`triage.py`) — **Haiku 4.5** recall gate: KILL (safe to discard) vs ESCALATE. Batches of 20. Deliberately recall-biased — it only kills *structural* junk (SEO sludge, login walls, contentless stubs), never for topic/quality. When in doubt, ESCALATE.
4. **Score** (`score.py`) — **Sonnet 4.6** scores escalated items 1–10 against the rubric. Batches of 12. This is the taste layer.

**Per-source cap:** `PER_SOURCE_CAP = 15` in `db.py`. Only the newest 15 items per
source are ever triaged/scored (the feed balances each source to a small display share,
so scoring more is wasted spend). Ranking is over *all* items per source so the cap
doesn't refill across runs.

**Cost architecture — the load-bearing rule:** the engine scores **one global feed,
once**. Cost scales with *article volume*, not user count. **Never introduce per-user
LLM scoring** — that flips cost to users × articles and is the thing to avoid.
Personalization (planned, Phase 2) is a cheap per-user *taste profile* + a near-free
re-rank on top of the global score, never a fresh LLM pass per user.

---

## Key Files

| File | Purpose |
|------|---------|
| `run_pipeline.py` | Engine orchestrator — ingest → enrich → triage → score |
| `ingest.py` | RSS polling, dedup, OG-image enrichment |
| `triage.py` | Haiku KILL/ESCALATE recall gate |
| `score.py` | Sonnet 1–10 scoring (the taste layer) |
| `db.py` | SQLite data layer for `blank.db`; holds `PER_SOURCE_CAP` |
| `blank.db` | SQLite store — engine output, committed each run. Do not hand-edit |
| `publish.py` | Static feed renderer (the live feed is built by `deploy-pages.yml` from `blank.db`) |
| `sources.json` | Active source list |
| `.github/workflows/blank.yml` | The engine — runs every 10 min, commits `blank.db` |
| `.github/workflows/deploy-pages.yml` | Builds the live feed from `blank.db` → GitHub Pages |
| `index.html` | The rendered web feed (the Canvas) |
| `CHANGELOG.md` | Feature history — must be updated with every change (see below) |
| `README.md` | Setup guide for humans |
| `brainstorms/` | Vision/discovery docs — start with the 2026-06-27 platform brainstorm |

---

## Key Decisions Already Made

- **The AI is the editor:** selection + organization, not authorship. No rewritten headlines.
- **Real headlines only:** the feed shows the source's real title — AI hook/“why” generation was removed. On-demand "catch me up" summaries (on tap) are the planned place for AI text.
- **Rank, never hide:** the product intent is to rank everything and keep low-ranked items reachable (a discovery surface), with a user correction loop ("this wasn't noise"). *Not yet implemented* — `score.py` `FEED_THRESHOLD = 6` and the `get_feed` `min_score` filter still drop sub-6 items. This is a planned Phase 1 change.
- **Per-source cap = 15** (see Engine above).
- **Global scoring only** — never per-user LLM scoring (see cost rule above).
- **Trends:** X (Twitter) + Google Trends (via Apify) are planned to be re-added to `ingest.py`, routed through the same triage→score→rank pipeline (tagged so they can be matched to a user's niches). Not in the engine yet.
- **Onboarding:** "topics to get started, sources to go deep" — pick niches → instant full feed; hand-picking sources is an opt-in power-user path.
- **Source catalog:** niche→sources is to be automated (auto-discovery) with founder visibility/oversight over what's selected per niche.
- **Name is NOT final:** finalists are **Keen** and **Caret**, with **Blank** as the fallback. Don't hardcode a final brand name yet.

---

## Scoring Rubric Philosophy

`score.py` asks Sonnet to surface what's most worth a curious person's attention across
*any* subject — it holds no topic opinions (politics, sports, niche hobbies are all
first-class). An item earns its place on **either** axis: **interest** (surprising,
novel, "wait, what?") **or** importance (consequential, major). Strong on either =
high score. Criteria (judgment, not arithmetic): trending, timely, cultural,
significance. Output is score + criteria + soft-floor flags only (no prose for the feed).

---

## GitHub Actions Workflows

### blank.yml — the engine (every 10 minutes)
Runs `run_pipeline.py` on a `*/10 * * * *` cron + manual dispatch. Single-concurrency
(`cancel-in-progress: false`) so two runs never write `blank.db` at once. Commits
`blank.db` back to `main` each run with a retry/rebase loop (other workflows also push).

### deploy-pages.yml — live feed deployment
Builds the feed from `blank.db` (scored items) into `picks_data.json` and deploys
`index.html` to GitHub Pages. Triggers on `workflow_run` after Blank Engine completes
(bot pushes don't trigger workflows directly).

---

## Required GitHub Secrets

The **engine** (`blank.yml`) needs only:
- `ANTHROPIC_API_KEY`

`APIFY_API_TOKEN` will be needed again once trends are re-added. The Inoreader secrets
(`INOREADER_*`) belong to the legacy engine.

---

## Legacy / Retired

These are the OLD carousel-scouting product. Kept in-repo as reference only — do not
build on them; they are being phased out as the engine covers their ground:
- `daily_curator.py` + `.github/workflows/daily_curator.yml` (3x/day batch)
- `picks/` (old markdown output — outputs, not source)
- The "carousel post" / "culture intelligence platform" framing

(`breaking_news_check.py` / `breaking_news.yml` is the **live feed** check — not a
"breaking news monitor".)

---

## Git Workflow

**Always commit and push changes to the `main` branch.** Never push to any other branch
unless explicitly instructed by the user. Never use feature branches unless explicitly asked.

Before starting any session, run:
```
git fetch origin main && git pull origin main
```

The engine pushes `blank.db` every 10 minutes, so `main` moves under you — expect to
`git pull --rebase` before pushing. If a dirty `blank.db` blocks the rebase, `git stash`
first (the remote copy is authoritative).

---

## Things to Never Touch

- `.env` — contains real credentials, never commit this
- `blank.db` — engine output; let the pipeline write it, don't hand-edit
- `picks/` folder contents — legacy outputs, not source files
- GitHub Secrets — set in GitHub UI, not in code

---

## Frontend Design

For any UI or frontend changes, always read and apply the frontend design skill at
~/.claude/skills/frontend-design/SKILL.md before writing any code.

---

## Maintaining the Changelog

**Every time you add, modify, or remove a feature, you must update `CHANGELOG.md`** with
the date and a brief description of what changed. Always add the new entry at the **top**
of the file (just below the `---` divider), under a `## [YYYY-MM-DD] Feature Name` heading.
Never append to the bottom.

**Keep CHANGELOG.md to the 20 most recent entries.** When adding a new entry would push
the total past 20, delete the oldest entry at the bottom.
