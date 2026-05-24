"""
breaking_news_check.py — Breaking News Monitor

Polls your subscribed RSS feeds (sources.json) every 5 minutes for articles
published in the last 90 minutes. New items are enriched with a one-sentence
context via Claude Haiku, then written to breaking_news.json (deployed to
GitHub Pages). If new items are found, a Web Push notification is sent.

Google Trends are refreshed from the unofficial daily trends endpoint whenever
the cached data is older than 10 minutes (free, no Apify).
X (Twitter) trending topics are refreshed every 10 minutes via trends24.in (free, no auth).
TikTok trends are available via the 3x/day Apify runs in daily_curator.py.

Writes:
  breaking_news.json       — deployed to GitHub Pages for the frontend
  breaking_news_state.json — persists seen article IDs across runs
"""

import hashlib
import json
import re
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import requests

# ── Config ────────────────────────────────────────────────────────────────────

BREAKING_NEWS_TTL_HOURS = 12
FEED_WINDOW_MINUTES     = 90   # articles published this recently count as breaking
MAX_KNOWN_IDS           = 500  # cap state file growth
MAX_LIVE_PER_SOURCE     = 5    # max items per source within the cap window
SOURCE_CAP_WINDOW_HOURS = 2    # rolling window for per-source cap
MAX_FEED_SIZE           = 40   # max total items in the live feed at once
FAILED_IDS_TTL_HOURS    = 4    # failed items re-enter the pipeline after this long
CLUSTER_THRESHOLD       = 3    # items in a cluster before escalating to main feed
CLUSTER_TTL_HOURS       = 24   # prune clusters from state after this long
REDDIT_ALL_MIN_SCORE    = 500  # minimum upvotes for r/all posts
REDDIT_SUB_MIN_SCORE    = 200  # minimum upvotes for culture-subreddit hot posts
REDDIT_SUB_AGE_HOURS    = 12   # culture-subreddit posts must be under this age

SOURCES_FILE        = "sources.json"
STATE_FILE          = "breaking_news_state.json"
OUTPUT_FILE         = "breaking_news.json"
SOCIAL_TRENDS_PATH  = "social_trends.json"
GOOGLE_TRENDS_URL     = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
GOOGLE_TRENDS_MAX_AGE = 10    # minutes before we try to refresh google trends
X_TRENDS_URL          = "https://trends24.in/united-states/"
X_TRENDS_MAX_AGE      = 10    # minutes before we try to refresh X trending

FEED_URL   = "https://boymeetsblank.github.io/daily-curator/"
VAPID_CLAIMS = {"sub": "mailto:mjaffry1@gmail.com"}

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BreakingNewsBot/1.0)"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def item_id(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()[:12]


