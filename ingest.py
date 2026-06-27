"""
ingest.py — RSS ingestion layer for the Blank continuous curation engine.

Polls active sources from the DB, normalizes feed entries, and writes
new items via db.py helpers. Dedup is automatic (content_hash + URL).

Does not touch daily_curator.py or any part of the existing pipeline.
"""

import os
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import quote_plus

import feedparser
import requests

import db

# User-Agent sent with every feed request. Reddit and some other hosts reject
# requests without a descriptive agent string.
USER_AGENT = "blank-engine/0.1 (personal feed reader)"

# Trends (Apify). Optional: if APIFY_API_TOKEN is unset, the trend stage is a
# graceful no-op so the engine still runs. Trends are throttled per source so we
# don't pay Apify on every 10-minute pipeline run (topics barely move that fast).
# 180 min (~8 refreshes/day across 2 sources) keeps estimated spend under the
# Apify free tier's $5/mo; hourly would overrun it (Google Trends is the driver).
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN")
TREND_REFRESH_MINUTES = 180

# Minimum seconds between consecutive Reddit RSS polls to avoid 429s.
# Non-Reddit sources are not delayed.
REDDIT_DELAY = 2.0

# Items older than this are skipped when a source is polled for the first time
BACKLOG_CUTOFF_HOURS = 48


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = _TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def _parse_date(entry) -> Optional[str]:
    """
    Extract a UTC ISO timestamp from a feedparser entry.
    Returns None if no date is present; caller falls back to fetched_at.
    """
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t is None:
        return None
    try:
        dt = datetime(*t[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core poll functions
# ---------------------------------------------------------------------------

def poll_source(source: dict, db_path: str = db.DB_PATH) -> dict:
    """
    Fetch and parse one RSS source, insert new items into the DB.

    source dict must have keys: id, url, name, last_polled_at (may be None).

    Returns:
        {"source_id": int, "new": int, "skipped": int, "errors": int}
    """
    source_id = source["id"]
    source_url = source["url"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=BACKLOG_CUTOFF_HOURS)

    new_count = 0
    skipped_count = 0
    error_count = 0

    try:
        feed = feedparser.parse(source_url, agent=USER_AGENT)
    except Exception as exc:
        print(f"  [ERROR] Failed to fetch {source_url}: {exc}")
        return {"source_id": source_id, "new": 0, "skipped": 0, "errors": 1}

    # Detect HTTP error responses (feedparser doesn't raise — it sets feed.status)
    http_status = getattr(feed, "status", None)
    if http_status and http_status >= 400:
        print(f"  [ERROR] HTTP {http_status} from {source_url}")
        return {"source_id": source_id, "new": 0, "skipped": 0, "errors": 1}

    if feed.bozo and not feed.entries:
        print(f"  [WARN] Malformed or empty feed: {source_url} ({feed.bozo_exception})")

    for entry in feed.entries:
        try:
            title = _strip_html(entry.get("title") or "").strip()
            if not title:
                skipped_count += 1
                continue

            # description: prefer summary, fall back to content[0], then empty
            raw_desc = (
                entry.get("summary")
                or (entry.get("content") or [{}])[0].get("value")
                or ""
            )
            description = _strip_html(raw_desc).strip() or None

            url = (entry.get("link") or "").strip()
            if not url:
                skipped_count += 1
                continue

            # Extract inline image: media:content → enclosure → media_thumbnail
            image_url = None
            for m in entry.get("media_content", []):
                u = (m.get("url") or "").strip()
                if u.startswith("http"):
                    image_url = u
                    break
            if not image_url:
                for enc in entry.get("enclosures", []):
                    u = (enc.get("url") or "").strip()
                    t = enc.get("type", "")
                    if u.startswith("http") and (t.startswith("image/") or not t):
                        image_url = u
                        break
            if not image_url:
                for thumb in entry.get("media_thumbnail", []):
                    u = (thumb.get("url") or "").strip()
                    if u.startswith("http"):
                        image_url = u
                        break

            published_at = _parse_date(entry)

            # When the feed provides no pubDate (common with Google News), treat
            # the item as published now so it passes the freshness check and
            # displays a sensible age ("hours ago") rather than a stale date.
            if published_at is None:
                published_at = datetime.now(timezone.utc).isoformat()

            # Skip entries older than BACKLOG_CUTOFF_HOURS on every poll
            try:
                pub_dt = datetime.fromisoformat(published_at)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    skipped_count += 1
                    continue
            except Exception:
                pass  # unparseable date — include it

            existing_items_before = _count_items(db_path)
            item_id = db.insert_item(
                source_id=source_id,
                url=url,
                title=title,
                description=description,
                image_url=image_url,
                published_at=published_at,
                raw_engagement={},
                db_path=db_path,
            )
            existing_items_after = _count_items(db_path)

            if existing_items_after > existing_items_before:
                new_count += 1
            else:
                skipped_count += 1

        except Exception as exc:
            print(f"  [ERROR] Entry processing failed ({source_url}): {exc}")
            error_count += 1

    return {
        "source_id": source_id,
        "new": new_count,
        "skipped": skipped_count,
        "errors": error_count,
    }


def _count_items(db_path: str) -> int:
    """Quick row count for new-vs-skip detection inside poll_source."""
    con = sqlite3.connect(db_path)
    try:
        return con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    finally:
        con.close()


def _update_last_polled(source_id: int, db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "UPDATE sources SET last_polled_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), source_id),
        )
        con.commit()
    finally:
        con.close()


def _fetch_og_image(url: str) -> Optional[str]:
    """
    Fetch a single article URL and extract its og:image meta tag.
    Returns the image URL string, or None if not found or on any error.
    Hard timeout of 5 seconds.
    """
    try:
        response = requests.get(
            url,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BlankEngine/1.0)"},
            allow_redirects=True,
        )
        if not response.ok:
            return None
        if "html" not in response.headers.get("content-type", ""):
            return None
        html = response.text[:50000]
        match = re.search(
            r'<meta[^>]+(?:'
            r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
            r'|content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
            r')',
            html, re.IGNORECASE
        )
        if match:
            return (match.group(1) or match.group(2)).strip() or None
        return None
    except Exception:
        return None


def enrich_og_images(db_path: str = db.DB_PATH) -> dict:
    """
    For items inserted in the last 15 minutes that have no image_url, fetch
    the article page and extract og:image as a fallback. Runs 10 concurrent
    workers with a 5-second per-request timeout.
    """
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT id, url FROM items "
            "WHERE image_url IS NULL AND fetched_at >= datetime('now', '-15 minutes')"
        ).fetchall()
    finally:
        con.close()

    if not rows:
        print("  No new items need OG enrichment.")
        return {"enriched": 0, "attempted": 0}

    print(f"  Fetching OG images for {len(rows)} items...")
    enriched = 0
    con = sqlite3.connect(db_path)
    try:
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_id = {
                executor.submit(_fetch_og_image, url): item_id
                for item_id, url in rows
            }
            for future in as_completed(future_to_id):
                item_id = future_to_id[future]
                og_url = future.result()
                if og_url:
                    con.execute(
                        "UPDATE items SET image_url = ? WHERE id = ?",
                        (og_url, item_id),
                    )
                    enriched += 1
        con.commit()
    finally:
        con.close()

    print(f"  Found OG images for {enriched}/{len(rows)} items.")
    return {"enriched": enriched, "attempted": len(rows)}


