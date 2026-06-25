"""
run_pipeline.py — Blank engine orchestrator.

Runs the full cascade in order:
  1. Ingest   — poll active RSS sources, dedup into DB
  2. Triage   — Haiku KILL/ESCALATE for new items
  3. Score    — Sonnet 1–10 scoring for escalated items

Each stage is wrapped so a failure in one logs cleanly and the pipeline
continues where it can (e.g. score failure still triages items from previous
runs; ingest failure still scores already-escalated items).

Git commit of blank.db is handled by blank.yml, not this script.
"""

import os
import sys
import time
import traceback
from datetime import datetime, timezone

# Load .env for local runs; no-op on Actions where env vars come from secrets
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import ingest
import triage
import score


# ---------------------------------------------------------------------------
# Stage runner
# ---------------------------------------------------------------------------

def _run_stage(name: str, fn, *args, **kwargs) -> tuple:
    """
    Execute one pipeline stage. Returns (result, elapsed_seconds, error).
    Never raises — failures are captured and returned as the error value.
    """
    print(f"\n{'─' * 52}")
    print(f"  STAGE: {name}")
    print(f"{'─' * 52}")
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        return result, time.time() - t0, None
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"  [FATAL] {name} crashed: {exc}")
        traceback.print_exc()
        return None, elapsed, exc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    started_at = datetime.now(timezone.utc)
    print(f"\nBlank Engine — {started_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 52)

    # Ensure DB schema exists. Sources are managed via sources.json import,
    # not auto-seeded here — removing seed_sources() prevents test defaults
    # from being re-activated on every run.
    db.init_db()
    print("DB initialized.")
    print()

    stage_log = {}

    # ── 1. Ingest ──────────────────────────────────────────────────────────
    result, elapsed, err = _run_stage("Ingest", ingest.poll_all_active)
    stage_log["ingest"] = (elapsed, err)
    if result:
        print(
            f"\n  Sources polled : {result['sources_polled']}"
            f"  (failed: {result['sources_failed']})"
        )
        print(
            f"  New items      : {result['total_new']}"
            f"  Skipped (dedup): {result['total_skipped']}"
        )

    # ── 1.5. Enrich OG images ─────────────────────────────────────────────
    result, elapsed, err = _run_stage("Enrich OG", ingest.enrich_og_images)
    stage_log["enrich_og"] = (elapsed, err)
    if result:
        print(f"\n  OG images found  : {result['enriched']}/{result['attempted']}")

    # ── 2. Triage ──────────────────────────────────────────────────────────
    result, elapsed, err = _run_stage("Triage", triage.run_triage)
    stage_log["triage"] = (elapsed, err)
    if result:
        print(f"\n  Triaged        : {result['total']}")
        print(f"  Escalated      : {result['escalated']}  Killed: {result['killed']}")
        print(f"  Escalation rate: {result['escalation_rate']:.1f}%")
        if result["total"] > 0 and result["escalation_rate"] < 40.0:
            print(f"  [FLAG] Escalation rate below 40% — Haiku may be over-killing.")

    # ── 3. Score ───────────────────────────────────────────────────────────
    result, elapsed, err = _run_stage("Score", score.run_scoring)
    stage_log["score"] = (elapsed, err)
    if result:
        print(f"\n  Scored         : {result['total_scored']}")
        print(f"  Skipped/errors : {result['total_skipped']}")
        print(f"  Below threshold: {result['below_threshold']}")
        dist = result.get("distribution", {})
        if dist:
            dist_line = "  ".join(
                f"{s}x{dist[s]}" for s in sorted(dist.keys(), reverse=True) if dist[s]
            )
            print(f"  Distribution   : {dist_line}")

    # ── Summary ────────────────────────────────────────────────────────────
    total_elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    print(f"\n{'=' * 52}")
    print(f"  PIPELINE COMPLETE — {total_elapsed:.1f}s")
    print(f"{'=' * 52}")
    for stage_name, (t, e) in stage_log.items():
        status = "OK" if e is None else f"FAILED ({type(e).__name__})"
        print(f"  {stage_name:<10} {t:5.1f}s  {status}")

    # Exit non-zero only if every stage crashed (partial success is still success)
    all_failed = all(e is not None for _, e in stage_log.values())
    if all_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
