"""
publish.py — Static site publisher for the Blank continuous curation engine.

Reads the scored feed from blank.db and generates a self-contained index.html.
By default: detects the Pages setup, reports findings, and asks for confirmation
before writing anything. Use --no-push to preview locally without committing.

Flags:
  --no-push    Generate HTML and write to target, print path — do NOT commit/push.
  --confirm    Skip the interactive confirmation prompt and proceed directly.
  --out PATH   Override the output file path (e.g. --out preview.html).
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import db

FEED_THRESHOLD = 6
FEED_LIMIT = 50

# ---------------------------------------------------------------------------
# Pages setup detection
# ---------------------------------------------------------------------------

def detect_pages_setup() -> dict:
    """
    Inspect the repo to determine how GitHub Pages is deployed and where
    to write the output HTML. Returns a dict describing the findings.
    """
    root = os.path.dirname(os.path.abspath(__file__))
    findings = {
        "root": root,
        "method": None,         # "actions" | "docs" | "root" | "unknown"
        "source_file": None,    # current index.html path if it exists
        "target": None,         # recommended output path
        "notes": [],
    }

    has_actions_deploy = os.path.exists(
        os.path.join(root, ".github", "workflows", "deploy-pages.yml")
    )
    has_docs_dir = os.path.isdir(os.path.join(root, "docs"))
    has_root_index = os.path.exists(os.path.join(root, "index.html"))

    if has_actions_deploy:
        findings["method"] = "actions"
        findings["notes"].append(
            "deploy-pages.yml found — Pages is deployed via GitHub Actions."
        )
        findings["notes"].append(
            "The workflow copies index.html from the repo root into a site/ "
            "directory, then uploads site/ as the Pages artifact."
        )
        if has_root_index:
            findings["source_file"] = os.path.join(root, "index.html")
            findings["notes"].append(
                "index.html exists in the repo root. Writing here will replace "
                "the existing feed on the next push to main."
            )
        findings["target"] = os.path.join(root, "index.html")

    elif has_docs_dir:
        findings["method"] = "docs"
        findings["notes"].append(
            "No Actions deploy workflow found, but a docs/ directory exists — "
            "Pages is likely configured to serve from docs/."
        )
        findings["target"] = os.path.join(root, "docs", "index.html")
        if os.path.exists(findings["target"]):
            findings["source_file"] = findings["target"]

    elif has_root_index:
        findings["method"] = "root"
        findings["notes"].append(
            "No Actions workflow or docs/ found. index.html exists at root — "
            "Pages is likely configured to serve from the root of main."
        )
        findings["source_file"] = os.path.join(root, "index.html")
        findings["target"] = findings["source_file"]

    else:
        findings["method"] = "unknown"
        findings["notes"].append(
            "Could not determine Pages setup. No deploy workflow, docs/ folder, "
            "or existing index.html found."
        )
        findings["target"] = os.path.join(root, "index.html")

    return findings


def print_detection(findings: dict) -> None:
    print("-- Pages Setup Detection --------------------")
    for note in findings["notes"]:
        print(f"  {note}")
    print(f"\n  Method : {findings['method']}")
    print(f"  Target : {findings['target']}")
    if findings["source_file"]:
        print(f"  Exists : YES — will be overwritten")
    else:
        print(f"  Exists : NO — will be created")


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """Minimal HTML escaping for text content."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _score_label(score: int) -> str:
    if score >= 9:
        return "essential"
    if score >= 8:
        return "strong"
    if score == 7:
        return "solid"
    return "notable"


