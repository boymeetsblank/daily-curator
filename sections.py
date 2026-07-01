"""
sections.py — assemble the feed into named rails (the "sectioned" payload).

Pure data, NO LLM. Given the already-ranked flat pick list (the single source of
truth built in deploy-pages.yml) plus the active Moment from blank.db, this
produces the `sections` array the PWA renders as rails:

  - moment      : the single dominant story right now (omitted if none / too few
                  members present in the feed). Its members are pulled OUT of
                  Top Stories so the page never repeats itself.
  - top_stories : the highest-ranked items (hero = items[0]).
  - category    : remaining items grouped by primary_category (the tag produced
                  in the score pass). Non-personalized for now — niche onboarding
                  will later filter these to a user's picks.
  - catchup     : the "if you only have a minute" brief — a TOPIC-BALANCED,
                  bounded digest (round-robin across niches so it isn't a wall of
                  sports). The UI's Catch-up tab renders this, filtering to the
                  user's picked niches + windowing to "since you last opened"
                  (both client-side). Pure data, no LLM. Fixes the alpha cohort's
                  "catch-up isn't balanced or niche-aware" finding.

The flat `runs` stream is untouched; `sections` is purely additive, so an older
PWA that ignores it keeps working.
"""

import db

# Tunables (single constants, like the rest of the engine).
TOP_STORIES_LIMIT = 6      # hero + 5
CATEGORY_MIN_ITEMS = 2     # don't show a category rail with fewer than this
MOMENT_MIN_IN_FEED = 3     # moment must have at least this many members in the feed
NICHE_CAP = 40             # max items per category section (>=6 head + sub-6 tail) —
                           # bounds the payload AND gives niche drill-downs depth
CATCHUP_LIMIT = 12         # total items in the catch-up brief (UI windows/filters down)
CATCHUP_PER_CATEGORY = 3   # max per niche in the brief, so no single niche dominates


def _pick_key(pick: dict):
    """Stable identity for a pick — prefer item_id, fall back to link/title."""
    if pick.get("item_id") is not None:
        return ("id", pick["item_id"])
    return ("url", pick.get("link") or pick.get("title"))


def _build_catchup(flat_picks: list[dict]) -> list[dict]:
    """
    The topic-balanced "if you only have a minute" brief. Round-robins across
    niches (up to CATCHUP_PER_CATEGORY each) in feed-rank order, so the brief
    leads with the biggest story from the biggest-story niche, then the biggest
    from the next niche, etc. — never a wall of one topic. Input is the already-
    ranked + cluster-collapsed flat feed, so it's deduped and high-signal by
    construction. Returns up to CATCHUP_LIMIT picks (or [] if nothing to brief).

    The engine can't know a user's picked niches or their last-open time (no
    accounts), so it emits a balanced SUPERSET across all niches; the UI filters
    to the user's niches and windows to "since you last opened" client-side.
    """
    groups: dict[str, list] = {}
    cat_order: list[str] = []          # niche first-appearance order == rank order
    for p in flat_picks:
        cat = (p.get("primary_category") or "").strip()
        if not cat or cat == "Other":
            continue
        if cat not in groups:
            groups[cat] = []
            cat_order.append(cat)
        groups[cat].append(p)

    brief: list[dict] = []
    for rank in range(CATCHUP_PER_CATEGORY):
        for cat in cat_order:
            items = groups[cat]
            if rank < len(items):
                brief.append(items[rank])
                if len(brief) >= CATCHUP_LIMIT:
                    return brief
    return brief


