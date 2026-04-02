# CLAUDE.md — Project Briefing for Claude Code

This file briefs Claude Code on the daily-curator project. Read this before making any changes.

---

## What This Project Does

daily_curator.py is an automated content scouting tool for **Blank** (formerly @boymeetsblank_), a culture intelligence platform. It runs 3x per day via GitHub Actions and surfaces the most culturally relevant articles for carousel content creation.

Each run:
1. Fetches articles from Inoreader RSS feeds (last 48 hours)
2. Caps articles at 5 per source to ensure diversity
3. Detects stories covered by 3+ sources (cross-source trend signal)
4. Fetches live trending topics from X (Twitter) and Google Trends via Apify
5. Sends everything to Claude AI for scoring (1–10)
6. Deduplicates same-story picks using Claude topic clustering
7. Saves the top 10 picks (minimum score 7) to picks/picks-YYYY-MM-DD-HHMM.md

The picks are also published to a live web feed at:
**https://boymeetsblank.github.io/daily-curator**

---

## Product Identity

The product is called **Blank**. This name appears in the web feed header wordmark and all public-facing surfaces. The previous handle (@boymeetsblank_) is no longer used in the UI. The brand aesthetic is editorial, premium, and culture-forward.

---

## Key Files

| File | Purpose |
|------|---------|
| `daily_curator.py` | Main script — all logic lives here |
| `requirements.txt` | Python dependencies |
| `.env` | Local credentials — never edit, never commit |
| `.github/workflows/daily_curator.yml` | GitHub Actions automation (runs 3x/day) |
| `.github/workflows/deploy-pages.yml` | Deploys the web feed to GitHub Pages on every push to main |
| `index.html` | GitHub Pages web feed — fetches picks_data.json and renders the feed |
| `picks/` | Output folder — one markdown file per run |
| `CHANGELOG.md` | Feature history — must be updated with every change |
| `README.md` | Full setup guide for humans |

---

## Settings (top of daily_curator.py)
```python
HOURS_BACK              = 48   # How far back to fetch articles
MAX_ARTICLES_TO_SEND    = 60   # Max articles fetched from Inoreader
MAX_ARTICLES_PER_SOURCE = 5    # Per-source cap for diversity
MIN_SCORE               = 7    # Minimum score to surface a pick
MAX_PICKS               = 10   # Max picks per run
```

---

## Key Decisions Already Made

- **Per-source cap:** Max 5 articles per source so ESPN and Complex don't dominate
- **Politics filter:** Claude prompt explicitly scores political articles a 1 — this account is politics-free
- **Celebrity gossip filter:** Claude prompt scores pure celebrity gossip a 1 — focus is cultural impact, not tabloid news
- **Timestamped filenames:** picks-YYYY-MM-DD-HHMM.md so all 3 daily runs are preserved
- **Auto token refresh:** Script uses INOREADER_REFRESH_TOKEN to get a fresh access token every run — no manual token management needed
- **Cross-source trend detection:** Articles covered by 3+ sources get a score bonus as evidence of real cultural momentum
- **Apify trends:** X (Twitter) and Google Trends trending topics are fetched via Apify on each run and mixed in with Inoreader articles as standalone "trend items" for Claude to score
- **Claude topic clustering:** After scoring, picks are sent back to Claude to group same-story duplicates into clusters. Only the highest-scoring pick per cluster survives
- **Cross-run URL dedup:** URLs from earlier runs today are excluded so the same article never surfaces twice in one day
- **Claude eval retry:** If Claude returns unparseable JSON, the scoring call is retried once before failing
- **OG image fallback:** After Inoreader fetch, articles missing images are enriched by concurrently fetching their `og:image` meta tag (10 workers, 5s timeout each) so cards in the feed always have a thumbnail when available
- **Flat reverse-chron feed:** The web feed displays all picks newest-first as a single stream — no Morning/Afternoon/Evening grouping or time-of-day filter pills
- **Blank wordmark:** Header uses "BLANK" in spaced uppercase sans-serif with an italic serif tagline — no @handle or social branding

---

## Claude Prompt Philosophy

The Claude scoring prompt evaluates articles and trend items on 4 criteria:
1. Trending — are people actively discussing this?
2. Timely — did it break in the last 24–48 hours?
3. Cultural — does it connect to a broader cultural moment?
4. Carousel — could this become a carousel post?

**Automatic score of 1:** political content, pure celebrity gossip.

**Score bonus:** articles flagged as trending across 3+ sources get +1–2 points.

**Trend items:** items from "X (Twitter) Trending" or "Google Trends" are evaluated on whether the topic itself is culturally interesting and carousel-worthy.

### Carousel Hook Format

The ANGLE field uses a structured format with a psychological trigger label:

```
[TRIGGER: Disbelief] The last Laker to score 60 / was Kobe. / In his final game.
```