# ---------------------------------------------------------------------------
# Trends (X / Google via Apify)
# ---------------------------------------------------------------------------

def _run_apify_actor(actor_id: str, input_data: dict) -> list[dict]:
    """
    Start an Apify actor run, poll until it finishes (up to 60 seconds), then
    return the dataset items. Raises on HTTP error, actor failure, or timeout.
    """
    run_resp = requests.post(
        f"https://api.apify.com/v2/acts/{actor_id}/runs",
        json=input_data,
        params={"token": APIFY_API_TOKEN},
        timeout=30,
    )
    run_resp.raise_for_status()
    run_data = run_resp.json()["data"]
    run_id = run_data["id"]
    dataset_id = run_data["defaultDatasetId"]

    deadline = time.time() + 60
    while time.time() < deadline:
        status_resp = requests.get(
            f"https://api.apify.com/v2/acts/{actor_id}/runs/{run_id}",
            params={"token": APIFY_API_TOKEN},
            timeout=10,
        )
        status_resp.raise_for_status()
        status = status_resp.json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify actor run {status.lower()}")
        time.sleep(3)
    else:
        raise TimeoutError("Apify actor run did not finish within 60 seconds")

    items_resp = requests.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items",
        params={"token": APIFY_API_TOKEN},
        timeout=30,
    )
    items_resp.raise_for_status()
    return items_resp.json()


