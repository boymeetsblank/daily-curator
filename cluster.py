"""
cluster.py — deterministic multi-source story clustering for the Blank engine.

Groups same-event items across sources into one cluster, picks one REAL headline
as the lead, and records the grouping so the feed builder can collapse members
into the lead ("Covered by ESPN, CBS +8 more"). No rewritten headlines.

Design (see brainstorms/2026-07-01-clustering-plan.md):
- ZERO API cost. Pure Python — TF-IDF/Jaccard + union-find. No LLM, no vendor,
  no secret, nothing metered. Runs in a few CPU-seconds over the feed window.
- Deterministic: same items -> same clusters every run, so cluster identity is
  stable across runs (no churn) without any prior-run "adopt" bookkeeping. The
  stable id is content_key = the lead's content_hash.
- CONSERVATIVE by construction: two items merge only if they share a STRONG named
  entity (proper noun, excluding months/days/generic words) AND their titles
  clear a tight word-Jaccard threshold. A missed merge just shows one extra card
  (safe); a wrong merge misattributes sources (the thing to avoid).
- Global, once per run — scores the same feed for all users (respects the
  global-score-once cost rule; adds no per-run API spend at all).
- Graceful no-op: any failure leaves the feed as singletons rather than erroring.

Calibrated on real blank.db data 2026-07-01: cleanly clusters the multi-outlet
duplicates (Gene Wilder AI x4, Ja Morant trade x3, Rocket Lab x3, Supreme Court,
Microsoft layoffs, LeBron) while keeping distinct same-subject events apart
(Nissan vs Toyota sales; Goggins/stampede vs Goggins/Strokes-video).
"""

import html
import re
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

import db

# ---------------------------------------------------------------------------
# Tunables (single source of truth)
# ---------------------------------------------------------------------------
MIN_SCORE = 6          # only cluster feed-eligible items (matches the feed threshold)
WINDOW_HOURS = 48      # candidate window (matches the feed window)
# Title word-overlap gate. Tuned on real blank.db data (2026-07-01): 0.42 is the
# balance point — it merges the true multi-outlet dupes (and unifies e.g. the whole
# Supreme Court ruling) while the STRONG-entity anchor holds precision. Lower (~0.40)
# dedups a bit more but starts admitting "same topic, different story" merges (two
# different World Cup pieces); higher (~0.45) is stricter but splits some real dupes.
WORD_JACCARD_THRESHOLD = 0.42

# Capitalized tokens that are NOT salient entities — never anchor a merge on these.
# (Months/weekdays are the key false-merge fix: "...sales fall in May" templates.)
_MONTHS = {"january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"}
_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
_GENERIC_CAPS = {
    "the", "new", "report", "breaking", "watch", "video", "first", "how", "why",
    "what", "update", "live", "exclusive", "best", "top", "day", "week", "year",
    "us", "america", "american", "said", "says", "this", "that", "here", "amid",
}
# Common words dropped from the title token set before computing Jaccard.
_STOPWORDS = _MONTHS | _DAYS | _GENERIC_CAPS | {
    "a", "an", "to", "of", "in", "on", "for", "and", "is", "at", "with", "as",
    "by", "from", "after", "its", "up", "over", "into", "out", "his", "her",
    "are", "be", "will", "has", "have", "was", "were", "it", "he", "she", "they",
}


# ---------------------------------------------------------------------------
# Text normalization + feature extraction (pure functions)
# ---------------------------------------------------------------------------

def normalize_title(t: Optional[str]) -> str:
    """Decode HTML entities, drop mojibake replacement chars, unify apostrophes."""
    t = html.unescape(t or "")
    t = t.replace("�", "").replace("’", "'").replace("‘", "'")
    return t


