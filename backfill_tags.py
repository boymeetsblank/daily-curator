"""
backfill_tags.py — self-draining topic-tag backfill for the Blank engine.

Topic tagging (primary_category + tags) is produced in the Sonnet score pass, so
only items scored AFTER tagging shipped carry tags. This stage tags the leftover
backlog: each run it classifies up to BACKFILL_LIMIT scored, feed-eligible,
still-untagged items in the recent window via one cheap Haiku call per batch.

Self-draining by design: new scores are already tagged, and old untagged items
age out of the feed window — so the queue empties within a few runs and this
stage becomes a near-free no-op (a single COUNT query returning nothing). It does
NOT re-score anything; it only fills in primary_category + tags on existing rows.

Reuses score.py's taxonomy (CATEGORIES), item formatting, JSON parser, and
normalizers so the backfilled tags match what the score pass would produce.
"""

import os
import sys
import time
from typing import Optional

import anthropic

import db
import score  # CATEGORIES, _build_items_block, _parse_sonnet_response, normalizers

HAIKU_MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 20
BACKFILL_LIMIT = 40  # max items tagged per engine run (bounds per-run cost)

SYSTEM_PROMPT = """\
You are a topic classifier for a news feed. For EACH item, assign:
- primary_category: choose EXACTLY ONE label from this fixed list (verbatim):
{categories_block}
  Pick the single best fit. Use "Other" only if none genuinely apply.
- tags: 2–5 short free-form tags (entities, subtopics, themes), e.g. \
["OpenAI", "EU AI Act", "regulation"]. Keep them specific — not restatements \
of the category.

OUTPUT — return ONLY a valid JSON array, no preamble, no markdown fences. \
Each element:
{{"item_id": <int>, "primary_category": "<one label from the list above>", "tags": [<2-5 short strings>]}}
""".format(categories_block="\n".join(f"  - {c}" for c in score.CATEGORIES))

USER_PROMPT_TEMPLATE = """\
Classify the following items. Return only the JSON array.

{items_block}
"""


def _tag_batch(client: anthropic.Anthropic, batch: list[dict], db_path: str) -> dict:
    """Tag one batch via Haiku, write primary_category + tags back. Returns counts."""
    batch_by_id = {item["id"]: item for item in batch}
    items_block = score._build_items_block(batch)

    try:
        message = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(items_block=items_block)}
            ],
        )
        raw = message.content[0].text
    except Exception as exc:
        print(f"  [ERROR] Haiku tag call failed: {exc}")
        return {"tagged": 0, "skipped": len(batch)}

    decisions = score._parse_sonnet_response(raw)
    if decisions is None:
        print(f"  [WARN] Failed to parse tag response — skipping batch of {len(batch)}")
        return {"tagged": 0, "skipped": len(batch)}

    tagged = 0
    skipped = 0
    for entry in decisions:
        try:
            item_id = int(entry["item_id"])
            if item_id not in batch_by_id:
                continue  # hallucinated id
            cat = score._normalize_category(entry.get("primary_category"))
            tags = score._normalize_tags(entry.get("tags"))
            db.update_score_tags(item_id, cat, tags, db_path)
            tagged += 1
        except Exception as exc:
            print(f"  [ERROR] Failed to process tag entry {entry}: {exc}")
            skipped += 1

    return {"tagged": tagged, "skipped": skipped}


def run_backfill(db_path: str = db.DB_PATH) -> dict:
    """
    Tag up to BACKFILL_LIMIT untagged in-window scored items. Graceful no-op if
    the API key is missing or nothing needs tagging. Never raises.

    Returns {"tagged": int, "skipped": int, "remaining": int, "skipped_run": bool}.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping tag backfill.")
        return {"tagged": 0, "skipped": 0, "remaining": 0, "skipped_run": True}

    items = db.get_untagged_scored_items(limit=BACKFILL_LIMIT, db_path=db_path)
    if not items:
        print("  No untagged in-window items — tag backfill is caught up.")
        return {"tagged": 0, "skipped": 0, "remaining": 0, "skipped_run": False}

    client = anthropic.Anthropic(api_key=api_key)
    print(f"  Backfilling tags for {len(items)} item(s) in batches of {BATCH_SIZE}...")

    total_tagged = 0
    total_skipped = 0
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        result = _tag_batch(client, batch, db_path)
        total_tagged += result["tagged"]
        total_skipped += result["skipped"]

    # How many in-window items still need tagging (for log visibility).
    remaining = len(db.get_untagged_scored_items(limit=10_000, db_path=db_path))
    return {
        "tagged": total_tagged,
        "skipped": total_skipped,
        "remaining": remaining,
        "skipped_run": False,
    }


# ---------------------------------------------------------------------------
# Self-test + live run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # --- Offline checks: queue + update + prompt, no API needed ----------------
    import os as _os
    from datetime import datetime, timezone

    TEST_DB = "backfill_test.db"
    if _os.path.exists(TEST_DB):
        _os.remove(TEST_DB)
    db.init_db(TEST_DB)
    src = db.upsert_source("https://ex.com/f", "Example", "rss", db_path=TEST_DB)
    iid = db.insert_item(
        source_id=src, url="https://ex.com/1", title="OpenAI ships a new model",
        description="A big AI release.",
        published_at=datetime.now(timezone.utc).isoformat(), db_path=TEST_DB,
    )
    db.record_triage(item_id=iid, decision="ESCALATE", signals={}, db_path=TEST_DB)
    db.record_score(item_id=iid, score=8, criteria={}, db_path=TEST_DB)  # no category

    untagged = db.get_untagged_scored_items(db_path=TEST_DB)
    assert len(untagged) == 1, f"expected 1 untagged, got {len(untagged)}"
    db.update_score_tags(iid, "Technology & AI", ["OpenAI"], db_path=TEST_DB)
    assert db.get_untagged_scored_items(db_path=TEST_DB) == [], "should be caught up after tagging"
    assert "Technology & AI" in SYSTEM_PROMPT and "JSON array" in SYSTEM_PROMPT
    print("Offline checks passed (queue drains after update; prompt OK).")

    import gc
    gc.collect()
    _os.remove(TEST_DB)

    # --- Live run against a COPY of blank.db (needs ANTHROPIC_API_KEY) ----------
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if not _os.path.exists(db.DB_PATH):
        print(f"\nNo {db.DB_PATH} present — skipping live backfill run.")
        sys.exit(0)

    import shutil
    LIVE_COPY = "backfill_live_test.db"
    shutil.copyfile(db.DB_PATH, LIVE_COPY)
    db.init_db(LIVE_COPY)

    before = len(db.get_untagged_scored_items(limit=10_000, db_path=LIVE_COPY))
    print(f"\nUntagged in-window items before: {before}")
    print("Running one backfill pass against a copy...")
    t0 = time.time()
    result = run_backfill(LIVE_COPY)
    print(f"Result: {result}  ({time.time() - t0:.1f}s)")

    gc.collect()
    _os.remove(LIVE_COPY)