def generate_html(items: list[dict]) -> str:
    """
    Build a self-contained static HTML page from a list of scored feed items.
    All CSS is inline. No external dependencies, no JS framework.
    Matches Blank aesthetic: system font, 1px borders, no gradients.
    """
    now = datetime.now(timezone.utc)
    updated = f"{now.strftime('%B')} {now.day}, {now.year} at {now.strftime('%I').lstrip('0') or '12'}:{now.strftime('%M %p')} UTC"
    item_count = len(items)

    # Score distribution for the header bar
    dist = {}
    for item in items:
        s = item.get("score", 0)
        dist[s] = dist.get(s, 0) + 1
    dist_summary = "  ".join(
        f"{s}×{dist[s]}" for s in sorted(dist.keys(), reverse=True)
    )

    cards_html = []
    for item in items:
        score = item.get("score", 0)
        hook = _esc(item.get("hook") or item.get("title") or "")
        why = _esc(item.get("why") or "")
        title = _esc(item.get("title") or "")
        url = item.get("url") or "#"
        # source name: join sources table via source_id — get_feed returns source_id not name
        # fall back to domain extraction from url
        source_display = _esc(_source_from_url(url))
        label = _score_label(score)

        card = f"""
    <article class="card">
      <div class="card-meta">
        <span class="score score-{score}">{score}</span>
        <span class="label">{label}</span>
        <span class="source">{source_display}</span>
      </div>
      <a class="hook" href="{url}" target="_blank" rel="noopener noreferrer">{hook}</a>
      {f'<p class="why">{why}</p>' if why else ''}
      {f'<p class="title-sub">{title}</p>' if title and title != hook else ''}
    </article>"""
        cards_html.append(card)

    cards = "\n".join(cards_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Blank — Feed</title>
  <meta name="description" content="Culturally relevant. Editorially scored.">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:      #E8E8E8;
      --ink:     #1E1E1E;
      --muted:   #7A7A7A;
      --faint:   #ABABAB;
      --border:  #C8C8C8;
      --surface: #DCDCDC;
      --accent:  #C4E817;
      --sans:    -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      --max-w:   680px;
    }}

    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg:      #111111;
        --ink:     #EBEBEB;
        --muted:   #777777;
        --faint:   #333333;
        --border:  #2A2A2A;
        --surface: #1A1A1A;
      }}
    }}

    html, body {{
      min-height: 100%;
      background: var(--bg);
      color: var(--ink);
      font-family: var(--sans);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }}

    ::selection {{ background: var(--accent); color: #1E1E1E; }}

    /* ── Header ── */
    header {{
      border-bottom: 1px solid var(--border);
      padding: 20px 24px 16px;
    }}

    .wordmark {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--ink);
      margin-bottom: 10px;
    }}

    .header-meta {{
      font-size: 11px;
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: baseline;
    }}

    .header-meta .updated {{
      color: var(--faint);
    }}

    /* ── Feed ── */
    main {{
      max-width: var(--max-w);
      margin: 0 auto;
      padding: 0 24px 80px;
    }}

    /* ── Card ── */
    .card {{
      border-bottom: 1px solid var(--border);
      padding: 24px 0;
    }}

    .card:first-child {{
      padding-top: 28px;
    }}

    .card-meta {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
    }}

    .score {{
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.04em;
      width: 22px;
      height: 22px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--border);
      border-radius: 3px;
      background: var(--surface);
      color: var(--ink);
      flex-shrink: 0;
    }}

    .score-9, .score-10 {{
      background: var(--accent);
      border-color: var(--accent);
      color: #1E1E1E;
    }}

    .label {{
      font-size: 10px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--faint);
    }}

    .source {{
      font-size: 11px;
      color: var(--muted);
      margin-left: auto;
    }}

    .hook {{
      display: block;
      font-size: 17px;
      font-weight: 550;
      line-height: 1.4;
      color: var(--ink);
      text-decoration: none;
      margin-bottom: 8px;
    }}

    .hook:hover {{
      text-decoration: underline;
      text-underline-offset: 3px;
    }}

    .why {{
      font-size: 14px;
      color: var(--muted);
      line-height: 1.55;
      margin-bottom: 4px;
    }}

    .title-sub {{
      font-size: 12px;
      color: var(--faint);
      margin-top: 6px;
    }}

    /* ── Footer ── */
    footer {{
      border-top: 1px solid var(--border);
      padding: 20px 24px;
      max-width: var(--max-w);
      margin: 0 auto;
      font-size: 11px;
      color: var(--faint);
    }}

    @media (max-width: 480px) {{
      header, main, footer {{ padding-left: 16px; padding-right: 16px; }}
      .hook {{ font-size: 16px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wordmark">B L A N K</div>
    <div class="header-meta">
      <span>{item_count} items &nbsp;·&nbsp; {dist_summary}</span>
      <span class="updated">Updated {updated}</span>
    </div>
  </header>

  <main>
{cards}
  </main>

  <footer>
    Scored and curated by the Blank engine. Minimum score {FEED_THRESHOLD}/10 to surface.
  </footer>
</body>
</html>"""


def _source_from_url(url: str) -> str:
    """Extract a readable source name from a URL (domain without www)."""
    try:
        host = url.split("://", 1)[1].split("/")[0].lower()
        if host.startswith("www."):
            host = host[4:]
        # Strip common TLD for brevity: bbc.co.uk → bbc, reddit.com → reddit
        parts = host.split(".")
        if len(parts) >= 2:
            return parts[-2] if parts[-2] not in ("co", "com") else parts[-3] if len(parts) >= 3 else parts[0]
        return host
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git(*args) -> tuple[int, str, str]:
    """Run a git command, return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def commit_and_push(target: str) -> None:
    """Stage target file, commit, and push to origin/main."""
    rel = os.path.relpath(target, os.path.dirname(os.path.abspath(__file__)))

    code, out, err = _git("add", rel)
    if code != 0:
        raise RuntimeError(f"git add failed: {err}")

    code, out, err = _git("diff", "--cached", "--quiet")
    if code == 0:
        print("  Nothing to commit — index.html is unchanged.")
        return

    code, out, err = _git(
        "commit", "-m",
        f"Publish feed snapshot [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}]"
    )
    if code != 0:
        raise RuntimeError(f"git commit failed: {err}")
    print(f"  Committed: {out}")

    # Safety: never force-push
    code, out, err = _git("push", "origin", "main")
    if code != 0:
        raise RuntimeError(f"git push failed: {err}")
    print(f"  Pushed to origin/main.")


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def run_publish(
    no_push: bool = False,
    confirm: bool = False,
    out_path: str = None,
) -> None:
    # 1. Pull the feed
    items = db.get_feed(min_score=FEED_THRESHOLD, limit=FEED_LIMIT)
    if not items:
        print("No scored items in the feed (min_score=6). Run score.py first.")
        return

    print(f"Feed: {len(items)} item(s) at score >= {FEED_THRESHOLD}.\n")

    # 2. Detect Pages setup
    findings = detect_pages_setup()
    print_detection(findings)

    target = out_path or findings["target"]
    print(f"\n  Output → {target}")

    # 3. Confirmation gate (skip if --confirm or --no-push)
    if not no_push and not confirm:
        print()
        if findings["source_file"]:
            print("  WARNING: This will overwrite the existing index.html.")
        answer = input("  Proceed? [y/N] ").strip().lower()
        if answer != "y":
            print("  Aborted.")
            return

    # 4. Generate and write HTML
    html = generate_html(items)
    with open(target, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  Written: {target}  ({len(html):,} bytes)")

    if no_push:
        print(f"\n  --no-push: skipping git commit/push.")
        abs_target = os.path.abspath(target)
        print(f"  Open in browser: file:///{abs_target.replace(os.sep, '/')}")
        return

    # 5. Commit and push
    print()
    commit_and_push(target)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from dotenv import load_dotenv
    load_dotenv()

    no_push = "--no-push" in sys.argv
    confirm = "--confirm" in sys.argv

    out_path = None
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]

    run_publish(no_push=no_push, confirm=confirm, out_path=out_path)