def filter_and_enrich_items(candidates: list[dict], trends: dict | None = None, live_clusters: dict | None = None) -> list[dict]:
    """
    Batch quality gate via Claude Haiku.

    Scores each candidate 1-10. Items scoring >= 5 are returned with
    haiku_score attached. Items scoring 9+ are candidates for Sonnet
    escalation and push notification.

    trends: optional dict {x, google, youtube, tiktok} of live topic lists
    used to boost items that match live social signals.

    live_clusters: existing cluster state so Haiku knows which stories are
    already building — corroborating signals score higher.

    Falls back to surfacing all candidates unfiltered if the API is
    unavailable or returns unparseable JSON.
    """
    if not candidates:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ⚠️  ANTHROPIC_API_KEY not set — surfacing all candidates unfiltered.")
        for c in candidates:
            c["haiku_score"] = 8
        return candidates

    items_block = "\n".join(
        f"{i+1}. [Source: {c['source_name']}] {c['topic']}" +
        (f"  [{c['traffic']}]" if c.get("traffic") else "")
        for i, c in enumerate(candidates)
    )

    # Build building clusters block — shows Haiku which stories already have signals
    clusters_block = ""
    if live_clusters:
        active = [
            (c["topic"], len(c["item_ids"]))
            for c in live_clusters.values()
            if c.get("topic") and c.get("item_ids")
        ]
        if active:
            cluster_lines = "\n".join(
                f"  - {topic} ({count} independent signal{'s' if count != 1 else ''} so far)"
                for topic, count in sorted(active, key=lambda x: -x[1])
            )
            clusters_block = (
                f"\n\nBUILDING STORIES — these topics already have independent signals in the live feed right now:\n"
                f"{cluster_lines}\n"
                f"If any item below corroborates one of these stories, that convergence is strong evidence "
                f"something real is happening — score it at least 1 point higher than you would in isolation."
            )

    # Build live social signals block — include rank/volume where available
    social_block = ""
    if trends:
        lines = []
        if trends.get("x"):
            x_ranks = trends.get("x_ranks", {})
            x_items = [f"#{x_ranks.get(t, i+1)} {t}" for i, t in enumerate(trends["x"][:15])]
            lines.append("X (Twitter) trending (ranked): " + ", ".join(x_items))
        if trends.get("google"):
            g_eng = trends.get("google_engagement", {})
            g_items = [f"{t} ({g_eng[t]})" if g_eng.get(t) else t for t in trends["google"][:15]]
            lines.append("Google Trends (with search volume): " + ", ".join(g_items))
        if trends.get("youtube"):
            lines.append("YouTube trending: " + ", ".join(trends["youtube"][:10]))
        if trends.get("tiktok"):
            lines.append("TikTok trending: " + ", ".join(trends["tiktok"][:10]))
        if trends.get("reddit_hot"):
            lines.append("Reddit r/all hot (recent curator run): " + ", ".join(trends["reddit_hot"][:10]))
        if lines:
            social_block = "\n\nLIVE SOCIAL SIGNALS — these topics are trending right now. If an item directly relates to one of these, it's evidence something is actively happening:\n" + "\n".join(lines)

    prompt = f"""You are the editorial filter for Blank — a culture intelligence platform for trend-forward people who want to know what's happening right now.

Your job: decide what's worth surfacing in a live culture feed. Score each item 1–10. Be strict — most items should score 5–7. Reserve 8–9 for genuinely important moments. When in doubt between two scores, choose the lower one.

SCORING GUIDE:
- 10: A cultural moment — someone will reference this a year from now. Genuinely rare, never forced.
- 9: You have to tell someone about this right now. Broad audience, immediate significance.
- 8: A significant, unexpected development that most culturally-aware people — not just fans of one niche — would genuinely care about.
- 7: Worth surfacing — something real is happening, with clear cultural or news relevance.
- 6: Made the cut — relevant and real, but minimum bar for the live feed.
- 1–5: Filtered out — noise, too dry, too predictable, too niche, or irrelevant.

AUTOMATIC SCORE OF 1 — always score these 1, no exceptions:
- Political content: partisan commentary, policy debates, elections, legislation, politicians, government actions, legal/court cases involving political figures, war/conflict updates, diplomatic news, Fed/inflation/regulatory coverage
- Generic social media posts: good morning greetings, motivational quotes, hashtag participation, lifestyle posts, nature photos, feel-good content, emoji-heavy filler posts
- Personal creator self-promotion: an individual or small account announcing or promoting their own art, merchandise, stickers, prints, zines, or projects — regardless of likes
- Crowdfunding and campaign posts: Kickstarter, Indiegogo, Patreon, or any "back my project / last day to support" post
- Trivial observations, viral jokes, or "look at this funny thing" posts with no cultural news significance (e.g. pointing out a typo, a funny coincidence, a relatable meme)
- Local or regional news with no national/cultural relevance
- Industry/trade publication articles about operational, business, or technical topics for specialist audiences (e.g. hospitality tech, fire academy training, supply chain updates)

BARE TRENDING TOPIC NAMES (X, Google, TikTok trend topics that are just a name or short phrase with no article context):
- Score 5–6. They are real-time signals that something is happening right now — often surfacing before any article exists.
- Score 5 for a name that could trend for many reasons. Score 6 when the name clearly belongs to a culturally significant person, team, or moment where trending almost certainly means something just happened.
- Do NOT score these 1. They belong in the live feed as early signals and are critical for clustering related items into a coherent story.

ENGAGEMENT SIGNALS: Numbers in brackets after an item show real engagement — upvotes, comments, search volume, or trending rank (e.g. [10,000 upvotes · 800 comments], [#3 on X], [200K+ searches]). Weight these heavily as evidence of actual audience reach:
- A Reddit post with 10K+ upvotes has real traction — score it at least 7.
- A Reddit post with 30K+ upvotes is almost certainly culturally significant — score it at least 8.
- An X topic ranked #1–5 is what everyone is talking about right now.
- A Google Trends topic with 100K+ searches is a strong signal of real-time interest.
- A Google Trends topic with 250K+ searches is dominating the day's conversation.
- High engagement alone doesn't override the auto-1 rules (politics, generic lifestyle posts), but for any borderline story, strong engagement should break the tie upward.

IMPORTANT:
- For Reddit posts: upvote count is strong signal — 10K+ means real traction, 30K+ means broadly significant. Score on the combination of topic substance AND engagement.
- For YouTube trending videos: score on whether the video captures a genuine cultural moment — a performance, a reveal, a reaction with broad significance.
- Anything genuinely significant has a fair shot regardless of topic area — a major sports result, a surprise album drop, a landmark business moment, a cultural event. Topic area is never a reason to score down.{social_block}{clusters_block}

Respond with a JSON array only — one object per item, same order as input:
[{{"score": <int>}}]

Items:
{items_block}"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=15 * len(candidates),
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        results = json.loads(raw)
    except Exception as e:
        print(f"   ⚠️  Quality gate failed ({e}) — surfacing all candidates unfiltered.")
        for c in candidates:
            c["haiku_score"] = 8
        return candidates

    if len(results) != len(candidates):
        print(f"   ⚠️  Quality gate returned {len(results)} results for {len(candidates)} candidates — surfacing all unfiltered.")
        for c in candidates:
            c["haiku_score"] = 8
        return candidates

    passed = []
    for candidate, result in zip(candidates, results):
        score = result.get("score", 0)
        if score >= 5:
            candidate["haiku_score"] = score
            passed.append(candidate)
        else:
            print(f"   ✂️  Filtered (score {score}): {candidate['topic'][:70]}")

    print(f"   🎯 Quality gate: {len(passed)}/{len(candidates)} candidates passed.")
    return passed


def escalate_to_sonnet(items: list[dict]) -> None:
    """
    For items scoring 9+, call Sonnet to write editorial context and a
    carousel hook, then write a picks markdown file so they appear in
    the main feed.
    """
    if not items:
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    items_block = "\n".join(
        f"{i+1}. [Source: {c['source_name']}] {c['topic']}"
        for i, c in enumerate(items)
    )

    prompt = f"""You are an editorial writer for Blank, a culture intelligence platform focused on sneakers, fashion, music, sports, tech, and internet culture.

For each breaking news item below, write:
1. Why it matters — 2-3 sentences, editorial and specific. Explain the cultural significance of this exact story right now.
2. Hook — a carousel post hook in this format: [TRIGGER: word] First line. / Second line. / Third line.

Respond with a JSON array only — one object per item, same order as input:
[{{"why": "<string>", "hook": "<string>"}}]

Items:
{items_block}"""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300 * len(items),
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        results = json.loads(raw)
    except Exception as e:
        print(f"   ⚠️  Sonnet escalation failed: {e}")
        return

    if len(results) != len(items):
        print(f"   ⚠️  Sonnet returned {len(results)} results for {len(items)} items — skipping escalation.")
        return

    now = datetime.now(tz=timezone.utc)
    timestamp    = now.strftime("%Y-%m-%d-%H%M")
    display_time = now.strftime("%Y-%m-%d at %I:%M %p")

    blocks = []
    for i, (item, result) in enumerate(zip(items, results), 1):
        score = item.get("haiku_score", 9)
        why   = result.get("why", "").strip()
        hook  = result.get("hook", "").strip()

        block  = f"## Pick #{i} — Score: {score}/10\n\n"
        block += f"**{item['topic']}**\n"
        block += f"*{item['source_name']}*\n"
        block += f"[Read the full article →]({item['search_url']})\n"
        block += "**Live Pick:** true\n"
        if why:
            block += f"\n**Why it matters:**\n{why}\n"
        if hook:
            block += f"\n**Hook:**\n{hook}\n"
        block += "\n---\n"
        blocks.append(block)
        print(f"   🚀 Escalated: {item['topic'][:70]}")

    header  = f"# Live Picks — {display_time}\n\n"
    header += f"> **Source:** Live feed — Breaking news monitor\n"
    header += f"> **Picks surfaced:** {len(blocks)}\n\n---\n\n"

    os.makedirs("picks", exist_ok=True)
    filepath = f"picks/picks-{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(blocks))

    print(f"   📝 Wrote {len(blocks)} live pick(s) to {filepath}")


def cluster_new_items(new_items: list[dict], live_clusters: dict, api_key: str) -> dict:
    """
    Uses Haiku to assign new live feed items to existing clusters or create new ones.
    Returns updated live_clusters dict. Items get a 'cluster_id' field attached if clustered.
    """
    if not new_items or not api_key:
        return live_clusters

    cluster_block = ""
    if live_clusters:
        lines = [
            f"  [{cid}] {c['topic']} ({len(c['item_ids'])} items)"
            for cid, c in live_clusters.items()
        ]
        cluster_block = "EXISTING STORY CLUSTERS:\n" + "\n".join(lines) + "\n\n"

    items_block = "\n".join(
        f"{i+1}. [Source: {item['source_name']}] {item['topic']}"
        for i, item in enumerate(new_items)
    )

    prompt = f"""You are a news clustering engine for a live culture feed.