def _twitter_trend_topics() -> list[str]:
    """Top US trending topics from X (Twitter) via Apify, newest-rank first."""
    items = _run_apify_actor(
        "karamelo~twitter-trends-scraper",
        {"country": "2", "live": True},  # "2" = United States
    )
    topics = []
    for item in items[:30]:
        name = (item.get("name") or item.get("trend") or
                item.get("title") or item.get("keyword") or "").strip()
        if name:
            topics.append(name)
    return topics


def _google_trend_topics() -> list[str]:
    """Top US trending search terms from Google Trends via Apify."""
    items = _run_apify_actor(
        "apify~google-trends-scraper",
        {"searchTerms": [""], "geo": "US"},
    )
    topics = []
    for item in items[:30]:
        name = (item.get("title") or item.get("keyword") or item.get("query") or
                item.get("topic") or item.get("name") or "").strip()
        if name:
            topics.append(name)
    return topics


# (source name, source type, clickable-search-URL template, topic fetcher)
_TREND_FETCHERS = [
    ("X (Twitter) Trending", "trend", "https://x.com/search?q={q}", _twitter_trend_topics),
    ("Google Trends",        "trend", "https://www.google.com/search?q={q}", _google_trend_topics),
]


def _source_last_polled(source_id: int, db_path: str) -> Optional[datetime]:
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT last_polled_at FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        return None
    try:
        dt = datetime.fromisoformat(row[0])
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def fetch_trends(db_path: str = db.DB_PATH) -> dict:
    """
    Fetch trending topics from X and Google (via Apify) and insert them as
    items, so they flow through the same triage -> score -> rank pipeline as
    articles. Each trend source is throttled to TREND_REFRESH_MINUTES so we
    don't pay Apify on every 10-minute run.

    Each topic becomes an item with a clickable search URL and a date-stamped
    description, so the same topic re-surfaces at most once per day (the date
    makes the dedup hash and URL unique per day) and won't re-score within a day.

    No-op (returns zeros) if APIFY_API_TOKEN is unset.

    Returns {"fetched": int, "sources_fetched": int, "throttled": int}.
    """
    if not APIFY_API_TOKEN:
        print("  APIFY_API_TOKEN not set — skipping trends.")
        return {"fetched": 0, "sources_fetched": 0, "throttled": 0}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_new = 0
    sources_fetched = 0
    throttled = 0

    for name, stype, url_tmpl, fetcher in _TREND_FETCHERS:
        source_id = db.upsert_source(
            url=f"trend://{name}", name=name, source_type=stype, db_path=db_path
        )

        last = _source_last_polled(source_id, db_path)
        if last and (datetime.now(timezone.utc) - last) < timedelta(minutes=TREND_REFRESH_MINUTES):
            throttled += 1
            print(f"  [{name}] throttled (polled <{TREND_REFRESH_MINUTES}m ago) — skipping Apify.")
            continue

        try:
            topics = fetcher()
        except Exception as exc:
            print(f"  [WARN] {name} unavailable (continuing without): {exc}")
            continue

        sources_fetched += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        new_here = 0
        # Only insert the top-ranked topics: the per-source cap will process at
        # most PER_SOURCE_CAP, and they share a fetch timestamp, so trim to the
        # highest-ranked ones rather than letting the cap pick arbitrarily.
        for rank, topic in enumerate(topics[:db.PER_SOURCE_CAP], start=1):
            # date fragment keeps the URL/hash unique per day so a recurring
            # topic can resurface tomorrow but dedups within today
            item_url = url_tmpl.format(q=quote_plus(topic)) + f"#blank-{today}"
            description = f"Trending on {name} · {today}"
            before = _count_items(db_path)
            db.insert_item(
                source_id=source_id,
                url=item_url,
                title=topic,
                description=description,
                published_at=now_iso,
                raw_engagement={"trend_rank": rank},
                db_path=db_path,
            )
            if _count_items(db_path) > before:
                new_here += 1

        _update_last_polled(source_id, db_path)
        total_new += new_here
        print(f"  [{name}] {len(topics)} topics, {new_here} new.")

    return {"fetched": total_new, "sources_fetched": sources_fetched, "throttled": throttled}


