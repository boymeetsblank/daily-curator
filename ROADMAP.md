# Blank — Product Roadmap

## In Progress
- Replace Inoreader with Direct RSS (sources.json) — run in parallel, keep Inoreader as fallback
- Fix vote state not persisting on refresh
- Source diversity — populate sources.json with current sources + new niche additions

## Visual / Frontend
- Rarity tier overhaul — Blue (8), Purple (9), Orange (10) with font glow in both List and Card view
- List view permanent left border in rarity color per row
- Remove date column from list view
- Accordion left border in rarity color, remove flat grey background
- Rename "Summary" to "Why it matters" in accordion
- X Trends card hidden by default on desktop (already done on mobile)

## Scoring
- Fix 10/10 scoring — guideline not quota, roughly once every 1-3 runs when truly earned

## Feedback Loop
- Build proper feedback loop once 50+ votes accumulated — influences Claude scoring based on content patterns, not just source names
- Source Discovery — AI-powered source recommendations based on voting patterns. Suggests new RSS sources not currently in sources.json that match user preferences

## Major Features
- Natural language feed filter — prompt bar to tune feed in real time
- "The Zeitgeist" — AI-generated sentence summarizing cultural moment per run
- Multi-user support — Mo + wife as initial beta test
- Supabase migration — move from JSON files to proper database, per-user data, authentication

## Parked
- Left sidebar / Niche Navigator
- Inoreader reader URL for paywalled articles
- Manual on-demand refresh button
- Blank app icon design
- cron-job.org for reliable run timing
