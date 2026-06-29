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

The flat `runs` stream is untouched; `sections` is purely additive, so an older
PWA that ignores it keeps working.
"""

import db

# Tunables (single constants, like the rest of the engine).
TOP_STORIES_LIMIT = 6      # hero + 5
CATEGORY_MIN_ITEMS = 2     # don't show a category rail with fewer than this
MOMENT_MIN_IN_FEED = 3     # moment must have at least this many members in the feed


def _pick_key(pick: dict):
    """Stable identity for a pick — prefer item_id, fall back to link/title."""
    if pick.get("item_id") is not None:
        return ("id", pick["item_id"])
    return ("url", pick.get("link") or pick.get("title"))


def build_sections(flat_picks: list[dict], db_path: str = db.DB_PATH) -> list[dict]:
    """
    Build the rails from the ranked flat pick list. `flat_picks` is assumed to be
    already in final ranked order (as produced by the deploy-pages consolidation).
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

    # Order rails by size (most-covered category first), then name for stability.
    ordered = sorted(
        groups.items(),
        key=lambda kv: (-len(kv[1]), kv[0]),
    )
    for cat, items in ordered:
        if len(items) < CATEGORY_MIN_ITEMS:
            continue
        sections.append({
            "key": f"category:{cat}",
            "kind": "category",
            "title": cat,
            "items": items,
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
