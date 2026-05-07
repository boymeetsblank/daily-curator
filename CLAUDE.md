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
7. Saves the top 10 picks (minimum score 6) to picks/picks-YYYY-MM-DD-HHMM.md

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

---

## GitHub Actions Workflows

### daily_curator.yml — Content scouting (3x/day)
Runs automatically at:
- 7:30 AM CT (12:30 UTC / CDT) — 6:30 AM CST in winter
- 1:30 PM CT (18:30 UTC / CDT) — 12:30 PM CST in winter
- 7:30 PM CT (00:30 UTC / CDT) — 6:30 PM CST in winter

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

---

## Things to Never Touch

- `.env` — contains real credentials, never commit this
- `picks/` folder contents — these are outputs, not source files
- GitHub Secrets — set in GitHub UI, not in code

---

## Frontend Design

For any UI or frontend changes, always read and apply the frontend design skill at ~/.claude/skills/frontend-design/SKILL.md before writing any code.

---

## Maintaining the Changelog

**Every time you add, modify, or remove a feature, you must update `CHANGELOG.md`** with the date and a brief description of what changed. Always add the new entry at the **top** of the file (just below the `---` divider), under a `## [YYYY-MM-DD] Feature Name` heading. Never append to the bottom.

**Keep CHANGELOG.md to the 20 most recent entries.** When adding a new entry would push the total past 20, delete the oldest entry at the bottom.
