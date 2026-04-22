"""
digest_publisher.py — Daily Digest with Auto-Sourced Images

Runs after the 7:30PM CT (00:30 UTC) pipeline. Pulls the top 5 stories from
the latest picks/*.md, generates platform-ready copy via Claude Sonnet, sources
images, and renders 6 post-ready JPEGs: slide_00_cover.jpg + slide_01–05.jpg.

Image sourcing priority per story slide:
  1. og:image from picks file (already scraped) / BeautifulSoup re-scrape
  2. Unsplash API
  3. Pexels API
  4. Placeholder

Outputs to /digests/YYYY-MM-DD/.
Usage: python digest_publisher.py [picks/picks-YYYY-MM-DD-HHMM.md]
"""

import glob
import html
import json
import math
import os
import re
import sys
import time
import unicodedata
from io import BytesIO
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

load_dotenv()

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY      = os.environ.get("PEXELS_API_KEY")

OUTPUT_SIZE  = (1080, 1350)
HALF_H       = OUTPUT_SIZE[1] // 2   # 675 — top image / bottom text split
BORDER_INSET = 24
JPEG_QUALITY = 95
REQUEST_DELAY = 0.4
MIN_IMAGE_DIM = 600

RARITY_MAP = {
    10: ("LEGENDARY", "#3B82F6"),
    9:  ("EPIC",      "#8B5CF6"),
}
RARITY_DEFAULT = ("TOP PICK", "#F97316")

_BEBAS_URL = (
    "https://github.com/dharmatype/Bebas-Neue/raw/master/"
    "fonts/BebasNeue%282018%29ByDhamraType/TTF/BebasNeue-Regular.ttf"
)
_INTER_URLS = [
    "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bslnt%2Cwght%5D.ttf",
    "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-Regular.otf",
]
_FONT_DIR    = Path("fonts")
_BEBAS_PATH  = _FONT_DIR / "BebasNeue-Regular.ttf"
_INTER_PATH  = _FONT_DIR / "Inter-Regular.ttf"

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DigestPublisher/1.0)"}

SYSTEM_PROMPT = (
    "You write like a human who reads everything and shares only what's worth it. "
    "No AI tells, no corporate polish, no filler phrases. Short sentences. Confident. "
    "Culture-forward but not try-hard. No brand name, no platform references, no CTAs. "
    "Just the stories, the source, and a point of view. You're a faceless curator with "
    "good taste — let the curation speak."
)


# ── Picks parsing ─────────────────────────────────────────────────────────────

def find_latest_picks_file() -> str:
    files = sorted(glob.glob("picks/picks-*.md"), reverse=True)
    if not files:
        sys.exit("❌  No picks files found in picks/")
    return files[0]


