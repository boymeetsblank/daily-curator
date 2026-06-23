"""
ingest.py — RSS ingestion layer for the Blank continuous curation engine.

Polls active sources from the DB, normalizes feed entries, and writes
new items via db.py helpers. Dedup is automatic (content_hash + URL).

Does not touch daily_curator.py or any part of the existing pipeline.
"""

import re
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import feedparser

import db

# ---------------------------------------------------------------------------
# Default seed sources — a mix of fast (news wire) and slower (culture/tech)
# ---------------------------------------------------------------------------

DEFAULT_SOURCES = [
    {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "name": "BBC News World",
        "type": "rss",
    },
    {
        "url": "https://techcrunch.com/feed/",
        "name": "TechCrunch",
        "type": "rss",
    },
    {
        "url": "https://www.reddit.com/r/popular.rss",
        "name": "Reddit r/popular",
        "type": "reddit",
    },
    {
        "url": "https://pitchfork.com/rss/news/feed.xml",
        "name": "Pitchfork News",
        "type": "rss",
    },
]

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
    first_poll = source["last_polled_at"] is None
    cutoff = datetime.now(timezone.utc) - timedelta(hours=BACKLOG_CUTOFF_HOURS)

    new_count = 0
    skipped_count = 0
    error_count = 0

    try:
        feed = feedparser.parse(source_url)
    except Exception as exc:
        print(f"  [ERROR] Failed to fetch {source_url}: {exc}")
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

            published_at = _parse_date(entry)

            # On first poll, skip entries older than BACKLOG_CUTOFF_HOURS
            if first_poll and published_at:
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

    for source in sources:
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
# Seed helper
# ---------------------------------------------------------------------------

def seed_sources(sources: list[dict] = DEFAULT_SOURCES, db_path: str = db.DB_PATH) -> None:
    """
    Add default RSS sources to the DB if not already present.
    Safe to call repeatedly — upsert_source is idempotent.
    """
    for s in sources:
        sid = db.upsert_source(
            url=s["url"],
            name=s["name"],
            source_type=s["type"],
            db_path=db_path,
        )
        print(f"  seeded source id={sid}  [{s['name']}]")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import sqlite3 as _sqlite3

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    db.init_db()
    print("DB initialized.\n")

    # Seed sources if the table is empty
    con = _sqlite3.connect(db.DB_PATH)
    source_count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    con.close()

    if source_count == 0:
        print("No sources found — seeding defaults...")
        seed_sources()
        print()
    else:
        print(f"Sources already seeded ({source_count} total). Skipping seed.\n")

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
    con = _sqlite3.connect(db.DB_PATH)
    con.row_factory = _sqlite3.Row
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
