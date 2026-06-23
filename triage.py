"""
triage.py — Haiku recall gate for the Blank continuous curation engine.

Reads un-triaged items from the DB, asks Haiku to decide KILL or ESCALATE
for each, and writes the decision via db.record_triage().

Design principle: Haiku is NOT deciding what's important. It is deciding
what is SAFE TO THROW AWAY. A wrongly-killed item is invisible and gone
forever. A wrongly-escalated item costs a fraction of a cent and Sonnet
filters it downstream. These errors are NOT equal — tune for recall.
When in doubt: ESCALATE. Over-escalating is healthy. Killing a survivor
is the only real failure.
"""

import json
import os
import sys
import time
from typing import Optional

import anthropic

import db

HAIKU_MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 20

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a recall gate for a content curation pipeline. Your only job is to \
identify items that are SAFE TO DISCARD — not to judge importance or topic \
quality. When uncertain, always ESCALATE.

KILL only when one of these is clearly true (uncertain → ESCALATE):
1. No substance: SEO filler, press-release boilerplate, affiliate/"best \
deals" roundups, a headline with no actual news behind it.
2. Non-content: login wall stub, navigation/category page, error page, \
contextless media with no surrounding information.
3. Routine triviality with no conceivable wider hook: purely local \
administrative notices, routine filler, "National X Day" fluff. \
Note: niche ≠ trivial. Surprising or hard-to-categorize things often look \
niche — kill only if trivial AND you can imagine no wider audience interest.
4. Stale rehash: re-packages old news, adds nothing new, no new angle.

TITLE-ONLY ITEMS (Reddit and similar formats): Many sources — Reddit, \
link-aggregators, image boards — produce items where the title is the \
entire content by design. There is no separate description blurb. Do NOT \
kill an item solely because its description is empty or missing. The title \
alone is sufficient substance. Kill only if the title itself is contentless \
— single words or pure noise like "Meirl", "Lol", "This", with no \
describable subject. A title that describes a video, a result, an event, \
an image's subject, or a substantive question IS content and must ESCALATE.

NEVER kill for:
- Being niche, small-source, or off-mainstream
- Being surprising, weird, or hard to categorize
- Having visible engagement or discussion
- Being a topic you might personally find unimportant
- Any uncertainty about whether it matters
- Having an empty description (title-only format — see rule above)

You hold NO topic opinions. Politics, gossip, sports, finance, culture, \
anything — all topics are equal here. Kill only for structural reasons \
listed above, never for subject matter.

Return ONLY a valid JSON array — no preamble, no markdown fences, no \
explanation. Each element: \
{"item_id": <int>, "decision": "KILL" | "ESCALATE", \
"kill_reason": "<short phrase, only when KILL, omit or null when ESCALATE>"}
"""

USER_PROMPT_TEMPLATE = """\
Triage the following items. Return only the JSON array.