{cluster_block}NEW ITEMS TO CLASSIFY:
{items_block}

For each new item, decide ONE of:
A) It covers the SAME specific event as an existing cluster → return that cluster's exact ID string
B) It starts a NEW cluster (a distinct event generating multiple signals) → return a concise topic label
C) It is standalone — does not cluster with anything → return null for both fields

RULES:
- Ask one question: did all these items exist because the SAME thing happened? If yes, they belong in one cluster — regardless of whether one item is the initial report, a detail reveal, a reaction, a stat breakdown, or a follow-up angle.
- Do NOT cluster items about genuinely different events, even in the same topic area or involving the same person.
- Generic posts, bare trend names without context, or unrelated items = standalone (null).
- New cluster topic labels should be specific and entity-focused: "Kendrick Lamar announces tour", not just "music".

Return a JSON array, one object per item, same order as input:
[{{"item_index": 0, "existing_cluster_id": "<id-string-or-null>", "new_cluster_topic": "<topic-if-new-or-null>"}}]"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60 * len(new_items),
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        results = json.loads(raw)
    except Exception as e:
        print(f"   ⚠️  Clustering failed ({e}) — skipping.")
        return live_clusters

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    for item, result in zip(new_items, results):
        item_id = item["id"]
        existing_cid = result.get("existing_cluster_id")
        new_topic    = result.get("new_cluster_topic")

        if existing_cid and existing_cid in live_clusters:
            if item_id not in live_clusters[existing_cid]["item_ids"]:
                live_clusters[existing_cid]["item_ids"].append(item_id)
            item["cluster_id"] = existing_cid
        elif new_topic:
            cid = hashlib.md5(new_topic.encode()).hexdigest()[:16]
            if cid not in live_clusters:
                live_clusters[cid] = {
                    "topic":                new_topic,
                    "item_ids":             [],
                    "created_at":           now_iso,
                    "last_escalated_size":  0,
                    "last_escalated_at":    None,
                }
            if item_id not in live_clusters[cid]["item_ids"]:
                live_clusters[cid]["item_ids"].append(item_id)
            item["cluster_id"] = cid

    return live_clusters


_ESCALATION_STOP_WORDS = {
    "with", "the", "that", "this", "from", "have", "been", "will", "about",
    "after", "their", "there", "which", "would", "could", "should", "than",
    "when", "where", "what", "into", "over", "just", "more", "some", "also",
    "says", "said", "show", "shows", "gets", "first", "year", "years", "week",
}

def _todays_pick_titles() -> list[str]:
    """Return bold-formatted titles from all picks files written today (UTC)."""
    import glob as _glob
    today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    titles = []
    for path in _glob.glob(f"picks/picks-{today_str}-*.md"):
        with open(path, encoding="utf-8") as f:
            content = f.read()
        titles += re.findall(r"\*\*([^*\n]+)\*\*\n\*[^*\n]+\*\n\[Read the full article", content)
    return titles


def _topic_already_covered(cluster_topic: str, published_titles: list[str], threshold: int = 2) -> str | None:
    """
    Return the matching published title if the cluster topic overlaps enough
    keywords with any already-published title today, else None.
    """
    def keywords(text: str) -> set[str]:
        return {
            w.lower() for w in re.findall(r"[a-zA-Z']+", text)
            if len(w) > 3 and w.lower() not in _ESCALATION_STOP_WORDS
        }

    topic_kw = keywords(cluster_topic)
    for title in published_titles:
        overlap = topic_kw & keywords(title)
        if len(overlap) >= threshold:
            return title
    return None