def build_sections(flat_picks: list[dict], db_path: str = db.DB_PATH,
                   deep_picks: list[dict] | None = None) -> list[dict]:
    """
    Build the rails from the ranked flat pick list. `flat_picks` is assumed to be
    already in final ranked order (as produced by the deploy-pages consolidation).

    `deep_picks` (optional) is a ranked list of scored-but-sub-6 items used to give
    the per-niche drill-downs depth (the "rank, don't hide" surface). They are
    appended ONLY to the matching `category` sections (after the >=6 head, so feed
    previews that take the top N stay clean) — never to `top_stories` or the flat
    feed. Each category section is capped at NICHE_CAP to bound the payload.

    Returns a list of section dicts.
    """
    sections: list[dict] = []
    moment_keys: set = set()

    # ── Moment rail ─────────────────────────────────────────────────────────
    try:
        active = db.get_active_moment(db_path)
    except Exception:
        active = None

    if active and active.get("item_ids"):
        member_ids = set(active["item_ids"])
        members = [p for p in flat_picks if p.get("item_id") in member_ids]
        if len(members) >= MOMENT_MIN_IN_FEED:
            # members preserve flat (ranked) order; items[0] is the lead
            sections.append({
                "key": "moment",
                "kind": "moment",
                "title": active["label"],
                "items": members,
            })
            moment_keys = {_pick_key(p) for p in members}

    # Everything below excludes the moment members so the page never repeats.
    remaining = [p for p in flat_picks if _pick_key(p) not in moment_keys]

    # ── Top Stories rail ────────────────────────────────────────────────────
    top = remaining[:TOP_STORIES_LIMIT]
    if top:
        sections.append({
            "key": "top_stories",
            "kind": "top_stories",
            "title": "Top Stories",
            "items": top,
        })

    # ── Category rails ──────────────────────────────────────────────────────
    # Group ALL remaining items by primary_category (not just the post-top tail)
    # so each category rail is complete; the UI decides how to handle overlap
    # with Top Stories. Items keep ranked order within each category.
    groups: dict[str, list] = {}
    for p in remaining:
        cat = (p.get("primary_category") or "").strip()
        if not cat or cat == "Other":
            continue
        groups.setdefault(cat, []).append(p)

    # Deep sub-6 tail per category (drill-down depth), de-duped against the feed
    # and the moment. Appended AFTER the >=6 head, so it sinks to the bottom of the
    # niche page and never reaches a top-N preview.
    deep_by_cat: dict[str, list] = {}
    if deep_picks:
        feed_keys = {_pick_key(p) for p in flat_picks}
        for p in deep_picks:
            k = _pick_key(p)
            if k in moment_keys or k in feed_keys:
                continue
            cat = (p.get("primary_category") or "").strip()
            if not cat or cat == "Other":
                continue
            deep_by_cat.setdefault(cat, []).append(p)

    # Order rails by size (most-covered category first), then name for stability.
    ordered = sorted(
        groups.items(),
        key=lambda kv: (-len(kv[1]), kv[0]),
    )
    for cat, items in ordered:
        if len(items) < CATEGORY_MIN_ITEMS:
            continue
        full = (items + deep_by_cat.get(cat, []))[:NICHE_CAP]
        sections.append({
            "key": f"category:{cat}",
            "kind": "category",
            "title": cat,
            "items": full,
        })

    # ── Catch-up brief ──────────────────────────────────────────────────────
    # Topic-balanced digest built from the full ranked feed (NOT `remaining`, so
    # the brief can include the moment/top stories — it's a separate surface).
    catchup = _build_catchup(flat_picks)
    if catchup:
        sections.append({
            "key": "catchup",
            "kind": "catchup",
            "title": "Catch-up",
            "items": catchup,
        })

    return sections


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    from datetime import datetime, timezone

    TEST_DB = "sections_test.db"
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    db.init_db(TEST_DB)

    # Fake ranked feed: 3 Iran items (the moment) + a spread of others.
    flat = [
        {"item_id": 1, "title": "Iran A", "link": "u1", "score": 9, "primary_category": "World / International"},
        {"item_id": 2, "title": "Iran B", "link": "u2", "score": 8, "primary_category": "World / International"},
        {"item_id": 3, "title": "Iran C", "link": "u3", "score": 8, "primary_category": "Politics & Policy"},
        {"item_id": 4, "title": "AI chip", "link": "u4", "score": 8, "primary_category": "Technology & AI"},
        {"item_id": 5, "title": "AI model", "link": "u5", "score": 7, "primary_category": "Technology & AI"},
        {"item_id": 6, "title": "Game review", "link": "u6", "score": 7, "primary_category": "Gaming"},
        {"item_id": 7, "title": "Misc", "link": "u7", "score": 6, "primary_category": "Other"},
        {"item_id": 8, "title": "No cat", "link": "u8", "score": 6, "primary_category": None},
    ]

    # No moment yet → no moment rail; top_stories + category rails only.
    secs = build_sections(flat, TEST_DB)
    kinds = [s["kind"] for s in secs]
    assert "moment" not in kinds, "no moment expected before one is recorded"
    assert kinds[0] == "top_stories"
    assert secs[0]["items"][0]["item_id"] == 1, "hero should be the top-ranked item"
    cat_titles = [s["title"] for s in secs if s["kind"] == "category"]
    assert "Technology & AI" in cat_titles and "World / International" in cat_titles
    assert "Other" not in cat_titles, "Other is excluded from category rails"
    assert "Gaming" not in cat_titles, "single-item category dropped (min 2)"
    print(f"No-moment: {len(secs)} sections, categories={cat_titles}  OK")

    # Catch-up brief: topic-balanced round-robin — first items span distinct
    # niches (not a wall of one topic), and thin niches (Gaming, dropped from the
    # category rails at min-2) still get represented.
    cu = next(s for s in secs if s["kind"] == "catchup")
    first_cats = [p.get("primary_category") for p in cu["items"][:4]]
    assert len(set(first_cats)) == 4, f"catch-up should lead with 4 distinct niches, got {first_cats}"
    cu_cats = {p.get("primary_category") for p in cu["items"]}
    assert "Gaming" in cu_cats, "thin niche (Gaming) should still appear in the balanced brief"
    assert all((p.get("primary_category") or "") not in ("", "Other") for p in cu["items"]), \
        "catch-up excludes Other/untagged"
    assert len(cu["items"]) <= CATCHUP_LIMIT
    print(f"Catch-up brief: {len(cu['items'])} items, balanced across {len(cu_cats)} niches  OK")

    # Deep sub-6 tail → appended to matching category AFTER the >=6 head (so a
    # top-N preview stays clean), capped at NICHE_CAP.
    deep = [
        {"item_id": 101, "title": "AI deep 1", "link": "d1", "score": 5, "primary_category": "Technology & AI"},
        {"item_id": 102, "title": "AI deep 2", "link": "d2", "score": 4, "primary_category": "Technology & AI"},
    ]
    secs_d = build_sections(flat, TEST_DB, deep_picks=deep)
    tech = next(s for s in secs_d if s["title"] == "Technology & AI")
    ids = [p["item_id"] for p in tech["items"]]
    assert ids[:2] == [4, 5], "the >=6 head must stay first (preview stays clean)"
    assert 101 in ids and 102 in ids, "deep sub-6 items should append to the niche"
    assert ids.index(101) >= 2 and ids.index(102) >= 2, "deep items go after the >=6 head"
    print(f"Deep tail: Technology & AI now {len(tech['items'])} items (head + sub-6)  OK")

    # Record a moment over the 3 Iran items.
    db.record_moment(label="US-Iran Escalation", item_ids=[1, 2, 3], db_path=TEST_DB)
    secs = build_sections(flat, TEST_DB)
    assert secs[0]["kind"] == "moment", "moment rail should lead"
    assert secs[0]["title"] == "US-Iran Escalation"
    assert [p["item_id"] for p in secs[0]["items"]] == [1, 2, 3]
    # Moment members must be absent from Top Stories.
    top = next(s for s in secs if s["kind"] == "top_stories")
    assert all(p["item_id"] not in {1, 2, 3} for p in top["items"]), "moment items leaked into Top Stories"
    print(f"With moment: lead='{secs[0]['title']}' ({len(secs[0]['items'])} items), "
          f"top_stories has {len(top['items'])} items  OK")

    # Moment with too few members present in feed → no moment rail.
    db.record_moment(label="Thin Story", item_ids=[1, 999], db_path=TEST_DB)
    secs = build_sections(flat, TEST_DB)
    assert secs[0]["kind"] != "moment", "moment with <3 in-feed members should be suppressed"
    print("Thin moment suppressed  OK")

    import gc
    gc.collect()
    os.remove(TEST_DB)
    print("\nAll section checks passed. sections_test.db cleaned up.")