def parse_picks(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    picks = []
    for block in re.split(r"\n## Pick #\d+", content)[1:]:
        sm = re.search(r"— Score: (\d+)/10", block)
        if not sm:
            continue
        score = int(sm.group(1))

        tm = re.search(r"\*\*([^*\n]+)\*\*\n\*([^*\n]+)\*", block)
        if not tm:
            continue
        title  = tm.group(1).strip()
        source = tm.group(2).strip()

        lm = re.search(r"\[Read the full article →\]\(([^)]+)\)", block)
        if not lm:
            continue
        link = lm.group(1).strip()

        cp = re.search(r"\*\*Cluster Primary:\*\*\s*(true|false)", block)
        if cp and cp.group(1) == "false":
            continue

        im = re.search(r"\*\*Image:\*\*\s*(\S+)", block)
        image_url = html.unescape(im.group(1).strip()) if im else None

        wm = re.search(r"\*\*Why it matters:\*\*\n(.+?)(?=\n\n|\*\*Hook|\Z)", block, re.DOTALL)
        why = wm.group(1).strip() if wm else ""

        picks.append({
            "title":     title,
            "source":    source,
            "link":      link,
            "score":     score,
            "image_url": image_url,
            "why":       why,
        })

    return picks


def select_top5(picks: list[dict]) -> list[dict]:
    return sorted(picks, key=lambda p: -p["score"])[:5]


# ── Network helpers ───────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 12, **kwargs) -> requests.Response | None:
    try:
        r = requests.get(url, timeout=timeout, headers=_HTTP_HEADERS, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"      ⚠️  GET failed ({url[:70]}): {e}")
        return None


def _fetch_bytes(url: str) -> bytes | None:
    r = _get(url)
    return r.content if r else None


def _meets_size(data: bytes) -> bool:
    try:
        img = Image.open(BytesIO(data))
        return min(img.size) >= MIN_IMAGE_DIM
    except Exception:
        return False


# ── Font loading ──────────────────────────────────────────────────────────────

def _download_font(url: str, dest: Path, label: str) -> bool:
    print(f"   📥 Downloading {label}…", end=" ", flush=True)
    r = _get(url, timeout=20)
    if r:
        dest.write_bytes(r.content)
        print("done.")
        return True
    print("failed.")
    return False


def _load_bebas(size: int = 68) -> ImageFont.FreeTypeFont | None:
    if not _BEBAS_PATH.exists():
        _FONT_DIR.mkdir(parents=True, exist_ok=True)
        if not _download_font(_BEBAS_URL, _BEBAS_PATH, "Bebas Neue"):
            return None
    try:
        return ImageFont.truetype(str(_BEBAS_PATH), size=size)
    except Exception as e:
        print(f"      ⚠️  Bebas Neue load failed: {e}")
        return None


def _load_inter(size: int = 16) -> ImageFont.FreeTypeFont | None:
    if not _INTER_PATH.exists():
        _FONT_DIR.mkdir(parents=True, exist_ok=True)
        downloaded = False
        for url in _INTER_URLS:
            if _download_font(url, _INTER_PATH, "Inter"):
                downloaded = True
                break
        if not downloaded:
            return None
    try:
        return ImageFont.truetype(str(_INTER_PATH), size=size)
    except Exception as e:
        print(f"      ⚠️  Inter load failed: {e}")
        return None


def _default_font(size: int = 16) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ── Image sourcing ────────────────────────────────────────────────────────────

def _scrape_og_image(article_url: str) -> bytes | None:
    if not HAS_BS4:
        return None
    r = _get(article_url, timeout=8)
    if not r:
        return None
    try:
        soup = BeautifulSoup(r.text, "html.parser")
        tag = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
        if not tag:
            return None
        og_url = tag.get("content", "").strip()
        if not og_url:
            return None
        data = _fetch_bytes(og_url)
        return data if data and _meets_size(data) else None
    except Exception as e:
        print(f"      ⚠️  og:image scrape failed: {e}")
        return None


def _source_unsplash(query: str) -> bytes | None:
    if not UNSPLASH_ACCESS_KEY:
        return None
    r = _get(
        "https://api.unsplash.com/search/photos",
        params={"query": query, "per_page": 5, "orientation": "portrait"},
        headers={**_HTTP_HEADERS, "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
    )
    if not r:
        return None
    for photo in r.json().get("results", []):
        url = photo.get("urls", {}).get("regular")
        if url:
            data = _fetch_bytes(url)
            if data and _meets_size(data):
                return data
    return None


def _source_pexels(query: str) -> bytes | None:
    if not PEXELS_API_KEY:
        return None
    r = _get(
        "https://api.pexels.com/v1/search",
        params={"query": query, "per_page": 5, "orientation": "portrait"},
        headers={**_HTTP_HEADERS, "Authorization": PEXELS_API_KEY},
    )
    if not r:
        return None
    for photo in r.json().get("photos", []):
        url = photo.get("src", {}).get("large")
        if url:
            data = _fetch_bytes(url)
            if data and _meets_size(data):
                return data
    return None


def source_story_image(pick: dict) -> bytes | None:
    # 1. Pre-scraped og:image from picks file
    if pick.get("image_url"):
        data = _fetch_bytes(pick["image_url"])
        if data and _meets_size(data):
            return data

    # 2. Fresh BeautifulSoup og:image scrape
    time.sleep(REQUEST_DELAY)
    data = _scrape_og_image(pick["link"])
    if data:
        return data

    # 3. Unsplash
    time.sleep(REQUEST_DELAY)
    query = " ".join(w for w in pick["title"].split() if len(w) > 4)[:60] or "culture"
    data = _source_unsplash(query)
    if data:
        return data

    # 4. Pexels
    time.sleep(REQUEST_DELAY)
    data = _source_pexels(query)
    return data


# ── Claude copy generation ────────────────────────────────────────────────────

def _break_tie(candidates: list[dict], client: anthropic.Anthropic) -> int:
    """Return index within candidates of the stronger Editor's Pick."""
    if len(candidates) == 1:
        return 0
    parts = []
    for i, p in enumerate(candidates):
        letter = chr(ord("A") + i)
        parts.append(f'Story {letter}: "{p["title"]}" — {p["why"][:120]}')
    prompt = (
        "Two stories are tied for Editor's Pick. Choose the one with greater cultural weight "
        "and staying power.\n\n"
        + "\n".join(parts)
        + '\n\nReturn ONLY valid JSON: {"pick": "A"} or {"pick": "B"}'
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        result = json.loads(raw)
        letter = result.get("pick", "A").upper()
        idx = ord(letter) - ord("A")
        return min(idx, len(candidates) - 1)
    except Exception:
        return 0


def select_editors_pick(top5: list[dict], client: anthropic.Anthropic) -> int:
    """Return index (0–4) of the Editor's Pick."""
    max_score = max(p["score"] for p in top5)
    candidates_idx = [i for i, p in enumerate(top5) if p["score"] == max_score]
    if len(candidates_idx) == 1:
        return candidates_idx[0]
    candidates = [top5[i] for i in candidates_idx]
    winner_pos = _break_tie(candidates, client)
    return candidates_idx[winner_pos]


def generate_copy(top5: list[dict], editors_pick_idx: int, client: anthropic.Anthropic) -> dict:
    stories_text = ""
    for i, p in enumerate(top5, start=1):
        ep = " [EDITOR'S PICK]" if (i - 1) == editors_pick_idx else ""
        stories_text += (
            f"\nStory {i}{ep}:\n"
            f"  Title: {p['title']}\n"
            f"  Source: {p['source']}\n"
            f"  Why it matters: {p['why'][:200]}\n"
        )

    prompt = (
        f"Generate copy for today's daily digest. Today's date: {_today_label()}\n\n"
        f"STORIES:{stories_text}\n"
        "Generate:\n"
        "1. cover_subline: A ≤5-word editorial line capturing today's digest mood. "
        "Cryptic, minimal, no punctuation at the end. Examples: 'Everything is accelerating', "
        "'Culture moves faster now', 'The week started somewhere'\n"
        "2. For each story (in order):\n"
        "   - category: 1-2 word ALL CAPS category label (MUSIC / TECH / CULTURE / SPORTS / "
        "SCIENCE / BUSINESS / FILM / DESIGN)\n"
        "   - instagram: Short-form Instagram copy. No links, no CTAs, no hashtags.\n"
        "   - tiktok: Short-form TikTok caption. Punchy, native feel.\n"
        "   - threads: Short-form Threads post. Conversational.\n"
        "   - substack: One paragraph for a Substack note. Slightly more analytical.\n"
        "   - why_slide: One punchy sentence ≤15 words for the slide. Why this matters right now.\n\n"
        "Return ONLY valid JSON:\n"
        '{"cover_subline": "...", "stories": ['
        '{"category": "...", "instagram": "...", "tiktok": "...", '
        '"threads": "...", "substack": "...", "why_slide": "..."}, ...]}'
    )

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def _today_label() -> str:
    import datetime
    return datetime.date.today().strftime("%B %d, %Y")


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _wrap_text(draw: ImageDraw.Draw, text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        try:
            w = draw.textlength(test, font=font)
        except Exception:
            w = len(test) * (font.size if hasattr(font, "size") else 10)
        if w <= max_w:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def _text_h(font) -> int:
    try:
        bb = font.getbbox("Ag")
        return bb[3] - bb[1]
    except Exception:
        return getattr(font, "size", 16)


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _entropy_offset(img: Image.Image, target: int, horizontal: bool) -> int:
    """Return the pixel offset that places the highest-entropy region within target px."""
    gray = img.convert("L")
    w, h = gray.size
    total = w if horizontal else h
    excess = total - target
    if excess <= 0:
        return 0

    # Divide the axis into 32px blocks and score each by entropy.
    BLOCK = 32
    n_blocks = max(1, total // BLOCK)
    block_px = total / n_blocks

    entropies: list[float] = []
    for i in range(n_blocks):
        p0 = int(i * block_px)
        p1 = min(int((i + 1) * block_px), total)
        tile = gray.crop((p0, 0, p1, h)) if horizontal else gray.crop((0, p0, w, p1))
        entropies.append(tile.entropy())

    # Sliding window: find the contiguous run of blocks that covers `target` px
    # and has the highest total entropy.
    window = max(1, round(target / block_px))
    if window >= n_blocks:
        return 0

    win_sum = sum(entropies[:window])
    best_sum, best_i = win_sum, 0
    for i in range(1, n_blocks - window + 1):
        win_sum += entropies[i + window - 1] - entropies[i - 1]
        if win_sum > best_sum:
            best_sum, best_i = win_sum, i

    return min(int(best_i * block_px), excess)


def _smart_crop(raw: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Scale-to-cover then entropy-crop to target_w × target_h."""
    w, h = raw.size
    scale = max(target_w / w, target_h / h)
    if scale != 1.0:
        new_w = max(target_w, math.ceil(w * scale))
        new_h = max(target_h, math.ceil(h * scale))
        raw = raw.resize((new_w, new_h), Image.LANCZOS)
        w, h = raw.size

    if w > target_w:
        left = _entropy_offset(raw, target_w, horizontal=True)
        raw = raw.crop((left, 0, left + target_w, h))
        w = target_w

    if h > target_h:
        top = _entropy_offset(raw, target_h, horizontal=False)
        raw = raw.crop((0, top, w, top + target_h))

    return raw


# ── Slide rendering ───────────────────────────────────────────────────────────

def _draw_outer_border(draw: ImageDraw.Draw) -> None:
    i = BORDER_INSET
    draw.rectangle(
        [i, i, OUTPUT_SIZE[0] - i - 1, OUTPUT_SIZE[1] - i - 1],
        outline="#111111",
        width=1,
    )


def render_cover(date_str: str, subline: str, out_path: Path) -> None:
    img  = Image.new("RGB", OUTPUT_SIZE, color="#FFFFFF")
    draw = ImageDraw.Draw(img)

    bebas_big  = _load_bebas(size=180) or _default_font(180)
    bebas_sub  = _load_bebas(size=40)  or _default_font(40)

    import datetime
    try:
        d = datetime.date.fromisoformat(date_str)
        date_label = d.strftime("%b %d").upper()  # "APR 21"
    except Exception:
        date_label = date_str.upper()

    cx = OUTPUT_SIZE[0] // 2
    cy = OUTPUT_SIZE[1] // 2

    # Date centered
    try:
        dw = draw.textlength(date_label, font=bebas_big)
    except Exception:
        dw = len(date_label) * 90
    dh = _text_h(bebas_big)
    dy = cy - dh // 2 - 30
    draw.text((cx - dw / 2, dy), date_label, fill="#111111", font=bebas_big)

    # Subline beneath
    try:
        sw = draw.textlength(subline, font=bebas_sub)
    except Exception:
        sw = len(subline) * 20
    sy = dy + dh + 20
    draw.text((cx - sw / 2, sy), subline, fill="#888888", font=bebas_sub)

    _draw_outer_border(draw)
    img.save(str(out_path), "JPEG", quality=JPEG_QUALITY, optimize=True)


def render_story_slide(
    pick: dict,
    copy: dict,
    img_data: bytes | None,
    is_editors_pick: bool,
    out_path: Path,
) -> None:
    canvas = Image.new("RGB", OUTPUT_SIZE, color="#FFFFFF")

    # ── Top half: sourced image ───────────────────────────────────────────────
    if img_data:
        try:
            raw = Image.open(BytesIO(img_data)).convert("RGB")
            top_img = _smart_crop(raw, OUTPUT_SIZE[0], HALF_H)
            canvas.paste(top_img, (0, 0))
        except Exception as e:
            print(f"      ⚠️  Image paste failed: {e} — top half blank")

    draw = ImageDraw.Draw(canvas)

    # ── Bottom half: text area ────────────────────────────────────────────────
    PAD_X   = 56
    content_w = OUTPUT_SIZE[0] - PAD_X * 2
    y = HALF_H + 40

    inter_cat  = _load_inter(13)  or _default_font(13)
    inter_src  = _load_inter(15)  or _default_font(15)
    inter_why  = _load_inter(16)  or _default_font(16)
    inter_rar  = _load_inter(12)  or _default_font(12)
    bebas_head = _load_bebas(52)  or _default_font(52)

    category = copy.get("category", "").upper()
    why_slide = copy.get("why_slide", pick["why"][:80])
    source    = pick["source"].split("|")[0].strip()

    # Category tag
    draw.text((PAD_X, y), category, fill="#888888", font=inter_cat)
    cat_h = _text_h(inter_cat)

    # Editor's Pick rarity label (top-right, same row as category)
    if is_editors_pick:
        label, color_hex = RARITY_MAP.get(pick["score"], RARITY_DEFAULT)
        try:
            lw = draw.textlength(label, font=inter_rar)
        except Exception:
            lw = len(label) * 7
        draw.text(
            (OUTPUT_SIZE[0] - PAD_X - lw, y + 1),
            label,
            fill=color_hex,
            font=inter_rar,
        )

    y += cat_h + 14

    # Bebas headline (word-wrapped)
    lines = _wrap_text(draw, pick["title"], bebas_head, content_w)
    line_h = _text_h(bebas_head) + 6
    for line in lines[:3]:
        draw.text((PAD_X, y), line, fill="#111111", font=bebas_head)
        y += line_h
    y += 10

    # Source
    draw.text((PAD_X, y), source, fill="#888888", font=inter_src)
    y += _text_h(inter_src) + 16

    # Why slide (up to 2 lines)
    why_lines = _wrap_text(draw, why_slide, inter_why, content_w)
    why_h = _text_h(inter_why) + 4
    for line in why_lines[:2]:
        draw.text((PAD_X, y), line, fill="#111111", font=inter_why)
        y += why_h

    # 1px bottom rule
    rule_y = OUTPUT_SIZE[1] - BORDER_INSET - 1
    draw.line([(BORDER_INSET, rule_y), (OUTPUT_SIZE[0] - BORDER_INSET, rule_y)], fill="#111111", width=1)

    # Outer border
    _draw_outer_border(draw)

    # Editor's Pick: left accent border (over full height, text area only)
    if is_editors_pick:
        _, color_hex = RARITY_MAP.get(pick["score"], RARITY_DEFAULT)
        color_rgb = _hex_to_rgb(color_hex)
        for px in range(3):
            draw.line(
                [(BORDER_INSET + px, HALF_H), (BORDER_INSET + px, OUTPUT_SIZE[1] - BORDER_INSET)],
                fill=color_rgb,
                width=1,
            )

    canvas.save(str(out_path), "JPEG", quality=JPEG_QUALITY, optimize=True)


# ── digest.md ─────────────────────────────────────────────────────────────────

def write_digest_md(
    top5: list[dict],
    copy_data: dict,
    editors_pick_idx: int,
    date_str: str,
    out_dir: Path,
) -> None:
    import datetime
    try:
        d = datetime.date.fromisoformat(date_str)
        pretty_date = d.strftime("%B %d, %Y")
    except Exception:
        pretty_date = date_str

    lines = [f"# Daily Digest — {pretty_date}\n"]

    for i, (pick, copy) in enumerate(zip(top5, copy_data.get("stories", []))):
        is_ep = (i == editors_pick_idx)
        label, _ = RARITY_MAP.get(pick["score"], RARITY_DEFAULT) if is_ep else ("", "")

        if is_ep:
            lines.append(f"---\n\n## ★ Editor's Pick — {label}")
        else:
            lines.append(f"---\n\n## Story {i + 1}")

        lines.append(f"**{pick['title']}**  \n*{pick['source'].split('|')[0].strip()}*\n")
        lines.append(f"> {copy.get('why_slide', pick['why'][:120])}\n")
        lines.append("### Platform Copy\n")
        lines.append(f"**Instagram**\n{copy.get('instagram', '')}\n")
        lines.append(f"**TikTok**\n{copy.get('tiktok', '')}\n")
        lines.append(f"**Threads**\n{copy.get('threads', '')}\n")
        lines.append(f"**Substack**\n{copy.get('substack', '')}\n")

    md_path = out_dir / "digest.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"   📄 digest.md written")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    picks_file = sys.argv[1] if len(sys.argv) > 1 else find_latest_picks_file()
    if not os.path.exists(picks_file):
        sys.exit(f"❌  File not found: {picks_file}")

    date_m   = re.search(r"picks-(\d{4}-\d{2}-\d{2})", picks_file)
    date_str = date_m.group(1) if date_m else __import__("datetime").date.today().isoformat()

    print(f"\n📰  Digest Publisher")
    print(f"    Picks file : {picks_file}")
    print(f"    Output dir : digests/{date_str}/\n")

    all_picks = parse_picks(picks_file)
    if not all_picks:
        print("⚠️  No cluster-primary picks found — nothing to do.")
        return

    top5 = select_top5(all_picks)
    if not top5:
        print("⚠️  No picks selected — nothing to do.")
        return

    print(f"    {len(top5)} stories selected (top {len(top5)} by score)\n")

    if not ANTHROPIC_API_KEY:
        sys.exit("❌  ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Editor's Pick selection
    editors_pick_idx = select_editors_pick(top5, client)
    ep_pick = top5[editors_pick_idx]
    ep_label, ep_color = RARITY_MAP.get(ep_pick["score"], RARITY_DEFAULT)
    print(f"    ★  Editor's Pick: [{ep_label}] {ep_pick['title'][:60]}\n")

    # Generate all copy in one Claude call
    print("    🤖 Generating digest copy via Claude Sonnet…")
    try:
        copy_data = generate_copy(top5, editors_pick_idx, client)
    except Exception as e:
        print(f"    ⚠️  Claude copy generation failed: {e}")
        copy_data = {
            "cover_subline": "What moved the culture",
            "stories": [
                {"category": "CULTURE", "instagram": pick["why"][:100],
                 "tiktok": pick["why"][:80], "threads": pick["why"][:100],
                 "substack": pick["why"], "why_slide": pick["why"][:80]}
                for pick in top5
            ],
        }

    cover_subline = copy_data.get("cover_subline", "What moved the culture")
    stories_copy  = copy_data.get("stories", [])
    # Pad if Claude returned fewer than 5
    while len(stories_copy) < len(top5):
        p = top5[len(stories_copy)]
        stories_copy.append({
            "category": "CULTURE", "instagram": p["why"][:100],
            "tiktok": p["why"][:80], "threads": p["why"][:100],
            "substack": p["why"], "why_slide": p["why"][:80],
        })

    out_dir = Path(f"digests/{date_str}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Slide 00 — cover
    cover_path = out_dir / "slide_00_cover.jpg"
    print(f"  [00] Cover slide")
    render_cover(date_str, cover_subline, cover_path)
    print(f"       ✅ {cover_path.name}")

    # Slides 01–05 — stories
    for idx, (pick, copy) in enumerate(zip(top5, stories_copy), start=1):
        is_ep = (idx - 1) == editors_pick_idx
        slide_path = out_dir / f"slide_{idx:02d}.jpg"
        ep_tag = " [EDITOR'S PICK]" if is_ep else ""
        print(f"  [{idx:02d}] {pick['title'][:60]}{ep_tag}")

        img_data = source_story_image(pick)
        src_label = "sourced" if img_data else "placeholder"
        print(f"       🖼  {src_label}")

        render_story_slide(pick, copy, img_data, is_ep, slide_path)
        print(f"       ✅ {slide_path.name}")
        time.sleep(REQUEST_DELAY)

    write_digest_md(top5, copy_data, editors_pick_idx, date_str, out_dir)

    print(f"\n  Done — digest saved to digests/{date_str}/\n")


if __name__ == "__main__":
    main()