def escalate_cluster_to_sonnet(cluster: dict, cluster_items: list[dict], new_items_only: list[dict] | None = None) -> None:
    """
    Synthesizes a cluster of related live feed items into one unified main feed story.
    On first escalation: writes a new picks file.
    On re-escalation: appends a timestamped update to the existing picks file.
    """
    if not cluster_items:
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    now          = datetime.now(tz=timezone.utc)
    # Display time in CT (UTC-5, approximate — covers CDT)
    ct_now       = now - timedelta(hours=5)
    display_time = now.strftime("%Y-%m-%d at %I:%M %p UTC")
    ct_time_str  = ct_now.strftime("%-I:%M %p CT")

    is_update = bool(cluster.get("picks_file") and cluster.get("why_text") and new_items_only)

    if is_update:
        # ── Re-escalation: append a timestamped update ────────────────────────
        new_block = "\n".join(
            f"{i+1}. [Source: {item['source_name']}] {item['topic']}"
            for i, item in enumerate(new_items_only)
        )

        update_prompt = f"""You are the senior editor for Blank, a culture intelligence platform.

This story is already in the main feed: "{cluster['topic']}"

EXISTING WRITE-UP:
{cluster['why_text']}

NEW SIGNALS just joined the cluster:
{new_block}

Write a brief update paragraph (1–2 sentences) to append below the existing write-up.
- Some signals may be bare trending names — use your knowledge to infer what specifically just happened
- Be concrete: what changed, what happened, what's new
- Write with editorial confidence — you're adding to a live story, not hedging

Return JSON only: {{"update": "<1-2 sentence update>"}}"""

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=200,
                messages=[{"role": "user", "content": update_prompt}],
            )
            raw = resp.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            update_text = json.loads(raw).get("update", "").strip()
        except Exception as e:
            print(f"   ⚠️  Cluster update failed: {e}")
            return

        update_paragraph = f"\n**Update {ct_time_str}:** {update_text}"
        updated_why = cluster["why_text"] + update_paragraph

        picks_file = cluster["picks_file"]
        if os.path.exists(picks_file):
            content = open(picks_file, encoding="utf-8").read()
            # Replace the why section with the updated version
            old_why_block = f"\n**Why it matters:**\n{cluster['why_text']}\n"
            new_why_block = f"\n**Why it matters:**\n{updated_why}\n"
            content = content.replace(old_why_block, new_why_block, 1)
            with open(picks_file, "w", encoding="utf-8") as f:
                f.write(content)
            cluster["why_text"] = updated_why
            n_src = len(cluster_items)
            print(f"   🔗 Cluster updated ({n_src} signals) → {picks_file}: +{len(new_items_only)} new signal(s)")
            send_breaking_push([{
                "topic": f"Update: {cluster['topic']}",
                "context": update_text[:120],
                "search_url": FEED_URL,
                "source_name": "Live Cluster Update",
            }])
        else:
            # File missing — fall through to write a fresh one
            is_update = False

    if not is_update:
        # ── Guard: skip if main feed already has this story today ─────────────
        already_published = _todays_pick_titles()
        match = _topic_already_covered(cluster["topic"], already_published)
        if match:
            print(f"   ⏭️  Cluster '{cluster['topic'][:60]}' skipped — already in feed as: '{match[:60]}'")
            cluster["picks_file"] = "SUPPRESSED"  # prevent future re-escalation attempts
            return

        # ── First escalation: full synthesis ──────────────────────────────────
        items_block = "\n".join(
            f"{i+1}. [Source: {item['source_name']}] {item['topic']}"
            for i, item in enumerate(cluster_items)
        )

        prompt = f"""You are the senior editor for Blank, a culture intelligence platform.

The following {len(cluster_items)} signals from the live feed all cover the same story: "{cluster['topic']}"

{items_block}

This story earned its place in the main feed through the weight of coverage — multiple independent signals are all pointing at the same event simultaneously.

Some signals may be bare trending topic names (e.g. a player's name, a team name) rather than full articles — this is intentional. Trending names surface in real time, often before any article exists. Use your knowledge of these people, teams, and the cultural context to confidently infer what is happening and write an accurate, specific "Why it matters." The convergence of these signals is itself strong evidence that something significant just occurred. Write like a smart editor who caught the story early — not like someone waiting for more information.

WHY IT MATTERS: 2–3 sentences. Be specific: who, what, why it matters culturally right now. Editorial voice — a take, not a summary.

HOOK: A punchy 2–3 line carousel headline, separated by /. Write like a text to a friend: fragments OK, each line a distinct beat. 7 words or fewer per line. Punctuate naturally.

Respond with JSON only:
{{"title": "<concise headline>", "why": "<2-3 sentence editorial context>", "hook": "<2-3 lines separated by />"}}"""

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw)
        except Exception as e:
            print(f"   ⚠️  Cluster Sonnet escalation failed: {e}")
            return

        title = result.get("title", cluster["topic"])
        why   = result.get("why", "").strip()
        hook  = result.get("hook", "").strip()

        primary   = max(cluster_items, key=lambda x: x.get("haiku_score", 0))
        n_src     = len(cluster_items)
        src_label = f"{primary['source_name']} + {n_src - 1} more" if n_src > 1 else primary["source_name"]

        timestamp = now.strftime("%Y-%m-%d-%H%M")
        header    = f"# Live Cluster — {display_time}\n\n"
        header   += f"> **Source:** Live feed — {n_src}-signal cluster\n"
        header   += f"> **Picks surfaced:** 1\n\n---\n\n"

        block  = f"## Pick #1 — Score: 8/10\n\n"
        block += f"**{title}**\n"
        block += f"*{src_label}*\n"
        block += f"[Read the full article →]({primary['search_url']})\n"
        block += "**Live Pick:** true\n"
        if why:
            block += f"\n**Why it matters:**\n{why}\n"
        if hook:
            block += f"\n**Hook:**\n{hook}\n"
        block += "\n---\n"

        os.makedirs("picks", exist_ok=True)
        filepath = f"picks/picks-{timestamp}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header + block)

        cluster["picks_file"] = filepath
        cluster["why_text"]   = why
        print(f"   🔗 Cluster escalated ({n_src} signals) → {filepath}: {title[:60]}")
        send_breaking_push([{
            "topic": title,
            "context": why[:120],
            "search_url": FEED_URL,
            "source_name": "Live Cluster",
        }])


def send_breaking_push(new_items: list[dict]) -> None:
    """Send a Web Push notification for new breaking items."""
    private_key = os.environ.get("VAPID_PRIVATE_KEY", "")
    public_key  = os.environ.get("VAPID_PUBLIC_KEY", "")
    if not private_key or not public_key:
        print("   ⚠️  VAPID keys not set — skipping push notification.")
        return

    subs_file = "subscriptions.json"
    if not os.path.exists(subs_file):
        print("   ℹ️  No subscriptions.json — skipping push.")
        return
    try:
        with open(subs_file, encoding="utf-8") as f:
            subscriptions = json.load(f)
    except Exception:
        print("   ⚠️  Could not load subscriptions.json — skipping push.")
        return
    if not subscriptions:
        print("   ℹ️  No subscribers — skipping push.")
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        print("   ⚠️  pywebpush not installed — skipping push.")
        return

    # One notification summarising what broke
    lead = new_items[0]
    body = lead.get("context") or lead["topic"]
    if len(new_items) > 1:
        body += f" + {len(new_items) - 1} more"

    payload = json.dumps({
        "title": "Breaking",
        "body":  body,
        "tag":   "breaking-news",
        "url":   FEED_URL,
    })

    expired, sent = [], 0
    for i, sub in enumerate(subscriptions):
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=VAPID_CLAIMS,
            )
            sent += 1
        except WebPushException as e:
            status = e.response.status_code if e.response else None
            if status in (404, 410):
                expired.append(i)
            else:
                print(f"   ⚠️  Push failed for subscriber {i+1}: {e}")
        except Exception as e:
            print(f"   ⚠️  Push error for subscriber {i+1}: {e}")

    if expired:
        for idx in reversed(expired):
            subscriptions.pop(idx)
        with open(subs_file, "w", encoding="utf-8") as f:
            json.dump(subscriptions, f, indent=2, ensure_ascii=False)
            f.write("\n")

    print(f"   🔔 Push sent to {sent} subscriber(s). Body: \"{body}\"")


# ── Social trends cache (written by daily_curator.py 3×/day via Apify) ───────

