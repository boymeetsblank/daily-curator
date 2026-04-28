"""
breaking_news_check.py — Breaking News Monitor

Sources:
  1. Google Trends RSS — velocity spikes (topics newly entering the top N)
  2. Wire services (AP, BBC, NPR) — articles published in the last ~15 min

Runs every 5 minutes via GitHub Actions cron.
Each new item is optionally enriched with a one-sentence context via Claude Haiku
(requires ANTHROPIC_API_KEY; gracefully skipped if absent).

Writes:
  breaking_news.json       — deployed to GitHub Pages for the frontend
  breaking_news_state.json — persisted in repo to track what's already been seen
"""

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import requests

# ── Config ────────────────────────────────────────────────────────────────────

TRENDS_RSS_URL      = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
SPIKE_TOP_N         = 5
BREAKING_NEWS_TTL_HOURS = 6
WIRE_WINDOW_MINUTES = 15   # articles published this recently count as breaking
MAX_KNOWN_WIRE_IDS  = 500  # cap state file growth

WIRE_FEEDS = [
    {"name": "AP News",  "url": "https://feeds.apnews.com/rss/apf-topnews"},
    {"name": "BBC News", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    {"name": "NPR News", "url": "https://feeds.npr.org/1001/rss.xml"},
]

STATE_FILE  = "breaking_news_state.json"
OUTPUT_FILE = "breaking_news.json"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BreakingNewsBot/1.0)"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def topic_id(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()[:12]


def enrich_with_context(topic: str) -> str | None:
    """Call Claude Haiku for a ≤12-word cultural context line. Returns None if unavailable."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=40,
            messages=[{
                "role": "user",
                "content": (
                    f"In 12 words or fewer, why does '{topic}' matter right now culturally? "
                    "No punctuation at the end. Be specific and editorial, not generic."
                ),
            }],
        )
        return resp.content[0].text.strip().rstrip(".")
    except Exception as e:
        print(f"      ⚠️  Haiku enrichment failed for {topic!r}: {e}")
        return None


# ── Source 1: Google Trends ───────────────────────────────────────────────────

def fetch_trending_topics() -> list[dict]:
    try:
        resp = requests.get(TRENDS_RSS_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"      ❌ Could not fetch Google Trends RSS: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"      ❌ Google Trends XML parse error: {e}")
        print(f"         Response snippet: {resp.text[:300]}")
        return []

    ns     = {"ht": "https://trends.google.com/trends/trendingsearches/daily"}
    topics = []
    for item in root.findall(".//item"):
        title_el   = item.find("title")
        traffic_el = item.find("ht:approx_traffic", ns)
        name    = (title_el.text   or "").strip() if title_el   is not None else ""
        traffic = (traffic_el.text or "").strip() if traffic_el is not None else ""
        if name:
            topics.append({"name": name, "traffic": traffic})

    print(f"      Google Trends: {len(topics)} topics fetched")
    return topics


# ── Source 2: Wire services ───────────────────────────────────────────────────

def _parse_pubdate(text: str) -> datetime | None:
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def fetch_wire_articles(feed: dict, window_minutes: int) -> list[dict]:
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
        print(f"         Response snippet: {resp.text[:300]}")
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
        # BBC puts the article URL in guid when link is absent
        if not link and guid_el is not None:
            link = (guid_el.text or "").strip()
        pub_dt = _parse_pubdate(pub_el.text if pub_el is not None else "")

        if not title or not link:
            continue
        if pub_dt and pub_dt < cutoff:
            continue  # too old

        articles.append({
            "title":       title,
            "link":        link,
            "pub_iso":     pub_dt.isoformat() if pub_dt else "",
            "source_name": feed["name"],
        })

    print(f"      {feed['name']}: {len(articles)} recent article(s) in window")
    return articles


# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"known_topics": [], "known_wire_ids": [], "last_checked": None}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
        state.setdefault("known_wire_ids", [])  # backfill old state files
        return state
    except Exception:
        return {"known_topics": [], "known_wire_ids": [], "last_checked": None}


def save_state(known_topics: list[str], known_wire_ids: list[str]) -> None:
    state = {
        "known_topics":   known_topics,
        "known_wire_ids": known_wire_ids[-MAX_KNOWN_WIRE_IDS:],
        "last_checked":   datetime.now(tz=timezone.utc).isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


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

    state          = load_state()
    known_set      = {t.lower() for t in state.get("known_topics", [])}
    known_wire_ids = list(state.get("known_wire_ids", []))
    known_wire_set = set(known_wire_ids)

    new_items = []

    # ── Google Trends ─────────────────────────────────────────────────────────
    print("\n   📡 Google Trends...")
    current_topics = fetch_trending_topics()
    top_topics = current_topics[:SPIKE_TOP_N] if current_topics else []

    for topic in top_topics:
        name = topic["name"]
        if name.lower() not in known_set:
            print(f"   🔥 Trends spike: {name!r} ({topic['traffic']})")
            context = enrich_with_context(name)
            item = {
                "id":          topic_id(name),
                "topic":       name,
                "traffic":     topic["traffic"],
                "detected_at": now_iso,
                "search_url":  f"https://www.google.com/search?q={requests.utils.quote(name)}",
                "source_type": "trends",
            }
            if context:
                item["context"] = context
            new_items.append(item)

    # ── Wire services ─────────────────────────────────────────────────────────
    print("\n   📰 Wire services...")
    for feed in WIRE_FEEDS:
        articles = fetch_wire_articles(feed, WIRE_WINDOW_MINUTES)
        for art in articles:
            wid = topic_id(art["link"])
            if wid not in known_wire_set:
                print(f"   🔥 Wire [{art['source_name']}]: {art['title'][:70]}")
                context = enrich_with_context(art["title"])
                item = {
                    "id":          wid,
                    "topic":       art["title"],
                    "traffic":     "",
                    "detected_at": now_iso,
                    "search_url":  art["link"],
                    "source_name": art["source_name"],
                    "source_type": "wire",
                }
                if context:
                    item["context"] = context
                new_items.append(item)
                known_wire_ids.append(wid)
                known_wire_set.add(wid)

    print(f"\n   {'✅' if not new_items else '🔴'} {len(new_items)} new breaking item(s) this check.")

    # ── Merge + prune ─────────────────────────────────────────────────────────
    existing     = load_breaking_news()
    cutoff       = datetime.now(tz=timezone.utc) - timedelta(hours=BREAKING_NEWS_TTL_HOURS)
    existing_ids = {item["id"] for item in existing}

    kept = [
        item for item in existing
        if datetime.fromisoformat(item["detected_at"]) > cutoff
    ]
    for item in new_items:
        if item["id"] not in existing_ids:
            kept.insert(0, item)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": kept, "last_checked": now_iso}, f, indent=2, ensure_ascii=False)
    print(f"   📝 {OUTPUT_FILE}: {len(kept)} active item(s)")

    # ── Persist state ─────────────────────────────────────────────────────────
    all_trend_names = [t["name"] for t in current_topics] if current_topics else list(known_set)
    save_state(all_trend_names, known_wire_ids)
    print(f"   💾 State saved — {len(all_trend_names)} trend topics, {len(known_wire_ids)} wire IDs\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n❌ Breaking news check crashed: {e}")
        traceback.print_exc()
        raise
