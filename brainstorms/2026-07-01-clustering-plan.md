# Plan — Real multi-source clustering (`cluster.py`)

**Date:** 2026-07-01
**Owner:** Engine agent
**Status:** Approach locked (deterministic, zero-LLM) — not yet built
**Motivation:** The 10-persona alpha cohort's #1 finding — the feed served the same
LeBron story 6–11× as separate cards. Verified: the live payload ships every item with
`cluster_size: 1`, `cluster_sources: null`, `related_articles: null`. The renderer
(`index.html clusterBlock()`) is built and waiting; the engine never fills the fields.

## Hard constraint (founder): NO cost increase

Clustering must add **zero** recurring LLM/API spend. This is binding and it drives the
approach choice below. Anything with a per-run API call — a Haiku clustering pass *or*
embeddings (Voyage/OpenAI) — is rejected on this basis, however cheap per call.

---

## Approach (LOCKED): deterministic entity-anchored lexical clustering

Cluster in **pure Python, no API calls**. For each candidate window (scored, feed-eligible,
last 48h — ~200 items), group items that report the same event using signals we already
have in `blank.db`:

1. **Block** by `primary_category` + 48h window (only compare items in the same niche and
   time frame — already tagged, cuts the comparison space and prevents cross-topic merges).
2. **Entity anchor (required):** two items can only merge if they share ≥1 salient
   named entity — a multi-word proper noun / capitalized phrase extracted from the title
   (e.g. "LeBron James", "Los Angeles Lakers", "Microsoft"). This is the "same subject"
   gate.
3. **Lexical similarity (required, on top of the anchor):** TF-IDF cosine (or token-set
   Jaccard) over normalized title+description above a **conservative threshold**. This is
   the "same event, not just same subject" gate — it keeps a *LeBron injury* story and a
   *LeBron trade* story apart even though both share the "LeBron James" entity.
