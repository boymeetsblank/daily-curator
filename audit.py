"""
audit.py — Sonnet second-opinion audit of Haiku's kill pile.

Periodically re-examines a sample of items Haiku killed and flags any that
Sonnet thinks were wrongly discarded. This makes the invisible error visible:
Haiku's only real failure mode is killing something that mattered, and that
error never surfaces unless explicitly checked.

Default mode (recover=False): measure-only — reports false-negative rate,
changes nothing. Recovery is opt-in: pass recover=True (or --recover on CLI)
to flip WRONGLY_KILLED items back to ESCALATE so they reach Sonnet scoring.

Safety cap: if the audit wants to recover more than RECOVERY_CAP (30%) of the
sampled kill pile in a single run, recovery is withheld and a warning is
printed. A spike that large usually means triage broke structurally; the right
response is to fix triage, not mass-re-inject via the audit.

Candidate for the 50% Anthropic batch discount since it is not time-sensitive.
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import anthropic

import db

SONNET_MODEL = "claude-sonnet-4-6"
BATCH_SIZE = 10  # smaller than Haiku — Sonnet output is wordier

# If wrongly-killed items exceed this fraction of the audited sample,
# recovery is withheld — a spike this large signals a structural triage break,
# not occasional judgment misses.
RECOVERY_CAP = 0.30

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are auditing another AI model's content triage decisions. Your job is to \
find false negatives — items the triage model wrongly killed that actually \
deserved to surface to users.

An item was WRONGLY_KILLED if it meets either of these bars (not both — \
either is enough):

1. INTERESTING: genuinely surprising, niche, weird, culturally resonant, \
   or something a curious person would be glad they discovered.
2. IMPORTANT: consequential, significant news that a reasonable person \
   would be upset to have missed — major events, notable decisions, \
   real-world impact.

The bar is: "Would a reasonable user be glad they saw this, OR upset they \
missed it?" Yes to either → WRONGLY_KILLED.

Topic-neutral: no subject is inherently kill-worthy. Politics, sports, \
gossip, finance, niche hobbies — any topic can qualify as interesting or \
important. Never mark something CORRECT_KILL purely because of its topic.

The triage model's stated kill_reason is provided for reference. It is \
often a structural reason (no substance, non-content, etc.). If you think \
the kill_reason mischaracterizes the item, say so in your reasoning.

Return ONLY a valid JSON array — no preamble, no markdown fences, no \
explanation outside the array. Each element:
{"item_id": <int>, "verdict": "CORRECT_KILL" | "WRONGLY_KILLED", \
"reasoning": "<one sentence explaining your verdict>"}
"""

USER_PROMPT_TEMPLATE = """\
Audit the following killed items. Return only the JSON array.

{items_block}
"""