def poll_all_active(db_path: str = db.DB_PATH) -> dict:
    """
    Poll every active source. Failures on individual sources are caught and logged;
    the run continues regardless. Updates last_polled_at after each source.

    Returns a summary dict:
        {"total_new": int, "total_skipped": int, "total_errors": int,
         "sources_polled": int, "sources_failed": int}
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        sources = con.execute(
            "SELECT id, url, name, type, last_polled_at FROM sources WHERE active = 1"
        ).fetchall()
        sources = [dict(s) for s in sources]
    finally:
        con.close()

    total_new = total_skipped = total_errors = 0
    sources_polled = 0
    sources_failed = 0
    last_reddit_at: float = 0.0  # timestamp of the last Reddit poll start

    for source in sources:
        is_reddit = "reddit.com" in source["url"]

        # Space out Reddit requests to avoid 429s. Non-Reddit sources are
        # unaffected. The delay applies before each Reddit poll (except the
        # very first one when last_reddit_at is 0).
        if is_reddit and last_reddit_at:
            since = time.time() - last_reddit_at
            if since < REDDIT_DELAY:
                time.sleep(REDDIT_DELAY - since)

        if is_reddit:
            last_reddit_at = time.time()

        print(f"Polling [{source['name']}] {source['url']}")
        try:
            result = poll_source(source, db_path=db_path)
            _update_last_polled(source["id"], db_path)
            total_new += result["new"]
            total_skipped += result["skipped"]
            total_errors += result["errors"]
            sources_polled += 1
            print(f"  -> new={result['new']}  skipped={result['skipped']}  errors={result['errors']}")
        except Exception as exc:
            print(f"  [FATAL] Source poll crashed ({source['url']}): {exc}")
            sources_failed += 1

    return {
        "total_new": total_new,
        "total_skipped": total_skipped,
        "total_errors": total_errors,
        "sources_polled": sources_polled,
        "sources_failed": sources_failed,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    db.init_db()
    print("DB initialized.\n")

    print("Starting poll...\n")
    t0 = time.time()
    summary = poll_all_active()
    elapsed = time.time() - t0

    print(f"\n-- Summary ----------------------------------")
    print(f"  Sources polled : {summary['sources_polled']}")
    print(f"  Sources failed : {summary['sources_failed']}")
    print(f"  New items      : {summary['total_new']}")
    print(f"  Skipped (dedup): {summary['total_skipped']}")
    print(f"  Entry errors   : {summary['total_errors']}")
    print(f"  Elapsed        : {elapsed:.1f}s")
    print()

    # Print 5 most recent items
    con = sqlite3.connect(db.DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT i.title, i.url, i.published_at, s.name AS source
        FROM items i
        JOIN sources s ON s.id = i.source_id
        ORDER BY i.fetched_at DESC
        LIMIT 5
        """
    ).fetchall()
    con.close()

    print(f"-- 5 Most Recent Items ----------------------")
    for i, row in enumerate(rows, 1):
        pub = row["published_at"] or "no date"
        print(f"\n  [{i}] {row['source']}")
        print(f"      {row['title'][:90]}")
        print(f"      {pub}")
        print(f"      {row['url'][:90]}")
