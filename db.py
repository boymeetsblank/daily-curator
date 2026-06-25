"""
db.py — SQLite data layer for the Blank continuous curation engine.

Standalone module. Not wired into the existing pipeline.
Initialize with init_db(); all other functions assume the DB exists.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

DB_PATH = "blank.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT    NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    type          TEXT    NOT NULL,          -- rss / reddit / etc.
    added_at      TEXT    NOT NULL,
    last_polled_at TEXT,
    active        INTEGER NOT NULL DEFAULT 1 -- bool
);

CREATE TABLE IF NOT EXISTS items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id      INTEGER NOT NULL REFERENCES sources(id),
    url            TEXT    NOT NULL UNIQUE,
    content_hash   TEXT    NOT NULL UNIQUE,  -- for score-once dedup
    title          TEXT    NOT NULL,
    description    TEXT,
    published_at   TEXT,
    fetched_at     TEXT    NOT NULL,
    raw_engagement TEXT    NOT NULL DEFAULT '{}'  -- JSON
);

CREATE INDEX IF NOT EXISTS idx_items_content_hash ON items(content_hash);
CREATE INDEX IF NOT EXISTS idx_items_fetched_at   ON items(fetched_at);

CREATE TABLE IF NOT EXISTS triage (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER NOT NULL UNIQUE REFERENCES items(id),
    decision    TEXT    NOT NULL,   -- KILL / ESCALATE
    kill_reason TEXT,               -- nullable; only set when decision = KILL
    signals     TEXT    NOT NULL DEFAULT '{}',  -- JSON
    triaged_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_triage_decision ON triage(decision);

CREATE TABLE IF NOT EXISTS scores (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER NOT NULL UNIQUE REFERENCES items(id),
    score            INTEGER NOT NULL,          -- 1–10
    criteria         TEXT    NOT NULL DEFAULT '{}',  -- JSON: trending/timely/cultural/significance
    why              TEXT    NOT NULL,
    hook             TEXT    NOT NULL,
    soft_floor_flags TEXT    NOT NULL DEFAULT '{}',  -- JSON: popularity signals, not score-forcing
    scored_at        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scores_score     ON scores(score);
CREATE INDEX IF NOT EXISTS idx_scores_scored_at ON scores(scored_at);

CREATE TABLE IF NOT EXISTS engagement (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id    INTEGER NOT NULL REFERENCES items(id),
    user_id    TEXT    NOT NULL DEFAULT 'mo',
    action     TEXT    NOT NULL,   -- opened / scrolled_past / dwelled / saved / finished
    dwell_ms   INTEGER,            -- nullable; only meaningful for dwelled
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_engagement_user_created ON engagement(user_id, created_at);
"""


def _conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

