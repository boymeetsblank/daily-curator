"""
moment.py — "Moment" detection for the Blank continuous curation engine.

Once per run, asks Haiku a single question: is there ONE dominant story the
news is converging on right now? If so, name it and list which of the current
top items belong to it. The result powers the Moment rail in the feed.

Design notes:
- This is a NARROW slice of clustering: find THE single dominant story, not
  cluster the whole feed (full multi-source clustering is a separate, parked
  effort). That keeps it a cheap, bounded problem.
- ONE Haiku call per run over the top ~35 already-scored headlines. Global, not
  per-user — respects the engine's load-bearing cost rule. No new vendor.
- A moment is multi-story by definition: we require MOMENT_MIN_ITEMS members,
  so the rail stays meaningfully different from the #1 Top Story.
- Sourced from SCORED NEWS (not external trend lists), so it can't go stale the
  way the old Trending surface did.
- Graceful no-op: missing API key, API failure, parse failure, or "no dominant
  story" all leave the feed without a moment rather than erroring.

Mirrors the client + JSON-parse patterns in triage.py / score.py.
"""

import json
import os
import sys
import time
from typing import Optional

import anthropic

import db

HAIKU_MODEL = "claude-haiku-4-5-20251001"

# How many recent items to show Haiku as candidates. Generous so a high-VOLUME
# mega-event (e.g. a World Cup with dozens of stories) is well represented in the
# pool — breadth of coverage is how we pick the moment.
CANDIDATE_LIMIT = 60
# Only consider items scored at/above this (matches the feed threshold).
MIN_SCORE = 6
# Only look at recent items — a "moment" is about right now.
WINDOW_HOURS = 24
# A moment must span at least this many stories, else it's just a top story.
MOMENT_MIN_ITEMS = 3
# Cap how many stories a moment claims, so a huge event doesn't gut the rest of
# the feed. The highest-ranked members are kept.
MOMENT_MAX_ITEMS = 12

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a news desk editor. You are shown the top stories in a feed right now. \
Your ONE job: identify THE single biggest thing the world is collectively \
following at this moment — the event that most deserves its own featured section \
at the top of a news homepage — and list which of the shown items belong to it.

WHAT COUNTS AS THE MOMENT:
- It CAN be a SUSTAINED MEGA-EVENT that many separate stories orbit — a major \
sports tournament (e.g. the FIFA World Cup), the Olympics, a national election, \
an awards season, a major ongoing conflict or saga. These ARE moments even \
though they span many sub-stories (different matches, results, profiles, angles). \
Group ALL of those sub-stories together as the event's members.
- It CAN also be a single breaking event the news is converging on (a disaster, \
a strike, a landmark ruling).

CHOOSING WHEN SEVERAL BIG STORIES COMPETE:
- Prefer the event that the MOST of the shown stories are about. Breadth of \
coverage is the signal for "what the world is following." A tournament that 15 \
of these stories cover outranks a breaking event that 4 stories cover — even if \
those 4 individually score higher. Volume of related coverage wins.
- A breaking news event should win only when no sustained mega-event is drawing \
more total coverage.

WHAT IS NOT A MOMENT:
- A generic CATEGORY or subject area ("sports", "politics", "technology"). The \
moment must be one specific, NAMED event ("FIFA World Cup 2026"), never a topic.
- A spread of unrelated stories with no single event most of them share — then \
there is NO moment, which is a perfectly valid answer.

Use ONLY the item ids shown. Do not invent ids. The label is a short, neutral, \
specific name for the event (e.g. "FIFA World Cup 2026", "US-Iran Ceasefire \
Crisis", "2026 US Midterms"). No editorializing.

OUTPUT — return ONLY valid JSON, no preamble, no markdown fences:
{
  "label": "<short specific event name, or null if no dominant event>",
  "item_ids": [<ids of items belonging to the event, or empty list>]
}
"""

USER_PROMPT_TEMPLATE = """\
Here are the top stories in the feed right now. Identify the biggest thing the \
world is following — the event the most of these stories are about, if any.