4. **Union-find** over the surviving pairs → clusters. Singletons stay singletons.
5. **Canonical lead:** highest score, tiebreak toward the item that *has an image* (fixes
   the cohort's gray-hero finding), then decayed_rank. **Never rewrite the headline.**

Why this is the right call under the no-cost constraint:

- **$0 marginal cost, forever.** No API, no tokens, no vendor, no new secret. Cost cannot
  increase because there is nothing metered.
- **"Won't break" — strongest option on this axis.** No API to fail, no rate limits, no
  JSON parse failures, no run-to-run non-determinism. Same input → same clusters, every
  time. Failure mode is *tunable clustering quality*, testable fully offline on a
  `blank.db` copy — not a production outage.
- **Dedups the trust-killer properly.** The cohort's damage was *many outlets running the
  near-same headline on one event* (ESPN/CBS/Complex/r-sports all "LeBron … Lakers"). That
  pattern has high entity + token overlap — exactly what this catches.
- **Conservative by construction.** Requiring BOTH an entity anchor AND lexical similarity
  above a tight threshold biases hard toward *not* merging. A missed merge just shows one
  extra card (safe); a wrong merge misattributes sources (the thing to avoid).

**Honest tradeoff:** deterministic matching will *not* catch the semantic-paraphrase tail
where the same event is written with almost no shared words (e.g. "LeBron leaves Lakers"
vs. "James signs with the Knicks"). That's the minority case and the *safe* direction to
miss. If we ever want it caught, see "Free / paid upgrades" below — but neither is needed
now, and both are additive later without reworking this.

### Moment-seeding (CORE — this is what makes zero-cost effective)

`moment.py` already runs every cycle and already identifies the members of the single
biggest story (LLM-grade grouping, including paraphrase variants) — that mega-cluster is
**already paid for**. We seed the #1 cluster from the active moment, then deterministic
clustering handles everything else. Net result: **LLM-quality clustering on the highest-
visibility event (free) + strong lexical clustering on the long tail (free).** The most
damaging duplication (the LeBron/World Cup–scale event splashed across the top of the feed)
gets the best method at no added cost; the tail gets the safe method.

### Paid upgrade (only if the founder later lifts the cost constraint)

Add a Haiku adjudication pass (or embeddings) for the semantic-paraphrase tail *below* the
#1 story. Drop-in addition — no rework of the above. Explicitly out of scope now, and we
measure before proposing it.

---

## The engine→UI contract (already built in `index.html`)

`clusterBlock(p)` (index.html:730) reads three fields per feed item. The engine fills them:

| Field | Type | Meaning |
|---|---|---|
| `cluster_size` | int | number of members (1 = singleton, no cluster UI) |
| `cluster_sources` | string[] | distinct source names among members ("Covered by ESPN, CBS +8") |
| `related_articles` | `{title, url, source}[]` | the non-lead members (the expand-drawer rows) |

---

## Design

### New stage `cluster.py` (after Score/backfill in `run_pipeline.py`)

Pull the candidate window → block by category+window → entity-anchor + TF-IDF pairs →
union-find → pick lead → persist. Pure functions, fully unit-testable, no network.

### Schema — new `clusters` table (mirrors the `moments` pattern)

```
clusters(
  id INTEGER PK,
  canonical_item_id INTEGER,   -- the lead (real headline shown in the feed)
  label TEXT,                  -- derived from the lead title / shared entities (no LLM)
  member_ids TEXT,             -- JSON array of items.id (includes the lead)
  content_key TEXT,            -- stable id = lead's content_hash (see stability below)
  updated_at TEXT
)
```

### The two hard parts (where this lives or dies)

1. **Cross-run stability.** The feed re-clusters every 10 min. Cluster identity must be
   durable — key a cluster to its lead's `content_hash` (`content_key`) and have a new
   item *join* the existing cluster of the item it matches, rather than re-forming from
   scratch. Without this the "Covered by…" card churns every render. (Deterministic
   matching helps here: same items always produce the same grouping, so drift only comes
   from genuinely new items, not from model noise.)
2. **Feed-collapse is the actual dedup — not the payload fields.** `get_feed` /
   `deploy-pages.yml` must rank each cluster *once* (by its lead) and **drop members from
   the top-level list**, attaching them as `related_articles` on the lead. Filling
   `cluster_sources` alone changes nothing — all 11 still rank independently.

### Payload wiring (`deploy-pages.yml` + `sections.py`)

Today lines ~261–267 hardcode `cluster_size: 1`, `cluster_sources: None`,
`related_articles: None` for blank.db items. Replace with a lookup into the `clusters`
table: for each lead, `cluster_size = len(member_ids)`, `cluster_sources = distinct source
names`, `related_articles = [{title, url, source} for each non-lead member]`. Suppress
member item_ids from the flat feed + Top Stories. `sections.py` niche rails inherit the
collapsed list.

---

## Cost

**Zero.** No API calls in the clustering path. TF-IDF/union-find run in-process during the
existing engine cycle (a few CPU-seconds over ~200 items). No tokens, no vendor, no secret,
nothing metered — cost cannot rise. Fully consistent with global-score-once (and stricter:
it adds no per-run spend at all).

---

## Verification plan

- Run `cluster.py` on a **copy** of `blank.db` (never the authoritative file).
- Confirm the known LeBron ×11 case collapses to one cluster with ~11 sources, and that
  distinct same-subject events (a Lakers trade vs. a Lakers injury) do **not** merge —
  this is the threshold-tuning target.
- Small labeled spot-check (~50 items) measuring **precision** (wrong merges — the
  dangerous direction) first, then recall.
- Confirm payload: lead carries populated `cluster_size`/`cluster_sources`/
  `related_articles`; members absent from the flat list; JSON serializable; blank.db
  unmutated.
- Because it's deterministic, the same fixture reproduces exactly — check thresholds into
  the repo as a regression test.

## Ownership

Engine-owned: `cluster.py`, `db.py` (clusters table), `run_pipeline.py`, `sections.py`,
`deploy-pages.yml`. **Do not edit `index.html`** — the `clusterBlock()` contract is fixed;
confirm field shape with the UI agent before finalizing.

## Sequence

1. `clusters` table + `cluster.py` stage (entity-anchor + TF-IDF + union-find, conservative
   threshold) + cross-run stability. Pure Python, unit-tested offline.
2. Tune the threshold on a `blank.db` copy against the LeBron case (precision-first).
3. Feed-collapse in `get_feed` / `deploy-pages.yml` (suppress members, attach
   `related_articles`) — the change that actually kills the duplicate cards.
4. (Optional, free) seed the #1 cluster from the active moment.
5. Verify end-to-end on a copy; ship; watch precision in logs.
