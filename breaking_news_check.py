"""
breaking_news_check.py — Breaking News Monitor

Polls your subscribed RSS feeds (sources.json) every 5 minutes for articles
published in the last 15 minutes. New items are enriched with a one-sentence
context via Claude Haiku, then written to breaking_news.json (deployed to
GitHub Pages). If new items are found, a Web Push notification is sent.

Note: Google Trends RSS was removed — Google deprecated the endpoint (404).
X trends are available via the 3x/day Apify runs in daily_curator.py.

Writes:
  breaking_news.json       — deployed to GitHub Pages for the frontend
  breaking_news_state.json — persists seen article IDs across runs
"""

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import requests

# ── Config ────────────────────────────────────────────────────────────────────

BREAKING_NEWS_TTL_HOURS = 6
FEED_WINDOW_MINUTES     = 30   # articles published this recently count as breaking
MAX_KNOWN_IDS           = 500  # cap state file growth

SOURCES_FILE = "sources.json"
STATE_FILE   = "breaking_news_state.json"
OUTPUT_FILE  = "breaking_news.json"

FEED_URL   = "https://boymeetsblank.github.io/daily-curator/"
VAPID_CLAIMS = {"sub": "mailto:mjaffry1@gmail.com"}

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BreakingNewsBot/1.0)"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def item_id(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()[:12]


def filter_and_enrich_items(candidates: list[dict]) -> list[dict]:
    """
    Batch quality gate + enrichment via Claude Haiku.

    Scores each candidate 1-10 for cultural significance. Items scoring >= 7
    are returned with a context line attached. Items scoring < 7 are silently
    dropped (their IDs are already in known_ids so they won't be re-evaluated).

    Falls back to surfacing all candidates without context if the API is
    unavailable or returns unparseable JSON.
    """
    if not candidates:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ⚠️  ANTHROPIC_API_KEY not set — surfacing all candidates unfiltered.")
        return candidates

    items_block = "\n".join(
        f"{i+1}. [Source: {c['source_name']}] {c['topic']}"
        for i, c in enumerate(candidates)
    )

    prompt = f"""You are an editorial filter for a culture intelligence platform focused on sneakers, fashion, music, sports, tech, and internet culture.

For each item below, score its cultural significance 1–10:
- 7–10: Genuinely newsworthy — a breaking story people will actually talk about, culturally significant, affects a broad audience
- 1–6: Noise — stock purchases/sales, corporate appointments, press releases, fund transactions, ticker symbol mentions, routine product reviews, niche B2B announcements

For items scoring >= 7 ONLY, also write a context line (12 words max, no punctuation at end, specific and editorial, not generic). For items scoring < 7, set context to null.

Respond with a JSON array only — one object per item, same order as input:
[{{"score": <int>, "context": "<string or null>"}}]

Items:
{items_block}"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60 * len(candidates),
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        results = json.loads(raw)
    except Exception as e:
        print(f"   ⚠️  Quality gate failed ({e}) — surfacing all candidates unfiltered.")
        return candidates

    if len(results) != len(candidates):
        print(f"   ⚠️  Quality gate returned {len(results)} results for {len(candidates)} candidates — surfacing all unfiltered.")
        return candidates

    passed = []
    for candidate, result in zip(candidates, results):
        score = result.get("score", 0)
        context = result.get("context")
        if score >= 7:
            if context:
                candidate["context"] = context.strip().rstrip(".")
            passed.append(candidate)
        else:
            print(f"   ✂️  Filtered (score {score}): {candidate['topic'][:70]}")

    print(f"   🎯 Quality gate: {len(passed)}/{len(candidates)} candidates passed.")
    return passed


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

REDDIT_MIN_SCORE    = 500   # upvote threshold to surface a hot post
REDDIT_HOT_LIMIT    = 10    # posts per subreddit

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
            post_id   = post.get("id", "")
            title     = (post.get("title") or "").strip()
            score     = post.get("score", 0)
            permalink = post.get("permalink", "")
            url_dest  = post.get("url") or f"https://www.reddit.com{permalink}"

            if not post_id or not title:
                continue
            if score < REDDIT_MIN_SCORE:
                continue

            aid = item_id(f"reddit:{post_id}")
            if aid in known_set:
                continue

            print(f"   🔴 [r/{sub}] {title[:70]} ({score:,} upvotes)")
            new_items.append({
                "id":          aid,
                "topic":       title,
                "traffic":     f"{score:,} upvotes",
                "detected_at": now_iso,
                "search_url":  url_dest,
                "source_name": f"r/{sub}",
                "source_type": "reddit",
            })

    return new_items


# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"known_ids": [], "last_checked": None}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
        # Backfill: old state files used known_wire_ids
        if "known_ids" not in state:
            state["known_ids"] = state.get("known_wire_ids", [])
        return state
    except Exception:
        return {"known_ids": [], "last_checked": None}


def save_state(known_ids: list[str]) -> None:
    state = {
        "known_ids":    known_ids[-MAX_KNOWN_IDS:],
        "last_checked": datetime.now(tz=timezone.utc).isoformat(),
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

    state     = load_state()
    known_ids = list(state.get("known_ids", []))
    known_set = set(known_ids)

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

    # Mark all candidates as seen regardless of whether they pass the quality gate,
    # so low-quality articles from noisy sources are never re-evaluated.
    for c in candidates:
        known_ids.append(c["id"])
        known_set.add(c["id"])

    if candidates:
        print(f"\n   🔍 Running quality gate on {len(candidates)} candidate(s)...")
        new_items = filter_and_enrich_items(candidates)
    else:
        new_items = []

    print(f"\n   {'🔴' if new_items else '✅'} {len(new_items)} new breaking item(s) this check.")

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

    # ── Push notification ──────────────────────────────────────────────────────
    if new_items:
        send_breaking_push(new_items)

    # ── Persist state ─────────────────────────────────────────────────────────
    save_state(known_ids)
    print(f"   💾 State saved — {len(known_ids)} IDs known\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n❌ Breaking news check crashed: {e}")
        traceback.print_exc()
        raise