def _build_items_block(batch: list[dict]) -> str:
    lines = []
    for item in batch:
        desc = (item.get("description") or "").strip()
        desc_part = f"\n  Description: {desc[:400]}" if desc else ""
        kill_reason = item.get("kill_reason") or "no reason recorded"
        lines.append(
            f'Item {item["item_id"]}:'
            f'\n  Title: {item["title"]}'
            f'{desc_part}'
            f'\n  Haiku kill_reason: {kill_reason}'
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# JSON parsing — defensive, strips accidental fences
# ---------------------------------------------------------------------------

def _parse_sonnet_response(text: str) -> Optional[list[dict]]:
    """
    Parse Sonnet's JSON array. Strips markdown fences if present.
    Returns None on any parse failure — caller logs and skips.
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


# ---------------------------------------------------------------------------
# Single batch audit call
# ---------------------------------------------------------------------------

def _audit_batch(
    client: anthropic.Anthropic,
    batch: list[dict],
) -> list[dict]:
    """
    Send one batch to Sonnet, return a list of verdict dicts:
        [{"item_id": int, "title": str, "kill_reason": str,
          "verdict": str, "reasoning": str}, ...]

    On API or parse failure: logs the error and returns an empty list
    (safe to skip — this is a read-only audit, unlike triage).
    """
    batch_by_id = {item["item_id"]: item for item in batch}
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
        return []

    decisions = _parse_sonnet_response(raw)

    if decisions is None:
        print(f"  [WARN] Failed to parse Sonnet response — skipping batch of {len(batch)}")
        print(f"  [WARN] Raw (first 300 chars): {raw[:300]}")
        return []

    results = []
    for entry in decisions:
        try:
            item_id = int(entry["item_id"])
            verdict = str(entry.get("verdict", "")).upper()
            reasoning = str(entry.get("reasoning", "")).strip()

            if verdict not in ("CORRECT_KILL", "WRONGLY_KILLED"):
                continue
            if item_id not in batch_by_id:
                continue

            original = batch_by_id[item_id]
            results.append({
                "item_id": item_id,
                "title": original["title"],
                "kill_reason": original.get("kill_reason") or "no reason recorded",
                "verdict": verdict,
                "reasoning": reasoning,
            })
        except Exception as exc:
            print(f"  [ERROR] Failed to process audit entry {entry}: {exc}")

    return results


# ---------------------------------------------------------------------------
# Recovery — flip a wrongly-killed item back to ESCALATE
# ---------------------------------------------------------------------------

def _recover_item(
    item_id: int,
    original_kill_reason: str,
    sonnet_reasoning: str,
    db_path: str,
) -> None:
    """
    Flip a KILL triage row to ESCALATE so the item reaches Sonnet scoring.

    The triage row is updated in place (record_triage uses ON CONFLICT UPDATE),
    annotating the signals JSON with the audit's reasoning so the recovery is
    traceable. kill_reason is cleared — it no longer applies.
    """
    db.record_triage(
        item_id=item_id,
        decision="ESCALATE",
        signals={
            "recovered_by_audit": True,
            "original_kill_reason": original_kill_reason,
            "audit_reasoning": sonnet_reasoning,
        },
        kill_reason=None,
        db_path=db_path,
    )


# ---------------------------------------------------------------------------
# Main audit runner
# ---------------------------------------------------------------------------

def run_audit(
    hours: int = 24,
    sample_size: Optional[int] = None,
    recover: bool = False,
    db_path: str = db.DB_PATH,
) -> dict:
    """
    Audit a sample of recently killed items using Sonnet.

    Args:
        hours:       How far back to look in the kill pile (default 24h).
        sample_size: If set, randomly sample this many items from the pile.
                     If None, audit the entire pile (fine for small volumes;
                     use sample_size at scale to control cost).
        recover:     If True, flip WRONGLY_KILLED items back to ESCALATE so
                     they reach Sonnet scoring on the next run. Subject to
                     RECOVERY_CAP — if the wrongly-killed rate exceeds 30%,
                     recovery is withheld and a warning is printed instead.
                     Default False (measure-only).
        db_path:     SQLite DB path.

    Returns:
        {"audited": int, "correct_kills": int, "wrongly_killed": int,
         "false_negative_rate": float, "recovered": int,
         "recovery_withheld": bool, "results": list[dict]}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the environment")

    client = anthropic.Anthropic(api_key=api_key)

    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    kill_pile = db.get_kill_pile(since=since, db_path=db_path)

    if not kill_pile:
        print(f"No killed items found in the last {hours}h.")
        return {
            "audited": 0, "correct_kills": 0, "wrongly_killed": 0,
            "false_negative_rate": 0.0, "recovered": 0,
            "recovery_withheld": False, "results": [],
        }

    # Rename 'id' → 'item_id' for clarity in prompts (triage table 'id' ≠ item_id)
    for row in kill_pile:
        row.setdefault("item_id", row.get("item_id") or row["id"])

    if sample_size is not None and sample_size < len(kill_pile):
        sample = random.sample(kill_pile, sample_size)
        print(f"Kill pile: {len(kill_pile)} items. Randomly sampling {sample_size}.\n")
    else:
        sample = kill_pile
        print(f"Kill pile: {len(kill_pile)} item(s) in the last {hours}h. Auditing all.\n")

    all_results = []
    total_batches = (len(sample) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(sample), BATCH_SIZE):
        batch = sample[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} items)...", end=" ", flush=True)
        results = _audit_batch(client, batch)
        all_results.extend(results)
        wrongly = sum(1 for r in results if r["verdict"] == "WRONGLY_KILLED")
        print(f"wrongly_killed={wrongly}/{len(results)} audited")

    correct = sum(1 for r in all_results if r["verdict"] == "CORRECT_KILL")
    wrongly_items = [r for r in all_results if r["verdict"] == "WRONGLY_KILLED"]
    audited = len(all_results)
    false_negative_rate = (len(wrongly_items) / audited * 100) if audited > 0 else 0.0

    recovered = 0
    recovery_withheld = False

    if recover and wrongly_items:
        cap_count = int(audited * RECOVERY_CAP)
        if len(wrongly_items) > cap_count:
            recovery_withheld = True
            print(
                f"\n  [SAFETY CAP] {len(wrongly_items)}/{audited} items flagged as wrongly killed "
                f"({false_negative_rate:.1f}%) — exceeds the {int(RECOVERY_CAP*100)}% cap."
            )
            print(
                f"  Recovery withheld. A rate this high usually means triage broke structurally."
            )
            print(f"  Fix the triage prompt, then re-run with --retriage-kills before recovering.")
        else:
            for r in wrongly_items:
                try:
                    _recover_item(
                        item_id=r["item_id"],
                        original_kill_reason=r["kill_reason"],
                        sonnet_reasoning=r["reasoning"],
                        db_path=db_path,
                    )
                    recovered += 1
                    print(
                        f"  RECOVERED: {r['title'][:75]}\n"
                        f"    Haiku killed : {r['kill_reason']}\n"
                        f"    Audit reason : {r['reasoning']}"
                    )
                except Exception as exc:
                    print(f"  [ERROR] Recovery failed for item {r['item_id']}: {exc}")

    return {
        "audited": audited,
        "correct_kills": correct,
        "wrongly_killed": len(wrongly_items),
        "false_negative_rate": false_negative_rate,
        "recovered": recovered,
        "recovery_withheld": recovery_withheld,
        "results": all_results,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from dotenv import load_dotenv
    load_dotenv()

    do_recover = "--recover" in sys.argv

    if do_recover:
        print("Running Sonnet audit of Haiku kill pile (recovery ON)...\n")
    else:
        print("Running Sonnet audit of Haiku kill pile (measure-only)...\n")
        print("  Tip: run with --recover to flip wrongly-killed items back to ESCALATE.\n")

    t0 = time.time()
    summary = run_audit(hours=24, recover=do_recover)
    elapsed = time.time() - t0

    print(f"\n-- Audit Summary ----------------------------")
    print(f"  Items audited      : {summary['audited']}")
    print(f"  Correct kills      : {summary['correct_kills']}")
    print(f"  Wrongly killed     : {summary['wrongly_killed']}")
    print(f"  False-negative rate: {summary['false_negative_rate']:.1f}%")
    if do_recover:
        if summary["recovery_withheld"]:
            print(f"  Recovered          : 0 (withheld — rate exceeded safety cap)")
        else:
            print(f"  Recovered          : {summary['recovered']}")
    print(f"  Elapsed            : {elapsed:.1f}s")

    if summary["audited"] == 0:
        sys.exit(0)

    # Calibration signal
    fnr = summary["false_negative_rate"]
    if fnr == 0.0:
        print(f"\n  [OK] No false negatives found. Haiku's kill threshold looks well-calibrated.")
    elif fnr <= 10.0:
        print(f"\n  [OK] False-negative rate {fnr:.1f}% — acceptable. Review the items below.")
    elif fnr <= 25.0:
        print(f"\n  [WARN] False-negative rate {fnr:.1f}% — Haiku is killing some real items.")
        print(f"         Review the wrongly-killed list and consider loosening the kill criteria.")
    else:
        print(f"\n  [FLAG] False-negative rate {fnr:.1f}% — Haiku threshold may be too aggressive.")
        print(f"         Strongly consider loosening the kill criteria in triage.py.")

    wrongly_killed = [r for r in summary["results"] if r["verdict"] == "WRONGLY_KILLED"]

    if not wrongly_killed:
        print(f"\n-- Wrongly Killed ---------------------------")
        print(f"  (none — kill pile looks clean)")
    else:
        label = "Wrongly Killed + Recovered" if (do_recover and not summary["recovery_withheld"]) else "Wrongly Killed (side-by-side)"
        print(f"\n-- {label} --------")
        print(f"  Each entry shows what Haiku killed and why Sonnet disagrees.\n")
        for i, r in enumerate(wrongly_killed, 1):
            recovered_tag = " [RECOVERED]" if (do_recover and not summary["recovery_withheld"]) else ""
            print(f"  [{i}]{recovered_tag} {r['title'][:85]}")
            print(f"       Haiku said  : {r['kill_reason']}")
            print(f"       Sonnet says : {r['reasoning']}")
            print()
