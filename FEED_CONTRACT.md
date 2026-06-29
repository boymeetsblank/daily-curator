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
  "key":   "moment",            // stable id; "category:<Name>" for category rails
  "kind":  "moment",            // "moment" | "top_stories" | "category"
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
| `cluster_sources`  | array \| null   | legacy multi-source list (usually null; full clustering is parked) |
| `why`              | string          | short rationale (may be empty) |
| `related_articles` | array \| null   | legacy "other angles" |

### Rules of thumb for the UI
1. If `sections` is non-empty, render rails; else render `runs` (flat).
2. The moment rail is optional — design for its absence.
3. Hero = `top_stories.items[0]`.
4. Never rewrite `title`. Real headlines only.
