# CLAUDE.md — Project Briefing for Claude Code

This file briefs Claude Code on the daily-curator project. Read this before making any changes.

---

## What This Project Does

daily_curator.py is an automated content scouting tool for the Instagram/TikTok/Substack account @boymeetsblank_. It runs 3x per day via GitHub Actions and surfaces the most culturally relevant articles for carousel content creation.

Each run:
1. Fetches articles from Inoreader RSS feeds (last 48 hours)
2. Caps articles at 5 per source to ensure diversity
3. Sends articles to Claude AI for scoring (1–10)
4. Saves the top 10 picks (minimum score 7) to picks/picks-YYYY-MM-DD-HHMM.md

---

## Key Files

| File | Purpose |
|------|---------|
| `daily_curator.py` | Main script — all logic lives here |
| `requirements.txt` | Python dependencies |
| `.env` | Local credentials — never edit, never commit |
| `.github/workflows/daily_curator.yml` | GitHub Actions automation (runs 3x/day) |
| `picks/` | Output folder — one markdown file per run |
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
- **Celebrity filter:** Pure celebrity gossip is not relevant — content focus is cultural impact only
- **Timestamped filenames:** picks-YYYY-MM-DD-HHMM.md so all 3 daily runs are preserved
- **Auto token refresh:** Script uses INOREADER_REFRESH_TOKEN to get a fresh access token every run — no manual token management needed

---

## Claude Prompt Philosophy

The Claude scoring prompt evaluates articles on 4 criteria:
1. Trending — are people actively discussing this?
2. Timely — did it break in the last 24–48 hours?
3. Cultural — does it connect to a broader cultural moment?
4. Carousel — could this become a carousel post?

Political content is automatically scored 1 regardless of traction.
Pure celebrity gossip is automatically scored 1 regardless of traction.

---

## GitHub Actions Schedule

Runs automatically at:
- 8:30 AM CT (14:30 UTC)
- 3:30 PM CT (21:30 UTC)
- 8:30 PM CT (02:30 UTC next day)

Each run commits the picks file back to the repo.

---

## Required GitHub Secrets

All 5 must be set in repo Settings → Secrets → Actions:
- ANTHROPIC_API_KEY
- INOREADER_APP_ID
- INOREADER_APP_KEY
- INOREADER_TOKEN
- INOREADER_REFRESH_TOKEN

---

## Common Commands
```
python3 daily_curator.py     # Run locally
git add .                    # Stage changes
git commit -m "message"      # Commit
git push                     # Push (if rejected, run git pull --rebase first)
```

---

## Things to Never Touch

- `.env` — contains real credentials, never commit this
- `picks/` folder contents — these are outputs, not source files
- GitHub Secrets — set in GitHub UI, not in code

---

## Feature Roadmap

**Already Built ✅**
1. Core script — fetches Inoreader articles, scores with Claude, saves picks as markdown
2. GitHub Actions automation — runs 3x per day automatically
3. Timestamped filenames — preserves all 3 daily runs
4. Per-source article cap — max 5 articles per source for diversity
5. Politics filter — auto-scores political content a 1
6. README — full setup and project documentation
7. CLAUDE.md — project briefing for Claude Code on iPad

**Phase 1 — Fix Discovery**
8. Reddit trend detection — catches breaking stories before publications write about them
9. Google Trends integration — real time signal of what people are actively searching
10. Cross-source trend detection — flag when multiple sources cover the same story
11. YouTube trending integration — viral videos as an early cultural signal
12. Celebrity filter — auto-score pure celebrity gossip a 1 to reduce noise

**Phase 2 — Make It a Real Product**
13. Custom scrollable feed — beautifully designed webpage on GitHub Pages, updates 3x/day
14. Deduplication — prevent the same story appearing across multiple daily runs
15. Feedback loop / taste training — thumbs up/down that calibrates Claude's scoring to your taste over time
16. iMessage or email notification — ping you the moment a 9+ story is found

**Phase 3 — Content Creation**
17. Draft carousel generator — turns picks into actual content drafts automatically
18. Platform fit scoring — rate each story for Instagram vs TikTok vs Substack
19. Best time to post suggestion — based on story type suggest optimal posting time
20. Content categories — tag each pick by type (music, sports, fashion, tech)

**Phase 4 — Reporting**
21. Score history — track which story types score highest over time to tune the prompt
22. Weekly digest — every Sunday summarize the week's best picks and dominant themes
