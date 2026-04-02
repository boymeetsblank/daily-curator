"""
breaking_news_check.py — Breaking News Velocity Monitor

Fetches Google Trends RSS every 15 minutes (via GitHub Actions cron).
Detects velocity spikes: topics newly entering the top 5 that were not
in the previous check's known set. Qualifying topics bypass Claude
scoring — velocity is the qualification.

Writes breaking_news.json (deployed to GitHub Pages by deploy-pages.yml)
and breaking_news_state.json (persisted in the repo to track known topics).
"""

import os
import re
import json
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

TRENDS_RSS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
STATE_FILE    = "breaking_news_state.json"
OUTPUT_FILE   = "breaking_news.json"

# Keep breaking news visible for this many hours
BREAKING_NEWS_TTL_HOURS = 6

# A topic must be NEW (not in known_topics from last check) to qualify as a spike
SPIKE_TOP_N = 5   # only topics in the top N are eligible


def fetch_trending_topics() -> list[dict]:
    """Fetch current top trending topics from Google Trends RSS."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BreakingNewsBot/1.0)"}
    try:
        resp = requests.get(TRENDS_RSS_URL, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Could not fetch Google Trends RSS: {e}")
        return []

    root = ET.fromstring(resp.content)
    ns   = {"ht": "https://trends.google.com/trends/trendingsearches/daily"}

    topics = []
    for item in root.findall(".//item"):
        title_el   = item.find("title")
        traffic_el = item.find("ht:approx_traffic", ns)
        pub_el     = item.find("pubDate")

        name    = (title_el.text or "").strip()   if title_el   is not None else ""
        traffic = (traffic_el.text or "").strip() if traffic_el is not None else ""
        pub     = (pub_el.text or "").strip()     if pub_el     is not None else ""

        if not name:
            continue
        topics.append({"name": name, "traffic": traffic, "pub": pub})

    return topics


def load_state() -> dict:
    """Load the last-check state (known topic names)."""
    if not os.path.exists(STATE_FILE):
        return {"known_topics": [], "last_checked": None}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"known_topics": [], "last_checked": None}


def save_state(known_topics: list[str]) -> None:
    state = {
        "known_topics": known_topics,
        "last_checked": datetime.now(tz=timezone.utc).isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_breaking_news() -> list[dict]:
    """Load existing breaking news items (to append / prune)."""
    if not os.path.exists(OUTPUT_FILE):
        return []
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("items", [])
    except Exception:
        return []


def topic_id(name: str) -> str:
    """Stable ID for a topic — first 12 chars of its MD5."""
    return hashlib.md5(name.lower().strip().encode()).hexdigest()[:12]


def main():
    print("\n⚡ Breaking News Monitor — checking Google Trends RSS...")

    current_topics = fetch_trending_topics()
    if not current_topics:
        print("   ⚠️  No topics fetched — exiting without changes.")
        return

    state         = load_state()
    known_set     = set(t.lower() for t in state.get("known_topics", []))
    top_topics    = current_topics[:SPIKE_TOP_N]

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    spikes  = []

    for topic in top_topics:
        name = topic["name"]
        if name.lower() not in known_set:
            tid = topic_id(name)
            search_url = f"https://www.google.com/search?q={requests.utils.quote(name)}"
            spikes.append({
                "id":          tid,
                "topic":       name,
                "traffic":     topic["traffic"],
                "detected_at": now_iso,
                "search_url":  search_url,
            })
            print(f"   🔥 Velocity spike: {name!r} ({topic['traffic']})")

    if not spikes:
        print(f"   ✅ No new spikes — all top-{SPIKE_TOP_N} topics already known.")
    else:
        print(f"   ✅ {len(spikes)} spike(s) detected.")

    # Merge with existing breaking news, prune older than TTL
    existing   = load_breaking_news()
    cutoff     = datetime.now(tz=timezone.utc) - timedelta(hours=BREAKING_NEWS_TTL_HOURS)
    existing_ids = {item["id"] for item in existing}

    # Prune expired items
    kept = [
        item for item in existing
        if datetime.fromisoformat(item["detected_at"]) > cutoff
    ]

    # Add new spikes that aren't already in the list
    for spike in spikes:
        if spike["id"] not in existing_ids:
            kept.insert(0, spike)

    output = {
        "items":        kept,
        "last_checked": now_iso,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    if spikes:
        print(f"   📝 Wrote {len(kept)} item(s) to {OUTPUT_FILE}")
    else:
        print(f"   📝 Updated last_checked in {OUTPUT_FILE} ({len(kept)} active items)")

    # Update state: all currently visible top topics are now "known"
    all_names = [t["name"] for t in current_topics]
    save_state(all_names)
    print(f"   💾 State updated — {len(all_names)} topics now known.")
    print()


if __name__ == "__main__":
    main()
