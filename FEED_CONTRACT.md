# Feed Contract — `picks_data.json`

The live feed reads `picks_data.json` (built by `.github/workflows/deploy-pages.yml`
from `blank.db`). This documents the shape the **UI/PWA renders against**. It is the
hand-off boundary between the engine (produces this JSON) and the frontend (renders it).

```jsonc
{
  "runs":        [ /* legacy flat stream — unchanged, still the fallback */ ],
  "sections":    [ /* NEW: named rails — render these */ ],
  "generated_at": "2026-06-29T03:55:00Z"
}
```

## `runs` (flat stream — unchanged)
A single ranked run whose `picks` array is the whole feed in final `decayed_rank`
order. This is the **fallback**: if `sections` is empty/absent, render `runs` as the
flat list (today's behavior). Do **not** remove this path.

## `sections` (the rails — new)
An **ordered** array of rails. Render them top-to-bottom in the given order. Each rail:

```jsonc
{
  "key":   "moment",            // stable id; "category:<Name>" for category rails; "catchup"
  "kind":  "moment",            // "moment" | "top_stories" | "category" | "catchup"
  "title": "US-Iran Escalation",// display title (the moment's name, "Top Stories", or category name)
  "items": [ /* pick objects, already in ranked order */ ]
}
```

`sections` may be **empty** (e.g. a build before the engine's next migration, or an
assembly failure) — in that case fall back to `runs`.

### Rail kinds
- **`moment`** — the single biggest thing the world is following right now: a
  sustained mega-event (e.g. the FIFA World Cup, the Olympics, an election) or a
  major breaking event. **May be absent** (when no single event dominates — that's
  normal, not an error). When present it is **first**. `items[0]` is the lead story;
  the rest are supporting coverage of the same event (up to 12). Give it a visually
  distinct treatment (this is the Apple-News "moment" rail). Its items are
  **excluded from Top Stories**, so you will never double-show them.
- **`top_stories`** — the highest-ranked items (up to 6). Treat **`items[0]` as the
  hero card**; the rest as a grid/list. Always present when there are any picks.
- **`category`** — items grouped by `primary_category` (e.g. "Technology & AI",
  "Sports"). Ordered by size (most-covered first). Non-personalized for now; niche
  onboarding will later filter these to the user's chosen niches. Coverage grows as
  the score pass tags more items, so expect these to be sparse at first.
- **`catchup`** — the **"if you only have a minute" brief** for the Catch-up tab:
  a **topic-balanced, bounded digest** (≤12 items), round-robined across niches so
  it's one-per-niche, not a wall of one topic (leads with the biggest story from the
  biggest-story niche, then the next niche, etc.). Already deduped (cluster leads
  only) and high-signal (ranked). **The engine can't know the user's picked niches
  or last-open time (no accounts), so this is a balanced SUPERSET — the UI should:**
  (a) **filter to the user's picked niches** (`blank.niches` localStorage, same as
  the feed), (b) **window to "since you last opened"** (a `lastOpen` localStorage
  timestamp vs each item's `published_at`), then (c) render the handful that remain
  with the **"you're all caught up" closure beat** when the window is empty/read.
  May be absent if nothing is tagged. This replaces the old `renderCatchup()` (top-8
  by score — which showed a wall of sports).

### Item shape (same object used everywhere — `runs` picks and `sections` items)
| field              | type            | notes |
|--------------------|-----------------|-------|
| `title`            | string          | the **real** headline — never rewritten |
| `source`           | string          | publication/source name |
| `link`             | string          | article URL |
| `image`            | string \| null  | `og:image` thumbnail if available |
| `score`            | int (1–10)      | editorial score |
| `primary_category` | string \| null  | one of `score.CATEGORIES`; null for legacy/untagged items |
| `item_id`          | int \| null     | `blank.db` item id; null for legacy picks |
| `trend_label`      | string \| null  | legacy trend annotation (usually null now) |
| `published_at`     | string \| null  | ISO timestamp — use for the Catch-up "since you last opened" window |
| `cluster_size`     | int             | # of sources covering this story (1 = singleton). **>1 → a collapsed cluster** |
| `cluster_sources`  | array \| null   | distinct source names covering the story (lead first) — render "Covered by X, Y +N" |
| `related_articles` | array \| null   | the other sources' articles: `[{title, url, source}]` — the cluster drawer rows |
| `why`              | string          | short rationale (may be empty) |

### Rules of thumb for the UI
1. If `sections` is non-empty, render rails; else render `runs` (flat).
2. The moment rail is optional — design for its absence.
3. Hero = `top_stories.items[0]`.
4. Never rewrite `title`. Real headlines only.
5. **Clustering is live:** duplicate stories are already collapsed engine-side — the
   feed shows one lead card per event, with members folded onto it. When
   `cluster_size > 1`, light up the "Covered by …" drawer from `cluster_sources` +
   `related_articles` (the `clusterBlock()` renderer already does this). You will
   **not** see the same event as separate cards anymore.
6. **Catch-up tab** renders the `catchup` section (not `visiblePicks()`): filter to
   picked niches → window to `lastOpen` → show the remainder, with a "you're all
   caught up" beat when empty. See the `catchup` rail kind above.
