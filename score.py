"""
score.py — Sonnet scoring layer for the Blank continuous curation engine.

Pulls escalated-but-unscored items, scores each 1–10 against the rubric,
and writes results via db.record_score(). This is the taste layer: the
place where cultural judgment actually lives.

Does not touch daily_curator.py or any part of the existing pipeline.

TODO: v1 scores on title + description only. A future pass should fetch
full article text (via trafilatura or similar) and pass it to Sonnet for
richer signal — especially for items where the description is sparse.
"""

import json
import os
import sys
import time
from typing import Optional

import anthropic

import db

SONNET_MODEL = "claude-sonnet-4-6"
BATCH_SIZE = 12
FEED_THRESHOLD = 6  # items scoring below this are filtered from the feed

# ---------------------------------------------------------------------------
# Prompt — the rubric is the product; follow exactly
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior editor curating a discovery feed. You surface what is most \
worth a curious person's attention across ANY subject. You hold NO topic \
opinions — politics, gossip, sports, niche hobbies are all first-class. \
No subject is inherently more or less worthy than another.

AN ITEM EARNS ITS PLACE BY EITHER OF TWO INDEPENDENT AXES — it needs only ONE:

1. INTEREST — surprising, novel, weird, culturally resonant, "wait, what?" — \
   the kind of thing someone would be glad they saw.
2. IMPORTANCE/SIGNIFICANCE — consequential, major news a reasonable person \
   should know — the kind of thing someone would be upset they missed.

An item strong on either axis scores high. Important news is NEVER downgraded \
for being "not interesting enough." A fascinating item is NEVER downgraded for \
being "not important enough."

FOUR CRITERIA (these inform the score; they are judgment, not arithmetic):
- trending: are people actively discussing this now?
- timely: recency-weighted — <12h favorable; 24–48h older unless still developing
- cultural: does it connect to a broader moment or movement?
- significance: does it genuinely matter?

Score each criterion 1–10 as context for your overall score. The overall score \
is your editorial judgment — not an average of the four.

SCALE:
10 → rare; a genuine cultural moment people reference a year out
9  → you would urgently tell someone today
8  → you would bring it up in conversation today
7  → worth their time, clearly earned its place
6  → made the cut; relevant but not urgent
1–5 → below the feed threshold

When torn between 6 and 7, score 7. Favor inclusion at the margin.

SOFT SIGNALS — NOT hard floors:
Popularity signals (high upvotes, multi-source pickup, high engagement) may \
INFORM your judgment and must be recorded in soft_floor_flags. They do NOT \
force a minimum score. A wildly popular item that is not actually interesting \
or important can still score low. Engagement is evidence, never an override. \
The product's north star is interestingness or importance earned on the merits.

OUTPUT per item — return ONLY a valid JSON array, no preamble, no markdown \
fences, no explanation outside the array. Each element:
{
  "item_id": <int>,
  "score": <int 1-10>,
  "criteria": {"trending": <1-10>, "timely": <1-10>, "cultural": <1-10>, "significance": <1-10>},
  "soft_floor_flags": [<string description of any popularity signal noted, or empty list>]
}
"""

USER_PROMPT_TEMPLATE = """\
Score the following items. Return only the JSON array.

{items_block}
"""


def _build_items_block(batch: list[dict]) -> str:
    lines = []
    for item in batch:
        desc = (item.get("description") or "").strip()
        desc_part = f"\n  Description: {desc[:500]}" if desc else ""
        lines.append(
            f'Item {item["id"]}:'
            f'\n  Title: {item["title"]}'
            f'{desc_part}'
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# JSON parsing — defensive, strips accidental fences
# ---------------------------------------------------------------------------

def _parse_sonnet_response(text: str) -> Optional[list[dict]]:
    """
    Parse Sonnet's JSON array. Strips markdown fences if present.
    Returns None on any parse failure — caller logs and skips the batch.
    """
    text = text.strip()

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
        if not isinstance(parsed, list):
            return None
        return parsed
    except json.JSONDecodeError:
        return None


def _normalize_soft_floor_flags(raw) -> dict:
    """
    record_score() expects a dict. Sonnet is prompted to return a list of
    strings. Normalize either shape into a dict for storage.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {"flags": raw} if raw else {}
    return {}


# ---------------------------------------------------------------------------
# Single batch scoring call
# ---------------------------------------------------------------------------