{items_block}
"""


def _build_items_block(candidates: list[dict]) -> str:
    lines = []
    for c in candidates:
        lines.append(
            f'Item {c["id"]} (score {c["score"]}, {c["source_name"]}): {c["title"]}'
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Candidate pull — reuses the shared time-decayed ranking
# ---------------------------------------------------------------------------

def _get_candidates(db_path: str) -> list[dict]:
    """
    Recently-scored items (score >= MIN_SCORE in the window), ordered by RECENCY,
    not by score. This is deliberate: the Moment is chosen by breadth of coverage
    ("what the world is following"), so the pool must reflect VOLUME — a high-
    volume mega-event (e.g. a World Cup with dozens of stories) must be fully
    represented, not buried under a handful of higher-scored breaking items.
    Returns id/title/source_name/score (newest first).
    """
    from datetime import datetime, timezone, timedelta

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)).isoformat()
    with db._conn(db_path) as con:
        rows = con.execute(
            """
            SELECT i.id, i.title, i.published_at,
                   s.score, s.scored_at,
                   src.name AS source_name
            FROM scores s
            JOIN items i   ON i.id  = s.item_id
            JOIN sources src ON src.id = i.source_id
            WHERE s.score >= ?
              AND i.fetched_at >= ?
            ORDER BY s.scored_at DESC
            LIMIT ?
            """,
            (MIN_SCORE, cutoff, CANDIDATE_LIMIT),
        ).fetchall()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Response parsing — defensive, strips accidental fences (mirrors score.py)
# ---------------------------------------------------------------------------

def _parse_response(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            inner.append(line)
        text = "\n".join(inner).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Main stage
# ---------------------------------------------------------------------------

def run_moment_detection(db_path: str = db.DB_PATH) -> dict:
    """
    Detect the single dominant story and store it (or clear it) in the DB.

    Returns {"label": str|None, "item_count": int, "skipped": bool}. Never
    raises — any failure is a graceful no-op that leaves the feed without a
    moment (the existing one is cleared so it can't go stale).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping moment detection.")
        return {"label": None, "item_count": 0, "skipped": True}

    candidates = _get_candidates(db_path)
    if len(candidates) < MOMENT_MIN_ITEMS:
        print(f"  Only {len(candidates)} candidates — too few for a moment. Clearing.")
        db.clear_moment(db_path)
        return {"label": None, "item_count": 0, "skipped": False}

    client = anthropic.Anthropic(api_key=api_key)
    items_block = _build_items_block(candidates)

    try:
        message = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(items_block=items_block)}
            ],
        )
        raw = message.content[0].text
    except Exception as exc:
        print(f"  [ERROR] Haiku moment call failed: {exc} — leaving moment unchanged.")
        return {"label": None, "item_count": 0, "skipped": True}

    parsed = _parse_response(raw)
    if parsed is None:
        print(f"  [WARN] Could not parse moment response — leaving moment unchanged.")
        print(f"  [WARN] Raw (first 200 chars): {raw[:200]}")
        return {"label": None, "item_count": 0, "skipped": True}

    label = parsed.get("label")
    raw_ids = parsed.get("item_ids") or []

    # Keep only ids that were actually in the candidate set (no hallucinated ids),
    # then order members by SCORE (best first → the rail's lead is the strongest
    # story) and cap so a huge event can't claim the whole feed.
    score_of = {c["id"]: (c["score"] or 0) for c in candidates}
    seen = set()
    member_ids = []
    for i in raw_ids:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if i in score_of and i not in seen:
            seen.add(i)
            member_ids.append(i)
    member_ids.sort(key=lambda i: score_of[i], reverse=True)
    member_ids = member_ids[:MOMENT_MAX_ITEMS]

    if not label or not isinstance(label, str) or len(member_ids) < MOMENT_MIN_ITEMS:
        print(f"  No dominant story (label={label!r}, members={len(member_ids)}). Clearing moment.")
        db.clear_moment(db_path)
        return {"label": None, "item_count": 0, "skipped": False}

    label = label.strip()[:120]
    db.record_moment(label=label, item_ids=member_ids, db_path=db_path)
    print(f"  Moment: \"{label}\" — {len(member_ids)} stories.")
    return {"label": label, "item_count": len(member_ids), "skipped": False}


# ---------------------------------------------------------------------------
# Self-test + live run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # --- Offline check: candidate pull + parsing, no API needed ----------------
    import os as _os
    from datetime import datetime, timezone

    TEST_DB = "moment_test.db"
    if _os.path.exists(TEST_DB):
        _os.remove(TEST_DB)
    db.init_db(TEST_DB)
    src = db.upsert_source("https://ex.com/f", "Example", "rss", db_path=TEST_DB)
    ids = []
    for n in range(4):
        iid = db.insert_item(
            source_id=src, url=f"https://ex.com/{n}", title=f"Story {n}",
            published_at=datetime.now(timezone.utc).isoformat(), db_path=TEST_DB,
        )
        db.record_triage(item_id=iid, decision="ESCALATE", signals={}, db_path=TEST_DB)
        db.record_score(item_id=iid, score=8, criteria={}, db_path=TEST_DB)
        ids.append(iid)

    cands = _get_candidates(TEST_DB)
    assert len(cands) == 4, f"expected 4 candidates, got {len(cands)}"
    assert _parse_response('```json\n{"label": "X", "item_ids": [1,2,3]}\n```') == {
        "label": "X", "item_ids": [1, 2, 3]
    }, "fence-stripping parse failed"
    assert _parse_response("not json") is None
    print(f"Offline checks passed ({len(cands)} candidates, parser OK).")

    import gc
    gc.collect()
    _os.remove(TEST_DB)

    # --- Live run against the real DB (needs ANTHROPIC_API_KEY) ----------------
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if not _os.path.exists(db.DB_PATH):
        print(f"\nNo {db.DB_PATH} present — skipping live moment run.")
        sys.exit(0)

    # Run against a COPY so the authoritative blank.db is never mutated by a
    # manual test (the real engine runs init_db + this stage on its own copy).
    import shutil
    LIVE_COPY = "moment_live_test.db"
    shutil.copyfile(db.DB_PATH, LIVE_COPY)
    db.init_db(LIVE_COPY)  # ensure the moments table exists on the copy

    print(f"\nRunning live moment detection against a copy of {db.DB_PATH}...")
    t0 = time.time()
    result = run_moment_detection(LIVE_COPY)
    print(f"\nResult: {result}  ({time.time() - t0:.1f}s)")
    print(f"Active moment in DB: {db.get_active_moment(LIVE_COPY)}")

    gc.collect()
    _os.remove(LIVE_COPY)