Rules:
- Trigger must be one of: Curiosity, FOMO, Disbelief, Defensiveness, Relief, Greed
- Lines separated by `/` indicate carousel slide breaks
- Each line is 7 words or fewer; maximum 3 lines

---

## GitHub Actions Workflows

### daily_curator.yml — Content scouting (3x/day)
Runs automatically at:
- 8:00 AM CT (13:00 UTC)
- 1:00 PM CT (18:00 UTC)
- 9:00 PM CT (02:00 UTC next day)

Each run commits the picks file back to the repo, which then triggers deploy-pages.yml.

### deploy-pages.yml — Web feed deployment
Triggers on every push to `main`. Parses all picks/*.md files into picks_data.json and deploys index.html + picks_data.json to GitHub Pages.

**One-time setup:** In repo Settings → Pages, set source to "GitHub Actions".

---

## Required GitHub Secrets

All 6 must be set in repo Settings → Secrets → Actions:
- ANTHROPIC_API_KEY
- INOREADER_APP_ID
- INOREADER_APP_KEY
- INOREADER_TOKEN
- INOREADER_REFRESH_TOKEN
- APIFY_API_TOKEN

---

## Platform Vision

Blank started as a personal content scouting tool but the long-term vision is bigger:

**Core mission:** A daily briefing tool that keeps people informed about what matters in their niche worlds. Not a content creator tool — a signal-over-noise intelligence layer for anyone who wants to stay sharp in a specific domain.

**Unique angle:**
- Natural language setup — describe your interests in plain English, the tool figures out the sources
- AI editorial judgment — not just aggregation, but curation with transparent reasoning (why this story matters, why now)
- Cross-platform signals — RSS feeds, X trends, Google trends, and more converge into one ranked briefing
- Intentionally finite — 10 picks max per run, so every item earns its place

**Long term:** A no-code AI curation platform open to the public. Anyone should be able to spin up their own daily briefing — sports, finance, tech, fashion, whatever their niche — without writing a line of code.

**Planned phases:**
- Phase 5 — Platform: natural language feed controls (describe what you want, AI updates your sources), dynamic source library (suggest + validate new RSS feeds on demand), public platform for anyone to create their own briefing, direct RSS feed ingestion
- Breaking News Mode: a lightweight watchdog that runs every 30–60 minutes, surfaces ONE breaking pick per check, estimated cost $15–30/month — for users who can't wait for 3x/day
- Always show X trending topics on feed: a dedicated section in the web feed showing the top 10–20 X trending topics from the latest run, always visible regardless of score filter

---

## Current To-Do List

Items are not in priority order. Each is a discrete project.

- **Feedback loop** — wire up ↑ ↓ vote arrows on pick cards via GitHub API so user reactions are stored and can inform future scoring
- **Category-aware scoring** — ensure diverse picks across music, sports, fashion, tech etc. so no single category dominates a run
- **Breaking News Mode** — lightweight real-time watchdog that runs every 30–60 min and surfaces one breaking story per check
- **Always show full X trending topics** — dedicated always-visible section in the web feed showing the full top 10–20 X trending topics from the latest run
- **Code review with Simplify skill** — run `/simplify` on daily_curator.py and index.html for a quality pass
- **Web app testing setup** — add automated tests (Playwright or similar) for the index.html feed
- **MCP Builder exploration** — evaluate whether MCP servers could replace or augment Apify for trend fetching
- **9+ score tuning** — monitor current scoring output before adjusting; no changes yet
- **Reddit trend detection** — still blocked pending Reddit API access; revisit when credentials are available
- **YouTube trending integration** — add YouTube trending videos as a signal source alongside X and Google Trends
- **Email/notification system** — token expiry alert + high score alert (score 9+) via email or webhook
- **Weekly digest** — automated weekly rollup of the top picks across all runs

---

## Git Workflow

**Always commit and push changes to the `main` branch.** Never push to any other branch unless explicitly instructed by the user.

---

## Working Branch

**Always develop and push on `main`.** Never use feature branches unless explicitly asked.

Before starting any session, run:
```
git fetch origin main && git pull origin main
```

## Common Commands
```
python3 daily_curator.py     # Run locally
git add .                    # Stage changes
git commit -m "message"      # Commit
git push origin main         # Push
```

---

## Things to Never Touch

- `.env` — contains real credentials, never commit this
- `picks/` folder contents — these are outputs, not source files
- GitHub Secrets — set in GitHub UI, not in code

---

## Maintaining the Changelog

**Every time you add, modify, or remove a feature, you must update `CHANGELOG.md`** with the date and a brief description of what changed. Always add the new entry at the **top** of the file (just below the `---` divider), under a `## [YYYY-MM-DD] Feature Name` heading. Never append to the bottom.

**At the start of every session, fetch and read the latest `CHANGELOG.md` from the remote** (`git fetch origin main && git pull origin main`) before doing anything else. This ensures you have the full picture including any changes made outside of the current session.