def make_content_hash(title: str, description: str) -> str:
    """SHA-256 of lowercased, whitespace-normalized title + description."""
    normalized = " ".join((title + " " + (description or "")).lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_db(db_path: str = DB_PATH) -> None:
    """Create tables and indexes if they don't exist."""
    with _conn(db_path) as con:
        con.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def upsert_source(
    url: str,
    name: str,
    source_type: str,
    active: bool = True,
    db_path: str = DB_PATH,
) -> int:
    """
    Insert a new source or update name/type/active if the URL already exists.
    Returns the source id.
    """
    with _conn(db_path) as con:
        con.execute(
            """
            INSERT INTO sources (url, name, type, added_at, active)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                name   = excluded.name,
                type   = excluded.type,
                active = excluded.active
            """,
            (url, name, source_type, _now(), int(active)),
        )
        row = con.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()
        return row["id"]


def insert_item(
    source_id: int,
    url: str,
    title: str,
    description: Optional[str] = None,
    published_at: Optional[str] = None,
    raw_engagement: Optional[dict] = None,
    db_path: str = DB_PATH,
) -> int:
    """
    Insert a new item. Deduplicates on content_hash — if an item with the same
    normalized title+description already exists, returns the existing id without
    inserting. Also deduplicates on URL.
    Returns the item id (new or existing).
    """
    content_hash = make_content_hash(title, description or "")
    engagement_json = json.dumps(raw_engagement or {})
    fetched_at = _now()

    with _conn(db_path) as con:
        # Check content_hash first (score-once dedup)
        existing = con.execute(
            "SELECT id FROM items WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            return existing["id"]

        try:
            con.execute(
                """
                INSERT INTO items
                    (source_id, url, content_hash, title, description,
                     published_at, fetched_at, raw_engagement)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (source_id, url, content_hash, title, description,
                 published_at, fetched_at, engagement_json),
            )
        except sqlite3.IntegrityError:
            # URL collision — return that row's id
            row = con.execute("SELECT id FROM items WHERE url = ?", (url,)).fetchone()
            return row["id"]

        return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def record_triage(
    item_id: int,
    decision: str,
    signals: dict,
    kill_reason: Optional[str] = None,
    db_path: str = DB_PATH,
) -> int:
    """
    Log a Haiku triage decision (KILL or ESCALATE) for an item.
    Returns the triage row id.
    """
    if decision not in ("KILL", "ESCALATE"):
        raise ValueError(f"decision must be KILL or ESCALATE, got {decision!r}")

    with _conn(db_path) as con:
        con.execute(
            """
            INSERT INTO triage (item_id, decision, kill_reason, signals, triaged_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                decision    = excluded.decision,
                kill_reason = excluded.kill_reason,
                signals     = excluded.signals,
                triaged_at  = excluded.triaged_at
            """,
            (item_id, decision, kill_reason, json.dumps(signals), _now()),
        )
        row = con.execute("SELECT id FROM triage WHERE item_id = ?", (item_id,)).fetchone()
        return row["id"]


def record_score(
    item_id: int,
    score: int,
    criteria: dict,
    why: str,
    hook: str,
    soft_floor_flags: Optional[dict] = None,
    db_path: str = DB_PATH,
) -> int:
    """
    Log a Sonnet score (1–10) for an escalated item.
    soft_floor_flags holds popularity signals that were noted but did NOT force the score.
    Returns the score row id.
    """
    if not 1 <= score <= 10:
        raise ValueError(f"score must be 1–10, got {score}")

    with _conn(db_path) as con:
        con.execute(
            """
            INSERT INTO scores
                (item_id, score, criteria, why, hook, soft_floor_flags, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                score            = excluded.score,
                criteria         = excluded.criteria,
                why              = excluded.why,
                hook             = excluded.hook,
                soft_floor_flags = excluded.soft_floor_flags,
                scored_at        = excluded.scored_at
            """,
            (
                item_id, score,
                json.dumps(criteria), why, hook,
                json.dumps(soft_floor_flags or {}),
                _now(),
            ),
        )
        row = con.execute("SELECT id FROM scores WHERE item_id = ?", (item_id,)).fetchone()
        return row["id"]


def log_engagement(
    item_id: int,
    action: str,
    user_id: str = "mo",
    dwell_ms: Optional[int] = None,
    db_path: str = DB_PATH,
) -> int:
    """
    Record a single user engagement event. Multiple events per item are fine.
    action: opened | scrolled_past | dwelled | saved | finished
    Returns the engagement row id.
    """
    valid_actions = {"opened", "scrolled_past", "dwelled", "saved", "finished"}
    if action not in valid_actions:
        raise ValueError(f"action must be one of {valid_actions}, got {action!r}")

    with _conn(db_path) as con:
        con.execute(
            """
            INSERT INTO engagement (item_id, user_id, action, dwell_ms, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item_id, user_id, action, dwell_ms, _now()),
        )
        return con.execute("SELECT last_insert_rowid()").fetchone()[0]


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_untriaged_items(db_path: str = DB_PATH) -> list[dict]:
    """
    Return items that have no row in the triage table yet.
    Used to drive the Haiku triage queue.
    """
    with _conn(db_path) as con:
        rows = con.execute(
            """
            SELECT i.id, i.title, i.description
            FROM items i
            LEFT JOIN triage t ON t.item_id = i.id
            WHERE t.id IS NULL
            ORDER BY i.fetched_at ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_unscored_escalated_items(db_path: str = DB_PATH) -> list[dict]:
    """
    Return items that Haiku escalated but Sonnet hasn't scored yet.
    Used to drive the scoring queue.
    """
    with _conn(db_path) as con:
        rows = con.execute(
            """
            SELECT i.*
            FROM items i
            JOIN triage t ON t.item_id = i.id
            LEFT JOIN scores s ON s.item_id = i.id
            WHERE t.decision = 'ESCALATE'
              AND s.id IS NULL
            ORDER BY i.fetched_at ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_kill_pile(since: str, db_path: str = DB_PATH) -> list[dict]:
    """
    Return all KILL triage records since a given ISO timestamp.
    Used for the audit log — lets us review what Haiku discarded.
    """
    with _conn(db_path) as con:
        rows = con.execute(
            """
            SELECT t.*, i.title, i.description, i.url, i.fetched_at
            FROM triage t
            JOIN items i ON i.id = t.item_id
            WHERE t.decision = 'KILL'
              AND t.triaged_at >= ?
            ORDER BY t.triaged_at DESC
            """,
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]


def _balance_feed(
    items: list[dict],
    limit: int,
    max_source_share: float,
) -> list[dict]:
    """
    Greedy source-capping pass over a score-sorted candidate list.

    Each source may claim at most round(limit * max_source_share) slots.
    Items that exceed a source's cap are deferred and appended in score
    order after the main pass — so they still appear in the feed, just
    below less-dominant sources.  High-scoring stories from any source
    are never suppressed; only the long tail of mid-scoring items from a
    single dominant source gets pushed down.
    """
    cap = max(1, round(limit * max_source_share))
    accepted: list[dict] = []
    deferred: list[dict] = []
    counts: dict[int, int] = {}

    for item in items:
        src = item["source_id"]
        if counts.get(src, 0) < cap:
            accepted.append(item)
            counts[src] = counts.get(src, 0) + 1
        else:
            deferred.append(item)

    return (accepted + deferred)[:limit]


def get_feed(
    min_score: int = 6,
    limit: int = 20,
    max_source_share: float = 0.30,
    db_path: str = DB_PATH,
) -> list[dict]:
    """
    Return scored items at or above min_score, balanced across sources.

    Ranking: score DESC (primary), scored_at DESC (tiebreaker).
    Balancing: no single source may occupy more than max_source_share of
    the returned items (default 30%).  A 5x candidate pool is fetched
    first so the balancer has room to reorder without running out of items.

    Prints a before/after source-distribution report to stdout on each call
    so the effect of the cap is visible in logs and easy to tune.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    # Pull a wide candidate pool so balancing has room to work.
    candidate_limit = min(limit * 5, 500)

    with _conn(db_path) as con:
        rows = con.execute(
            """
            SELECT i.id, i.url, i.title, i.description, i.published_at,
                   i.fetched_at, i.raw_engagement,
                   s.score, s.criteria, s.why, s.hook, s.scored_at,
                   src.id   AS source_id,
                   src.name AS source_name
            FROM scores s
            JOIN items i   ON i.id  = s.item_id
            JOIN sources src ON src.id = i.source_id
            WHERE s.score >= ?
              AND i.fetched_at >= ?
            ORDER BY s.score DESC, s.scored_at DESC
            LIMIT ?
            """,
            (min_score, cutoff, candidate_limit),
        ).fetchall()

    candidates = [dict(r) for r in rows]

    # ── Before-balancing distribution (top 50 candidates by score) ────────────
    before: dict[str, int] = {}
    for item in candidates[:50]:
        before[item["source_name"]] = before.get(item["source_name"], 0) + 1

    print(f"\n-- Feed assembly: {len(candidates)} candidates, score >= {min_score}, last 48 h --")
    print("  BEFORE balancing (top 50 by score):")
    for name, n in sorted(before.items(), key=lambda x: -x[1]):
        print(f"    {n:>3}  {name}")

    # ── Balance ───────────────────────────────────────────────────────────────
    balanced = _balance_feed(candidates, limit, max_source_share)

    # ── After-balancing distribution ──────────────────────────────────────────
    after: dict[str, int] = {}
    for item in balanced:
        after[item["source_name"]] = after.get(item["source_name"], 0) + 1

    cap = max(1, round(limit * max_source_share))
    print(f"  AFTER balancing (max_source_share={max_source_share:.0%}, cap={cap}/source,"
          f" returning {len(balanced)}):")
    for name, n in sorted(after.items(), key=lambda x: -x[1]):
        print(f"    {n:>3}  {name}")
    print()

    return balanced


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    TEST_DB = "blank_test.db"

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    print("Initializing DB...")
    init_db(TEST_DB)
    print("  OK")

    print("Inserting source...")
    src_id = upsert_source(
        url="https://example.com/feed.rss",
        name="Example RSS",
        source_type="rss",
        db_path=TEST_DB,
    )
    print(f"  source id={src_id}")

    print("Upserting same source (should update, not insert)...")
    src_id2 = upsert_source(
        url="https://example.com/feed.rss",
        name="Example RSS (renamed)",
        source_type="rss",
        db_path=TEST_DB,
    )
    assert src_id == src_id2, "upsert_source should return same id"
    print(f"  still id={src_id2}  OK")

    print("Inserting item...")
    item_id = insert_item(
        source_id=src_id,
        url="https://example.com/article-1",
        title="Big Culture Moment",
        description="Something culturally significant happened.",
        raw_engagement={"source_pickups": 5, "likes": 1200},
        db_path=TEST_DB,
    )
    print(f"  item id={item_id}")

    print("Inserting duplicate (same content_hash, different URL)...")
    dup_id = insert_item(
        source_id=src_id,
        url="https://mirror.com/article-1",
        title="Big Culture Moment",
        description="Something culturally significant happened.",
        db_path=TEST_DB,
    )
    assert dup_id == item_id, "Duplicate content should return existing id"
    print(f"  returned existing id={dup_id}  OK")

    print("Recording triage (ESCALATE)...")
    triage_id = record_triage(
        item_id=item_id,
        decision="ESCALATE",
        signals={"source_pickups": 5, "trending_x": True},
        db_path=TEST_DB,
    )
    print(f"  triage id={triage_id}")

    print("Checking escalated queue...")
    queue = get_unscored_escalated_items(TEST_DB)
    assert len(queue) == 1
    print(f"  {len(queue)} item in queue  OK")

    print("Recording score...")
    score_id = record_score(
        item_id=item_id,
        score=8,
        criteria={"trending": 9, "timely": 8, "cultural": 8, "significance": 7},
        why="Widely picked up, strong cultural resonance.",
        hook="Here's why this moment matters for the culture.",
        soft_floor_flags={"high_like_count": True},
        db_path=TEST_DB,
    )
    print(f"  score id={score_id}")

    print("Logging engagement...")
    eng_id = log_engagement(item_id=item_id, action="dwelled", dwell_ms=4200, db_path=TEST_DB)
    print(f"  engagement id={eng_id}")

    print("Reading feed (min_score=6)...")
    feed = get_feed(min_score=6, limit=10, db_path=TEST_DB)
    assert len(feed) == 1
    assert feed[0]["score"] == 8
    print(f"  {len(feed)} item in feed, score={feed[0]['score']}  OK")

    print("Reading kill pile (empty — nothing killed)...")
    kill_pile = get_kill_pile(since="2000-01-01T00:00:00+00:00", db_path=TEST_DB)
    assert len(kill_pile) == 0
    print(f"  {len(kill_pile)} items  OK")

    print("Recording a KILL for coverage...")
    item_id2 = insert_item(
        source_id=src_id,
        url="https://example.com/article-2",
        title="Boring Press Release",
        description="A company announced earnings.",
        db_path=TEST_DB,
    )
    record_triage(item_id=item_id2, decision="KILL", kill_reason="no cultural angle", signals={}, db_path=TEST_DB)
    kill_pile2 = get_kill_pile(since="2000-01-01T00:00:00+00:00", db_path=TEST_DB)
    assert len(kill_pile2) == 1
    print(f"  kill pile now has {len(kill_pile2)} item  OK")

    import gc
    gc.collect()  # release sqlite connections before delete (Windows file-lock)
    os.remove(TEST_DB)
    print("\nAll checks passed. blank_test.db cleaned up.")