def _score_batch(
    client: anthropic.Anthropic,
    batch: list[dict],
    db_path: str,
) -> dict:
    """
    Send one batch to Sonnet, parse, write scores to DB.

    On API or parse failure: logs and skips the batch entirely — scoring
    is re-runnable (un-scored escalated items stay in the queue).

    Returns {"scored": int, "skipped": int, "parse_failed": bool}
    """
    batch_by_id = {item["id"]: item for item in batch}
    items_block = _build_items_block(batch)

    try:
        message = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(items_block=items_block)}
            ],
        )
        raw = message.content[0].text
    except Exception as exc:
        print(f"  [ERROR] Sonnet API call failed: {exc}")
        return {"scored": 0, "skipped": len(batch), "parse_failed": True}

    decisions = _parse_sonnet_response(raw)

    if decisions is None:
        print(f"  [WARN] Failed to parse Sonnet response — skipping batch of {len(batch)}")
        print(f"  [WARN] Raw (first 300 chars): {raw[:300]}")
        return {"scored": 0, "skipped": len(batch), "parse_failed": True}

    scored = 0
    skipped = 0

    for entry in decisions:
        try:
            item_id = int(entry["item_id"])
            if item_id not in batch_by_id:
                continue  # hallucinated id — skip

            score = int(entry["score"])
            if not 1 <= score <= 10:
                print(f"  [WARN] Score {score} out of range for item {item_id} — skipping")
                skipped += 1
                continue

            criteria = entry.get("criteria") or {}
            if not isinstance(criteria, dict):
                criteria = {}

            soft_floor_flags = _normalize_soft_floor_flags(entry.get("soft_floor_flags") or [])

            db.record_score(
                item_id=item_id,
                score=score,
                criteria=criteria,
                soft_floor_flags=soft_floor_flags,
                db_path=db_path,
            )
            scored += 1

        except Exception as exc:
            print(f"  [ERROR] Failed to process score entry {entry}: {exc}")
            skipped += 1

    return {"scored": scored, "skipped": skipped, "parse_failed": False}


# ---------------------------------------------------------------------------
# Main scoring runner
# ---------------------------------------------------------------------------

def run_scoring(db_path: str = db.DB_PATH) -> dict:
    """
    Score all escalated-but-unscored items in the DB.

    Returns:
        {"total_scored": int, "total_skipped": int, "parse_failures": int,
         "distribution": {10: int, 9: int, ..., 1: int},
         "below_threshold": int}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the environment")

    client = anthropic.Anthropic(api_key=api_key)

    items = db.get_unscored_escalated_items(db_path=db_path)
    if not items:
        print("No unscored escalated items found.")
        return {
            "total_scored": 0, "total_skipped": 0, "parse_failures": 0,
            "distribution": {}, "below_threshold": 0,
        }

    print(f"Found {len(items)} item(s) to score. Processing in batches of {BATCH_SIZE}...\n")

    total_scored = 0
    total_skipped = 0
    total_parse_failures = 0

    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} items)...", end=" ", flush=True)

        result = _score_batch(client, batch, db_path)
        total_scored += result["scored"]
        total_skipped += result["skipped"]
        if result["parse_failed"]:
            total_parse_failures += 1

        print(f"scored={result['scored']}  skipped={result['skipped']}")

    # Build score distribution from what was just written
    import sqlite3 as _sqlite3
    con = _sqlite3.connect(db_path)
    con.row_factory = _sqlite3.Row
    dist_rows = con.execute(
        "SELECT score, COUNT(*) as n FROM scores GROUP BY score ORDER BY score DESC"
    ).fetchall()
    con.close()

    distribution = {r["score"]: r["n"] for r in dist_rows}
    below_threshold = sum(v for k, v in distribution.items() if k < FEED_THRESHOLD)

    return {
        "total_scored": total_scored,
        "total_skipped": total_skipped,
        "parse_failures": total_parse_failures,
        "distribution": distribution,
        "below_threshold": below_threshold,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from dotenv import load_dotenv
    load_dotenv()

    print("Running Sonnet scoring...\n")
    t0 = time.time()
    summary = run_scoring()
    elapsed = time.time() - t0

    print(f"\n-- Scoring Summary --------------------------")
    print(f"  Scored this run    : {summary['total_scored']}")
    print(f"  Skipped (errors)   : {summary['total_skipped']}")
    print(f"  Parse failures     : {summary['parse_failures']}")
    print(f"  Below threshold (<{FEED_THRESHOLD}): {summary['below_threshold']}")
    print(f"  Elapsed            : {elapsed:.1f}s")

    dist = summary["distribution"]
    if dist:
        print(f"\n-- Score Distribution -----------------------")
        for s in range(10, 0, -1):
            count = dist.get(s, 0)
            bar = "#" * count
            marker = " <-- feed threshold" if s == FEED_THRESHOLD else ""
            print(f"  {s:2d}  {bar:<30} {count}{marker}")

    if summary["total_scored"] == 0:
        sys.exit(0)

    # Top 10 by score for eyeballing
    import sqlite3 as _sqlite3
    con = _sqlite3.connect(db.DB_PATH)
    con.row_factory = _sqlite3.Row
    top_rows = con.execute(
        """
        SELECT i.title, s.score
        FROM scores s
        JOIN items i ON i.id = s.item_id
        ORDER BY s.score DESC, s.scored_at DESC
        LIMIT 10
        """
    ).fetchall()
    con.close()

    print(f"\n-- Top 10 Items -----------------------------")
    for i, r in enumerate(top_rows, 1):
        print(f"\n  [{i}] score={r['score']}  {r['title'][:75]}")