{items_block}
"""


def _build_items_block(batch: list[dict]) -> str:
    lines = []
    for item in batch:
        desc = (item["description"] or "").strip()
        desc_part = f"\n  Description: {desc[:300]}" if desc else ""
        lines.append(f'Item {item["id"]}:\n  Title: {item["title"]}{desc_part}')
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# JSON parsing — defensive, strips accidental fences
# ---------------------------------------------------------------------------

def _parse_haiku_response(text: str) -> Optional[list[dict]]:
    """
    Parse Haiku's JSON array response. Strips markdown code fences if present.
    Returns None on any parse failure — caller must ESCALATE the whole batch.
    """
    text = text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (fence open) and last non-empty line (fence close)
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


# ---------------------------------------------------------------------------
# Single batch call
# ---------------------------------------------------------------------------

def _triage_batch(
    client: anthropic.Anthropic,
    batch: list[dict],
    db_path: str,
) -> dict:
    """
    Send one batch to Haiku, parse the response, write decisions to DB.
    On any parse failure, ESCALATE every item in the batch (fail toward recall).

    Returns {"escalated": int, "killed": int, "parse_failed": bool}
    """
    items_block = _build_items_block(batch)
    batch_ids = {item["id"] for item in batch}

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
        print(f"  [ERROR] Haiku API call failed: {exc}")
        _escalate_all(batch, db_path, reason="api_error")
        return {"escalated": len(batch), "killed": 0, "parse_failed": True}

    decisions = _parse_haiku_response(raw)

    if decisions is None:
        print(f"  [WARN] Failed to parse Haiku response — escalating entire batch of {len(batch)}")
        print(f"  [WARN] Raw response (first 300 chars): {raw[:300]}")
        _escalate_all(batch, db_path, reason="parse_failure")
        return {"escalated": len(batch), "killed": 0, "parse_failed": True}

    escalated = 0
    killed = 0
    seen_ids = set()

    for entry in decisions:
        try:
            item_id = int(entry["item_id"])
            decision = str(entry.get("decision", "ESCALATE")).upper()
            kill_reason = entry.get("kill_reason") or None

            if decision not in ("KILL", "ESCALATE"):
                decision = "ESCALATE"
                kill_reason = None

            if item_id not in batch_ids:
                continue  # Haiku hallucinated an id not in this batch — skip

            seen_ids.add(item_id)
            db.record_triage(
                item_id=item_id,
                decision=decision,
                signals={},
                kill_reason=kill_reason if decision == "KILL" else None,
                db_path=db_path,
            )

            if decision == "KILL":
                killed += 1
            else:
                escalated += 1

        except Exception as exc:
            print(f"  [ERROR] Failed to process decision entry {entry}: {exc}")
            # If we can identify the item, ESCALATE it
            try:
                item_id = int(entry.get("item_id", -1))
                if item_id in batch_ids:
                    seen_ids.add(item_id)
                    db.record_triage(item_id=item_id, decision="ESCALATE", signals={}, db_path=db_path)
                    escalated += 1
            except Exception:
                pass

    # Any item Haiku silently omitted from the response → ESCALATE (fail toward recall)
    missing_ids = batch_ids - seen_ids
    for item_id in missing_ids:
        db.record_triage(item_id=item_id, decision="ESCALATE", signals={}, db_path=db_path)
        escalated += 1

    if missing_ids:
        print(f"  [WARN] Haiku omitted {len(missing_ids)} item(s) — all escalated")

    return {"escalated": escalated, "killed": killed, "parse_failed": False}


def _escalate_all(batch: list[dict], db_path: str, reason: str) -> None:
    """Escalate every item in a batch. Used when a batch call fails entirely."""
    for item in batch:
        try:
            db.record_triage(
                item_id=item["id"],
                decision="ESCALATE",
                signals={"escalation_reason": reason},
                db_path=db_path,
            )
        except Exception as exc:
            print(f"  [ERROR] Could not record fallback escalation for item {item['id']}: {exc}")


# ---------------------------------------------------------------------------
# Re-triage helper — clears KILL rows so they flow back through run_triage()
# ---------------------------------------------------------------------------

def reset_killed_items(db_path: str = db.DB_PATH) -> int:
    """
    Delete all triage rows where decision = 'KILL', returning them to the
    un-triaged pool so run_triage() will re-evaluate them with the current
    prompt. Used after a prompt fix to recheck previously-killed items.

    Returns the number of rows deleted.
    """
    import sqlite3
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute("DELETE FROM triage WHERE decision = 'KILL'")
        count = cur.rowcount
        con.commit()
        return count
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Main triage runner
# ---------------------------------------------------------------------------

def run_triage(db_path: str = db.DB_PATH) -> dict:
    """
    Triage all un-triaged items in the DB. Processes in batches of BATCH_SIZE.

    Returns:
        {"total": int, "escalated": int, "killed": int,
         "escalation_rate": float, "batches": int, "parse_failures": int}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the environment")

    client = anthropic.Anthropic(api_key=api_key)

    items = db.get_untriaged_items(db_path=db_path)
    if not items:
        print("No un-triaged items found.")
        return {"total": 0, "escalated": 0, "killed": 0, "escalation_rate": 0.0,
                "batches": 0, "parse_failures": 0}

    print(f"Found {len(items)} un-triaged item(s). Processing in batches of {BATCH_SIZE}...\n")

    total_escalated = 0
    total_killed = 0
    total_parse_failures = 0
    batch_count = 0

    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} items)...", end=" ", flush=True)

        result = _triage_batch(client, batch, db_path)
        total_escalated += result["escalated"]
        total_killed += result["killed"]
        batch_count += 1
        if result["parse_failed"]:
            total_parse_failures += 1

        print(f"escalated={result['escalated']}  killed={result['killed']}")

    total = total_escalated + total_killed
    escalation_rate = (total_escalated / total * 100) if total > 0 else 0.0

    return {
        "total": total,
        "escalated": total_escalated,
        "killed": total_killed,
        "escalation_rate": escalation_rate,
        "batches": batch_count,
        "parse_failures": total_parse_failures,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from dotenv import load_dotenv
    load_dotenv()

    if "--retriage-kills" in sys.argv:
        n = reset_killed_items()
        print(f"Cleared {n} KILL row(s) — items returned to un-triaged pool.\n")

    print("Running Haiku triage...\n")
    t0 = time.time()
    summary = run_triage()
    elapsed = time.time() - t0

    print(f"\n-- Triage Summary ---------------------------")
    print(f"  Total triaged      : {summary['total']}")
    print(f"  Escalated          : {summary['escalated']}")
    print(f"  Killed             : {summary['killed']}")
    print(f"  Escalation rate    : {summary['escalation_rate']:.1f}%")
    print(f"  Batches sent       : {summary['batches']}")
    print(f"  Parse failures     : {summary['parse_failures']}")
    print(f"  Elapsed            : {elapsed:.1f}s")

    if summary["total"] > 0 and summary["escalation_rate"] < 40.0:
        print(f"\n  [FLAG] Escalation rate is {summary['escalation_rate']:.1f}% — below the healthy")
        print(f"         40-60% target. Haiku may be killing too aggressively. Review the")
        print(f"         killed sample below and consider loosening the prompt if needed.")

    if summary["total"] == 0:
        sys.exit(0)

    # Sample of killed items
    import sqlite3 as _sqlite3
    con = _sqlite3.connect(db.DB_PATH)
    con.row_factory = _sqlite3.Row

    killed_rows = con.execute(
        """
        SELECT i.title, t.kill_reason
        FROM triage t
        JOIN items i ON i.id = t.item_id
        WHERE t.decision = 'KILL'
        ORDER BY t.triaged_at DESC
        LIMIT 5
        """
    ).fetchall()

    escalated_rows = con.execute(
        """
        SELECT i.title
        FROM triage t
        JOIN items i ON i.id = t.item_id
        WHERE t.decision = 'ESCALATE'
        ORDER BY t.triaged_at DESC
        LIMIT 5
        """
    ).fetchall()
    con.close()

    print(f"\n-- Sample: Killed (up to 5) -----------------")
    if killed_rows:
        for i, r in enumerate(killed_rows, 1):
            reason = r["kill_reason"] or "no reason recorded"
            print(f"  [{i}] {r['title'][:85]}")
            print(f"       Reason: {reason}")
    else:
        print("  (none killed)")

    print(f"\n-- Sample: Escalated (up to 5) --------------")
    if escalated_rows:
        for i, r in enumerate(escalated_rows, 1):
            print(f"  [{i}] {r['title'][:85]}")
    else:
        print("  (none escalated)")