def load_social_trends() -> dict:
    """
    Load the social trends cache written by daily_curator.py.
    Returns topic lists plus engagement metadata (ranks, search volumes).
    """
    empty = {"x": [], "google": [], "youtube": [], "tiktok": [], "x_ranks": {}, "google_engagement": {}}
    if not os.path.exists(SOCIAL_TRENDS_PATH):
        return empty
    try:
        with open(SOCIAL_TRENDS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {
            "x":                 data.get("x", []),
            "google":            data.get("google", []),
            "youtube":           data.get("youtube", []),
            "tiktok":            data.get("tiktok", []),
            "reddit_hot":        data.get("reddit_hot", []),
            "x_ranks":           data.get("x_ranks", {}),
            "google_engagement": data.get("google_engagement", {}),
        }
    except Exception as e:
        print(f"   ⚠️  Could not load social_trends.json: {e}")
        return empty


# ── Google Trends live refresh (free, no Apify) ──────────────────────────────

def refresh_google_trends(trends: dict) -> dict:
    """
    Top up the google field in trends if the cached data is older than
    GOOGLE_TRENDS_MAX_AGE minutes. Hits the unofficial daily trends endpoint
    (free, no Apify). Falls back silently to the cached data on any failure.
    Also writes the refreshed data back to social_trends.json so subsequent
    runs within the same window skip the fetch.
    """
    try:
        if os.path.exists(SOCIAL_TRENDS_PATH):
            with open(SOCIAL_TRENDS_PATH, encoding="utf-8") as f:
                cached = json.load(f)
            # Use google_fetched_at (independent of Apify's global fetched_at timestamp)
            google_fetched_at = cached.get("google_fetched_at")
            if google_fetched_at:
                age_minutes = (
                    datetime.now(tz=timezone.utc)
                    - datetime.fromisoformat(google_fetched_at)
                ).total_seconds() / 60
                if age_minutes < GOOGLE_TRENDS_MAX_AGE:
                    return trends  # still fresh
    except Exception:
        pass  # can't determine age — attempt a refresh anyway

    try:
        resp = requests.get(
            GOOGLE_TRENDS_URL,
            headers={**_HEADERS, "Accept-Language": "en-US,en;q=0.9"},
            timeout=10,
        )
        resp.raise_for_status()
        # Parse RSS/XML — more reliable in GitHub Actions than the JSON endpoint
        GT_NS = "https://trends.google.com/trends/trendingsearches/daily"
        root = ET.fromstring(resp.content)
        topics = []
        engagement = {}
        for item in root.findall("./channel/item"):
            title_el   = item.find("title")
            traffic_el = item.find(f"{{{GT_NS}}}approx_traffic")
            if title_el is not None and title_el.text:
                query = title_el.text.strip()
                topics.append(query)
                if traffic_el is not None and traffic_el.text:
                    engagement[query] = traffic_el.text.strip()
        if topics:
            trends = {**trends, "google": topics, "google_engagement": engagement}
            try:
                existing = {}
                if os.path.exists(SOCIAL_TRENDS_PATH):
                    with open(SOCIAL_TRENDS_PATH, encoding="utf-8") as f:
                        existing = json.load(f)
                existing["google"] = topics
                existing["google_engagement"] = engagement
                existing["google_fetched_at"] = datetime.now(tz=timezone.utc).isoformat()
                with open(SOCIAL_TRENDS_PATH, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
            print(f"   🔍 Google Trends refreshed: {len(topics)} topics")
    except Exception as e:
        print(f"   ⚠️  Google Trends refresh failed ({e}) — using cached data")

    return trends


# ── X (Twitter) trending live refresh (trends24.in, free, no auth) ──────────

def fetch_x_trending_live(trends: dict) -> dict:
    """
    Refresh X (Twitter) trending topics from trends24.in every X_TRENDS_MAX_AGE minutes.
    Free, no API key or auth required. Falls back to cached data on any failure.
    Writes refreshed topics back to social_trends.json so subsequent runs skip the fetch.
    """
    try:
        if os.path.exists(SOCIAL_TRENDS_PATH):
            with open(SOCIAL_TRENDS_PATH, encoding="utf-8") as f:
                cached = json.load(f)
            x_fetched_at = cached.get("x_fetched_at")
            if x_fetched_at:
                age_minutes = (
                    datetime.now(tz=timezone.utc)
                    - datetime.fromisoformat(x_fetched_at)
                ).total_seconds() / 60
                if age_minutes < X_TRENDS_MAX_AGE:
                    return trends  # still fresh
    except Exception:
        pass

    try:
        import re
        resp = requests.get(
            X_TRENDS_URL,
            headers={**_HEADERS, "Accept-Language": "en-US,en;q=0.9"},
            timeout=10,
        )
        resp.raise_for_status()
        # trends24 renders links like: href="/united-states/#topic-name">Topic Name</a>
        raw = re.findall(r'href="/united-states/#[^"]*">([^<]+)</a>', resp.text)
        seen = set()
        topics = []
        for t in raw:
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                topics.append(t)
        if topics:
            top30 = topics[:30]
            # Rank = 1-indexed position on the trending list
            ranks = {t: i + 1 for i, t in enumerate(top30)}
            trends = {**trends, "x": top30, "x_ranks": ranks}
            try:
                existing = {}
                if os.path.exists(SOCIAL_TRENDS_PATH):
                    with open(SOCIAL_TRENDS_PATH, encoding="utf-8") as f:
                        existing = json.load(f)
                existing["x"] = top30
                existing["x_ranks"] = ranks
                existing["x_fetched_at"] = datetime.now(tz=timezone.utc).isoformat()
                with open(SOCIAL_TRENDS_PATH, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
            print(f"   🐦 X Trending refreshed (trends24.in): {len(top30)} topics")
        else:
            print(f"   ⚠️  X Trending: no topics parsed from trends24.in — using cached data")
    except Exception as e:
        print(f"   ⚠️  Could not refresh X trending ({e}) — using cached data")

    return trends


# ── Source: Reddit hot posts for key culture subreddits (direct API) ─────────

CULTURE_SUBREDDITS = [
    "popculturechat",
    "music",
    "movies",
    "hiphopheads",
    "streetwear",
    "sneakers",
    "nba",
    "soccer",
]

def fetch_reddit_culture_hot(known_set: set[str], now_iso: str) -> list[dict]:
    """
    Fetch hot posts from key culture subreddits via Reddit's public JSON API.
    Bypasses the RSS publication-time window so posts surface when they're
    actually hot, not just when they were first published.
    """
    new_items = []
    now_ts = datetime.now(tz=timezone.utc).timestamp()

    for sub in CULTURE_SUBREDDITS:
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit=10",
                headers=_REDDIT_HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
        except Exception as e:
            print(f"      ⚠️  Could not fetch r/{sub}: {e}")
            continue

        for child in posts:
            post         = child.get("data", {})
            post_id      = post.get("id", "")
            title        = (post.get("title") or "").strip()
            score        = post.get("score", 0)
            num_comments = post.get("num_comments", 0)
            permalink    = post.get("permalink", "")

            if not post_id or not title:
                continue
            if score < REDDIT_SUB_MIN_SCORE:
                continue
            age_hours = (now_ts - post.get("created_utc", 0)) / 3600
            if age_hours > REDDIT_SUB_AGE_HOURS:
                continue

            aid = item_id(f"reddit_sub:{post_id}")
            if aid in known_set:
                continue

            eng_parts = [f"{score:,} upvotes"]
            if num_comments:
                eng_parts.append(f"{num_comments:,} comments")
            traffic = " · ".join(eng_parts)

            print(f"   🟠 [r/{sub}] {title[:70]} ({traffic})")
            new_items.append({
                "id":          aid,
                "topic":       title,
                "traffic":     traffic,
                "detected_at": now_iso,
                "search_url":  f"https://www.reddit.com{permalink}",
                "source_name": f"r/{sub}",
                "source_type": "reddit",
            })

    print(f"   🟠 Got {len(new_items)} new culture subreddit post(s).")
    return new_items


# ── Source: social trend topics as candidates (X, Google, TikTok) ────────────

def build_social_candidates(trends: dict, known_set: set[str], now_iso: str) -> list[dict]:
    """
    Convert cached social trend topics into scoreable candidates with search URLs.
    X topics → x.com/search, Google topics → google.com/search, TikTok → tiktok.com/search.
    """
    from urllib.parse import quote_plus
    candidates = []

    platform_cfg = [
        ("x",       "X (Twitter) Trending", lambda t: f"https://x.com/search?q={quote_plus(t)}&src=trend_click"),
        ("google",  "Google Trends",        lambda t: f"https://www.google.com/search?q={quote_plus(t)}"),
        ("tiktok",  "TikTok Trending",      lambda t: f"https://www.tiktok.com/search?q={quote_plus(t)}"),
    ]

    x_ranks           = trends.get("x_ranks", {})
    google_engagement = trends.get("google_engagement", {})

    for key, source_name, url_fn in platform_cfg:
        for i, topic in enumerate(trends.get(key, [])):
            if not topic:
                continue
            url = url_fn(topic)
            aid = item_id(url)
            if aid in known_set:
                continue

            if key == "x":
                rank    = x_ranks.get(topic, i + 1)
                traffic = f"#{rank} on X"
            elif key == "google":
                vol     = google_engagement.get(topic, "")
                traffic = f"{vol} searches" if vol else ""
            else:
                traffic = ""

            print(f"   📲 [{source_name}] {topic[:70]}" + (f" ({traffic})" if traffic else ""))
            candidates.append({
                "id":          aid,
                "topic":       topic,
                "traffic":     traffic,
                "detected_at": now_iso,
                "search_url":  url,
                "source_name": source_name,
                "source_type": key,
            })

    return candidates


# ── Source: your subscribed feeds (sources.json) ─────────────────────────────

def load_source_feeds() -> list[dict]:
    """Load enabled RSS feeds from sources.json."""
    try:
        with open(SOURCES_FILE, encoding="utf-8") as f:
            sources = json.load(f)
        feeds = [
            {"name": s["name"], "url": s["rss"]}
            for s in sources
            if s.get("enabled", True) and s.get("rss")
        ]
        print(f"      Loaded {len(feeds)} feeds from {SOURCES_FILE}")
        return feeds
    except Exception as e:
        print(f"      ⚠️  Could not load {SOURCES_FILE}: {e}")
        return []


def _parse_pubdate(text: str) -> datetime | None:
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def fetch_feed_articles(feed: dict, window_minutes: int) -> list[dict]:
    try:
        resp = requests.get(feed["url"], headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"      ⚠️  Could not fetch {feed['name']}: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"      ⚠️  XML parse error from {feed['name']}: {e}")
        print(f"         Response snippet: {resp.text[:200]}")
        return []

    cutoff   = datetime.now(tz=timezone.utc) - timedelta(minutes=window_minutes)
    articles = []

    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el  = item.find("link")
        guid_el  = item.find("guid")
        pub_el   = item.find("pubDate")

        title = (title_el.text or "").strip() if title_el is not None else ""
        link  = (link_el.text  or "").strip() if link_el  is not None else ""
        if not link and guid_el is not None:
            link = (guid_el.text or "").strip()
        pub_dt = _parse_pubdate(pub_el.text if pub_el is not None else "")

        if not title or not link:
            continue
        if pub_dt and pub_dt < cutoff:
            continue

        articles.append({
            "title":       title,
            "link":        link,
            "source_name": feed["name"],
        })

    return articles


# ── Source: Reddit hot posts ──────────────────────────────────────────────────

REDDIT_MIN_SCORE    = 150   # upvote threshold to surface a hot post
REDDIT_HOT_LIMIT    = 20    # posts per subreddit

_REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BreakingNewsBot/1.0; +https://boymeetsblank.github.io/daily-curator/)"
}


def _extract_subreddit(rss_url: str) -> str | None:
    """Extract subreddit name from a reddit.com/r/<sub>... URL."""
    import re
    m = re.search(r"reddit\.com/r/([^/?#]+)", rss_url, re.IGNORECASE)
    return m.group(1) if m else None


def fetch_reddit_hot_posts(known_set: set[str], now_iso: str) -> list[dict]:
    """
    Fetch hot posts from each Reddit subreddit in sources.json.
    Returns raw candidates (not in known_set, score >= REDDIT_MIN_SCORE).
    Enrichment/filtering is handled by filter_and_enrich_items().
    """
    try:
        with open(SOURCES_FILE, encoding="utf-8") as f:
            sources = json.load(f)
    except Exception as e:
        print(f"      ⚠️  Could not load {SOURCES_FILE} for Reddit: {e}")
        return []

    subreddits = []
    for s in sources:
        if not s.get("enabled", True):
            continue
        rss = s.get("rss", "")
        sub = _extract_subreddit(rss)
        if sub:
            subreddits.append(sub)

    if not subreddits:
        return []

    print(f"\n   🔴 Polling {len(subreddits)} Reddit subreddit(s) for hot posts...")
    new_items = []

    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit={REDDIT_HOT_LIMIT}"
        try:
            resp = requests.get(url, headers=_REDDIT_HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"      ⚠️  Could not fetch r/{sub}: {e}")
            continue

        posts = data.get("data", {}).get("children", [])
        for child in posts:
            post = child.get("data", {})
            post_id      = post.get("id", "")
            title        = (post.get("title") or "").strip()
            score        = post.get("score", 0)
            num_comments = post.get("num_comments", 0)
            permalink    = post.get("permalink", "")
            url_dest     = post.get("url") or f"https://www.reddit.com{permalink}"

            if not post_id or not title:
                continue
            if score < REDDIT_MIN_SCORE:
                continue

            created_utc = post.get("created_utc", 0)
            post_age_hours = (datetime.now(tz=timezone.utc).timestamp() - created_utc) / 3600
            if post_age_hours > 6:
                continue  # skip posts older than 6 hours — live feed needs fresh content

            aid = item_id(f"reddit:{post_id}")
            if aid in known_set:
                continue

            eng_parts = [f"{score:,} upvotes"]
            if num_comments:
                eng_parts.append(f"{num_comments:,} comments")
            traffic = " · ".join(eng_parts)

            print(f"   🔴 [r/{sub}] {title[:70]} ({traffic})")
            new_items.append({
                "id":          aid,
                "topic":       title,
                "traffic":     traffic,
                "detected_at": now_iso,
                "search_url":  url_dest,
                "source_name": f"r/{sub}",
                "source_type": "reddit",
            })

    return new_items


def fetch_reddit_all_hot(known_set: set[str], now_iso: str) -> list[dict]:
    """
    Fetch hot posts from Reddit r/all — the internet's broadest real-time signal.
    Uses a higher upvote threshold (REDDIT_ALL_MIN_SCORE) than subscribed subreddits
    to ensure only genuinely viral posts enter the clustering pipeline.
    """
    print(f"\n   🟠 Fetching Reddit r/all hot posts...")
    new_items = []
    try:
        resp = requests.get(
            f"https://www.reddit.com/r/all/hot.json?limit=25",
            headers=_REDDIT_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        posts = resp.json().get("data", {}).get("children", [])
    except Exception as e:
        print(f"      ⚠️  Could not fetch r/all: {e}")
        return []

    for child in posts:
        post        = child.get("data", {})
        post_id     = post.get("id", "")
        title       = (post.get("title") or "").strip()
        score       = post.get("score", 0)
        num_comments = post.get("num_comments", 0)
        permalink   = post.get("permalink", "")
        subreddit   = post.get("subreddit_name_prefixed") or post.get("subreddit") or "r/all"

        if not post_id or not title:
            continue
        if score < REDDIT_ALL_MIN_SCORE:
            continue

        created_utc = post.get("created_utc", 0)
        post_age_hours = (datetime.now(tz=timezone.utc).timestamp() - created_utc) / 3600
        if post_age_hours > REDDIT_SUB_AGE_HOURS:
            continue

        aid = item_id(f"reddit_all:{post_id}")
        if aid in known_set:
            continue

        eng_parts = [f"{score:,} upvotes"]
        if num_comments:
            eng_parts.append(f"{num_comments:,} comments")
        traffic = " · ".join(eng_parts)

        print(f"   🟠 [r/all/{subreddit}] {title[:70]} ({traffic})")
        new_items.append({
            "id":          aid,
            "topic":       title,
            "traffic":     traffic,
            "detected_at": now_iso,
            "search_url":  f"https://www.reddit.com{permalink}",
            "source_name": f"Reddit r/all ({subreddit})",
            "source_type": "reddit",
        })

    print(f"   🟠 Got {len(new_items)} new r/all post(s).")
    return new_items


# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"known_ids": [], "failed_ids": {}, "live_clusters": {}, "last_checked": None}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
        # Backfill: old state files used known_wire_ids
        if "known_ids" not in state:
            state["known_ids"] = state.get("known_wire_ids", [])
        # Prune failed_ids older than FAILED_IDS_TTL_HOURS so they re-enter the pipeline
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=FAILED_IDS_TTL_HOURS)
        raw_failed = state.get("failed_ids", {})
        state["failed_ids"] = {
            k: v for k, v in raw_failed.items()
            if datetime.fromisoformat(v) > cutoff
        }
        # Prune clusters older than CLUSTER_TTL_HOURS
        cluster_cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=CLUSTER_TTL_HOURS)
        raw_clusters = state.get("live_clusters", {})
        state["live_clusters"] = {
            cid: c for cid, c in raw_clusters.items()
            if datetime.fromisoformat(c["created_at"]) > cluster_cutoff
        }
        return state
    except Exception:
        return {"known_ids": [], "failed_ids": {}, "live_clusters": {}, "last_checked": None}


def save_state(known_ids: list[str], failed_ids: dict[str, str], live_clusters: dict) -> None:
    state = {
        "known_ids":     known_ids[-MAX_KNOWN_IDS:],
        "failed_ids":    failed_ids,
        "live_clusters": live_clusters,
        "last_checked":  datetime.now(tz=timezone.utc).isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def load_breaking_news() -> list[dict]:
    if not os.path.exists(OUTPUT_FILE):
        return []
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            return json.load(f).get("items", [])
    except Exception:
        return []


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n⚡ Breaking News Monitor")
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    state        = load_state()
    known_ids    = list(state.get("known_ids", []))
    failed_ids   = dict(state.get("failed_ids", {}))
    live_clusters = dict(state.get("live_clusters", {}))
    known_set    = set(known_ids) | set(failed_ids.keys())

    # Load social trends, then live-refresh X (every 10 min) and Google (every 10 min).
    # TikTok/YouTube stay on the 3×/day Apify schedule.
    trends = load_social_trends()
    trends = refresh_google_trends(trends)
    trends = fetch_x_trending_live(trends)
    if any(trends.values()):
        total = sum(len(v) for v in trends.values())
        print(f"\n   📲 Loaded social trends: {total} topics across X, Google, YouTube, TikTok")
    else:
        print("\n   📲 No social_trends.json found — scoring without trend context")

    candidates = []

    print("\n   📰 Polling your sources...")
    for feed in load_source_feeds():
        for art in fetch_feed_articles(feed, FEED_WINDOW_MINUTES):
            aid = item_id(art["link"])
            if aid not in known_set:
                print(f"   📌 [{art['source_name']}] {art['title'][:70]}")
                candidates.append({
                    "id":          aid,
                    "topic":       art["title"],
                    "traffic":     "",
                    "detected_at": now_iso,
                    "search_url":  art["link"],
                    "source_name": art["source_name"],
                    "source_type": "feed",
                })

    reddit_candidates = fetch_reddit_hot_posts(known_set, now_iso)
    candidates.extend(reddit_candidates)

    reddit_all_candidates = fetch_reddit_all_hot(known_set, now_iso)
    candidates.extend(reddit_all_candidates)

    reddit_culture_candidates = fetch_reddit_culture_hot(known_set, now_iso)
    candidates.extend(reddit_culture_candidates)

    social_candidates = build_social_candidates(trends, known_set, now_iso)
    candidates.extend(social_candidates)

    # Add all candidate IDs to known_set now to prevent same-run re-evaluation.
    # After scoring we route: passed → known_ids (permanent), failed → failed_ids (4h TTL).
    for c in candidates:
        known_set.add(c["id"])

    # Cap candidates per source before scoring to avoid wasting API calls on
    # burst-publishing sources and to encourage diversity in what gets evaluated.
    _source_counts: dict[str, int] = defaultdict(int)
    capped: list[dict] = []
    for c in candidates:
        if _source_counts[c["source_name"]] < MAX_LIVE_PER_SOURCE:
            capped.append(c)
            _source_counts[c["source_name"]] += 1
    if len(capped) < len(candidates):
        print(f"   ✂️  Per-source cap: {len(candidates)} → {len(capped)} candidates")
    candidates = capped

    if candidates:
        print(f"\n   🔍 Running quality gate on {len(candidates)} candidate(s)...")
        new_items = filter_and_enrich_items(candidates, trends, live_clusters)
    else:
        new_items = []

    # ── Cluster new items with existing live feed ──────────────────────────────
    if new_items:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        print(f"\n   🧩 Clustering {len(new_items)} new item(s) against {len(live_clusters)} existing cluster(s)...")
        live_clusters = cluster_new_items(new_items, live_clusters, api_key)

        # Load current live feed items so we can gather full cluster context for escalation
        existing_for_cluster = load_breaking_news()
        existing_by_id = {item["id"]: item for item in existing_for_cluster}

        for cid, cluster in live_clusters.items():
            item_count = len(cluster["item_ids"])
            last_size  = cluster.get("last_escalated_size", 0)

            should_escalate = (
                (last_size == 0 and item_count >= CLUSTER_THRESHOLD) or
                (last_size > 0 and (item_count - last_size) >= CLUSTER_THRESHOLD)
            )

            if should_escalate:
                # Gather all cluster items from new items + existing live feed
                new_by_id = {item["id"]: item for item in new_items}
                cluster_items = []
                for iid in cluster["item_ids"]:
                    if iid in new_by_id:
                        cluster_items.append(new_by_id[iid])
                    elif iid in existing_by_id:
                        cluster_items.append(existing_by_id[iid])

                # On re-escalation, identify which items are new since last escalation
                last_item_ids = set(cluster.get("last_escalated_item_ids", []))
                new_items_only = [item for item in cluster_items if item["id"] not in last_item_ids]
                is_reescalation = last_size > 0

                if cluster_items:
                    verb = "updating" if is_reescalation else "escalating"
                    print(f"\n   🔗 Cluster '{cluster['topic']}' reached {item_count} signals — {verb} to Sonnet...")
                    escalate_cluster_to_sonnet(
                        cluster,
                        cluster_items,
                        new_items_only=new_items_only if is_reescalation else None,
                    )
                    cluster["last_escalated_size"]    = item_count
                    cluster["last_escalated_at"]      = now_iso
                    cluster["last_escalated_item_ids"] = cluster["item_ids"].copy()

    # ── Individual item escalation: 9+ haiku score → Sonnet + push ───────────
    escalate_items = [item for item in new_items if item.get("haiku_score", 0) >= 9]
    if escalate_items:
        print(f"\n   🚀 Escalating {len(escalate_items)} item(s) to Sonnet for main feed...")
        escalate_to_sonnet(escalate_items)

    print(f"\n   {'🔴' if new_items else '✅'} {len(new_items)} new item(s) this check ({len(escalate_items)} individually escalated).")

    # Route candidates: passed → known_ids (permanent), failed → failed_ids (4h TTL)
    passed_ids = {item["id"] for item in new_items}
    for c in candidates:
        if c["id"] in passed_ids:
            known_ids.append(c["id"])
        else:
            failed_ids[c["id"]] = now_iso

    # ── Merge + prune ─────────────────────────────────────────────────────────
    existing     = load_breaking_news()
    cutoff       = datetime.now(tz=timezone.utc) - timedelta(hours=BREAKING_NEWS_TTL_HOURS)
    existing_ids = {item["id"] for item in existing}

    kept = [
        item for item in existing
        if datetime.fromisoformat(item["detected_at"]) > cutoff
    ]

    # Count items per source detected within the rolling cap window.
    # Items older than SOURCE_CAP_WINDOW_HOURS don't block new ones from the same source.
    cap_cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=SOURCE_CAP_WINDOW_HOURS)
    _kept_source_counts: dict[str, int] = defaultdict(int)
    for item in kept:
        if datetime.fromisoformat(item["detected_at"]) > cap_cutoff:
            _kept_source_counts[item["source_name"]] += 1

    for item in new_items:
        if item["id"] not in existing_ids:
            if _kept_source_counts[item["source_name"]] < MAX_LIVE_PER_SOURCE:
                kept.append(item)
                _kept_source_counts[item["source_name"]] += 1

    # Live feed is purely reverse-chronological — no score-based pinning here.
    # Pinning by score is handled in the main feed only.
    kept = sorted(kept, key=lambda x: x.get("detected_at", ""), reverse=True)[:MAX_FEED_SIZE]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": kept, "last_checked": now_iso}, f, indent=2, ensure_ascii=False)
    print(f"   📝 {OUTPUT_FILE}: {len(kept)} active item(s)")

    # ── Push notification — only for 9+ escalated items ────────────────────────
    if escalate_items:
        send_breaking_push(escalate_items)

    # ── Persist state ─────────────────────────────────────────────────────────
    save_state(known_ids, failed_ids, live_clusters)
    print(f"   💾 State saved — {len(known_ids)} known, {len(failed_ids)} on 4h suppression\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n❌ Breaking news check crashed: {e}")
        traceback.print_exc()
        raise