def extract_entities(title: str) -> set:
    """
    Salient named entities = capitalized proper-noun tokens (len > 2), lowercased,
    excluding months/weekdays/generic capitalized words. Possessive 's is stripped
    ("Nissan's" -> "nissan"). This is the "same subject" gate.
    """
    out = set()
    for tok in re.findall(r"[A-Z][a-zA-Z0-9]+(?:'s)?", title):
        w = tok[:-2] if tok.endswith("'s") else tok
        wl = w.lower()
        if len(w) > 2 and wl not in _STOPWORDS:
            out.add(wl)
    return out


def tokenize(title: str) -> set:
    """Lowercased word set minus stopwords — the basis for the Jaccard gate."""
    return set(re.findall(r"[a-z0-9]+", title.lower())) - _STOPWORDS


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _same_event(a: dict, b: dict) -> bool:
    """Merge iff a STRONG entity is shared AND title word-Jaccard clears threshold."""
    if not (a["_ent"] & b["_ent"]):
        return False
    return _jaccard(a["_wrd"], b["_wrd"]) >= WORD_JACCARD_THRESHOLD


# ---------------------------------------------------------------------------
# Clustering (union-find over the candidate window)
# ---------------------------------------------------------------------------

def cluster_items(items: list[dict]) -> list[list[dict]]:
    """
    Group items into same-event clusters. Input dicts need at least 'id' and
    'title'; this annotates each with _nt/_ent/_wrd. Returns a list of clusters
    (lists of the input dicts); singletons are included as 1-item lists. All-pairs
    over the window (n ~ a few hundred to ~1500 -> trivial CPU).
    """
    for it in items:
        nt = normalize_title(it.get("title"))
        it["_nt"] = nt
        it["_ent"] = extract_entities(nt)
        it["_wrd"] = tokenize(nt)

    parent = {it["id"]: it["id"] for it in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    n = len(items)
    for i in range(n):
        a = items[i]
        for j in range(i + 1, n):
            b = items[j]
            if find(a["id"]) == find(b["id"]):
                continue
            if _same_event(a, b):
                parent[find(a["id"])] = find(b["id"])

    groups: dict = {}
    for it in items:
        groups.setdefault(find(it["id"]), []).append(it)
    return list(groups.values())


def pick_lead(cluster: list[dict]) -> dict:
    """
    Canonical lead = highest score, tiebreak toward an item that HAS an image
    (fixes gray-hero cards when multiple sources cover a story), then recency,
    then id for determinism. Never rewrites the headline — the lead's real title
    is what the feed shows.
    """
    def key(it):
        has_img = 1 if (it.get("image_url") or "").strip() else 0
        ts = it.get("published_at") or it.get("fetched_at") or ""
        return (it.get("score") or 0, has_img, ts, -int(it["id"]))
    return max(cluster, key=key)


def _label_for(lead: dict) -> str:
    """Short debug/Moment-reuse label — the lead's normalized title (not user-facing)."""
    return (lead.get("_nt") or normalize_title(lead.get("title")))[:120]


# ---------------------------------------------------------------------------
# Candidate pull + main stage
# ---------------------------------------------------------------------------

def _get_candidates(db_path: str) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)).isoformat()
    with db._conn(db_path) as con:
        rows = con.execute(
            """
            SELECT i.id, i.title, i.image_url, i.content_hash,
                   i.published_at, i.fetched_at,
                   s.score, s.primary_category,
                   src.name AS source_name
            FROM scores s
            JOIN items i   ON i.id  = s.item_id
            JOIN sources src ON src.id = i.source_id
            WHERE s.score >= ?
              AND i.fetched_at >= ?
            """,
            (MIN_SCORE, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]


def run_clustering(db_path: str = db.DB_PATH) -> dict:
    """
    Cluster the current feed window and persist the active cluster set.
    Returns {"clusters": int, "collapsed": int, "candidates": int, "skipped": bool}.
    Never raises — on any failure it leaves the feed as singletons.
    """
    try:
        items = _get_candidates(db_path)
    except Exception as exc:
        print(f"  [ERROR] cluster candidate pull failed: {exc} — skipping.")
        return {"clusters": 0, "collapsed": 0, "candidates": 0, "skipped": True}

    if len(items) < 2:
        db.replace_clusters([], db_path=db_path)
        return {"clusters": 0, "collapsed": 0, "candidates": len(items), "skipped": False}

    try:
        groups = cluster_items(items)
    except Exception as exc:
        print(f"  [ERROR] clustering failed: {exc} — leaving feed as singletons.")
        return {"clusters": 0, "collapsed": 0, "candidates": len(items), "skipped": True}

    records = []
    collapsed = 0
    for g in groups:
        if len(g) < 2:
            continue
        lead = pick_lead(g)
        member_ids = [lead["id"]] + [it["id"] for it in g if it["id"] != lead["id"]]
        records.append({
            "canonical_item_id": lead["id"],
            "member_ids": member_ids,
            "label": _label_for(lead),
            "content_key": lead.get("content_hash") or "",
        })
        collapsed += len(g) - 1

    written = db.replace_clusters(records, db_path=db_path)
    print(f"  Clusters: {written} multi-source stories, {collapsed} duplicate cards collapsed "
          f"(feed {len(items)} -> {len(items) - collapsed} cards).")
    return {"clusters": written, "collapsed": collapsed, "candidates": len(items), "skipped": False}


# ---------------------------------------------------------------------------
# Self-test + live run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # --- Offline unit checks (no DB, no network) ------------------------------
    assert extract_entities("Nissan's global sales fall 10% in May") == {"nissan"}, \
        "months/possessive handling"
    assert extract_entities("Toyota's global vehicle sales fall 6.4% in May") == {"toyota"}
    # Same subject, different event -> different entities OR low overlap -> no merge
    a = {"id": 1, "title": "Nissan's global sales fall 10% in May"}
    b = {"id": 2, "title": "Toyota's global vehicle sales fall 6.4% in May"}
    groups = cluster_items([dict(a), dict(b)])
    assert all(len(g) == 1 for g in groups), "Nissan/Toyota must NOT merge"
    # True multi-outlet dupe -> merges
    c1 = {"id": 3, "title": "Rocket Lab to take on SpaceX's Starlink with $8 billion acquisition"}
    c2 = {"id": 4, "title": "Rocket Lab buys Iridium in $8 billion deal to take on SpaceX"}
    groups = cluster_items([dict(c1), dict(c2)])
    assert any(len(g) == 2 for g in groups), "Rocket Lab dupes must merge"
    # Lead prefers higher score, then image
    lead = pick_lead([
        {"id": 5, "title": "x", "score": 8, "image_url": None},
        {"id": 6, "title": "x", "score": 9, "image_url": None},
        {"id": 7, "title": "x", "score": 9, "image_url": "http://img"},
    ])
    assert lead["id"] == 7, "lead should be the score-9 item WITH an image"
    print("Offline checks passed (entity extraction, false-merge guard, merge, lead pick).")

    # --- Live run against a COPY of the real DB -------------------------------
    import os, shutil, gc, time
    if not os.path.exists(db.DB_PATH):
        print(f"\nNo {db.DB_PATH} present — skipping live run.")
        sys.exit(0)

    LIVE_COPY = "cluster_live_test.db"
    shutil.copyfile(db.DB_PATH, LIVE_COPY)
    db.init_db(LIVE_COPY)  # ensure the clusters table exists on the copy

    print(f"\nRunning live clustering against a copy of {db.DB_PATH}...")
    t0 = time.time()
    result = run_clustering(LIVE_COPY)
    print(f"Result: {result}  ({time.time() - t0:.2f}s)")

    active = db.get_active_clusters(LIVE_COPY)
    print(f"\nTop clusters by size:")
    for c in sorted(active, key=lambda c: -len(c["member_ids"]))[:12]:
        print(f"  size {len(c['member_ids'])}: {c['label'][:78]}")

    gc.collect()
    os.remove(LIVE_COPY)
