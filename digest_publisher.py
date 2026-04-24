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

OUTPUT_SIZE     = (1080, 1350)
GRAD_START_Y    = 500           # story slide: bottom gradient begins here
TEXT_BOTTOM_PAD = 72            # story slide: source pinned this far from bottom
BORDER_INSET    = 20            # outer border inset from canvas edges
MARGIN          = 48            # left/right text margin
JPEG_QUALITY    = 95
REQUEST_DELAY   = 0.4
MIN_IMAGE_DIM   = 600

RARITY_MAP = {
    10: ("LEGENDARY", "#3B82F6"),
    9:  ("EPIC",      "#8B5CF6"),
}
RARITY_DEFAULT = ("TOP PICK", "#F97316")

# Direct GitHub raw URLs for TTF/variable-font files (Google Fonts now only serves woff2)
_BEBAS_TTF_URL = (
    "https://raw.githubusercontent.com/dharmatype/Bebas-Neue/master/"
    "fonts/BebasNeue%282018%29ByDhamraType/ttf/BebasNeue-Regular.ttf"
)
_INTER_TTF_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/"
    "Inter%5Bopsz%2Cwght%5D.ttf"
)
_FONT_DIR          = Path("fonts")
_BEBAS_PATH        = _FONT_DIR / "BebasNeue-Regular.ttf"
_INTER_PATH        = _FONT_DIR / "Inter-Variable.ttf"
_INTER_MEDIUM_PATH = _INTER_PATH   # same variable font file; weight distinction via size/tracking

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DigestPublisher/1.0)"}

SYSTEM_PROMPT = (
    "You write like a human who reads everything and shares only what's worth it. "
    "No AI tells, no corporate polish, no filler phrases. Short sentences. Confident. "
    "Culture-forward but not try-hard. No brand name, no platform references, no CTAs. "
    "Just the stories, the source, and a point of view. You're a faceless curator with "
    "good taste — let the curation speak."
)


# ── Picks parsing ─────────────────────────────────────────────────────────────

def find_todays_picks_files() -> list[str]:
    today = __import__("datetime").date.today().isoformat()
    files = sorted(glob.glob(f"picks/picks-{today}-*.md"))
    if not files:
        sys.exit(f"❌  No picks files found for {today}")
    return files


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

        hm = re.search(r"\*\*Hook:\*\*\n(.+?)(?=\n\n|\Z)", block, re.DOTALL)
        hook_raw = hm.group(1).strip() if hm else ""
        # Strip the [TRIGGER: ...] prefix and split on " / " to get pre-formatted lines
        hook_clean = re.sub(r'^\[TRIGGER:\s*[^\]]+\]\s*', '', hook_raw)
        hook_lines = [l.strip() for l in hook_clean.split(" / ") if l.strip()] if hook_clean else []

        picks.append({
            "title":      title,
            "source":     source,
            "link":       link,
            "score":      score,
            "image_url":  image_url,
            "why":        why,
            "hook_lines": hook_lines,  # pre-split lines from the Hook field
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

def _is_valid_font(path: Path) -> bool:
    """Return True if the file is a readable TTF/OTF, False if woff/woff2."""
    try:
        header = path.read_bytes()[:4]
        return header not in (b'wOF2', b'wOFF')
    except Exception:
        return False


def _fetch_font_direct(url: str, dest: Path, label: str) -> bool:
    """Download a TTF/variable font file directly from a known URL."""
    print(f"   📥 Downloading {label}…", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        dest.write_bytes(r.content)
        if not _is_valid_font(dest):
            dest.unlink()
            raise ValueError("downloaded file is not a valid TTF/OTF font")
        print("done.")
        return True
    except Exception as e:
        print(f"failed ({e}).")
        return False


def _load_bebas(size: int = 68) -> ImageFont.FreeTypeFont | None:
    if not _BEBAS_PATH.exists() or not _is_valid_font(_BEBAS_PATH):
        _FONT_DIR.mkdir(parents=True, exist_ok=True)
        if _BEBAS_PATH.exists():
            _BEBAS_PATH.unlink()
        _fetch_font_direct(_BEBAS_TTF_URL, _BEBAS_PATH, "Bebas Neue")
    if not _BEBAS_PATH.exists():
        return None
    try:
        return ImageFont.truetype(str(_BEBAS_PATH), size=size)
    except Exception as e:
        print(f"      ⚠️  Bebas Neue load failed: {e}")
        return None


def _load_inter(size: int = 16) -> ImageFont.FreeTypeFont | None:
    if not _INTER_PATH.exists() or not _is_valid_font(_INTER_PATH):
        _FONT_DIR.mkdir(parents=True, exist_ok=True)
        if _INTER_PATH.exists():
            _INTER_PATH.unlink()
        _fetch_font_direct(_INTER_TTF_URL, _INTER_PATH, "Inter")
    if not _INTER_PATH.exists():
        return None
    try:
        return ImageFont.truetype(str(_INTER_PATH), size=size)
    except Exception as e:
        print(f"      ⚠️  Inter load failed: {e}")
        return None


def _load_inter_medium(size: int = 16) -> ImageFont.FreeTypeFont | None:
    return _load_inter(size)


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


def _truncate_lines(lines: list[str], max_lines: int, draw: ImageDraw.Draw, font, max_w: int) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    result = list(lines[:max_lines])
    last = result[-1]
    try:
        while last and draw.textlength(last + "…", font=font) > max_w:
            last = last[:-1]
    except Exception:
        last = last[:40]
    result[-1] = last + "…"
    return result


def _text_h(font) -> int:
    try:
        bb = font.getbbox("Ag")
        return bb[3] - bb[1]
    except Exception:
        return getattr(font, "size", 16)


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _char_w(font, char: str) -> int:
    try:
        bb = font.getbbox(char)
        return max(0, bb[2] - bb[0])
    except Exception:
        return 8


def _draw_tracked(
    draw: ImageDraw.Draw,
    text: str,
    font,
    fill,
    tracking_px: int = 0,
    *,
    x: float | None = None,
    y: float = 0,
    center_in_w: int | None = None,
) -> None:
    """Draw text with per-character letter spacing (tracking).

    Pass center_in_w to horizontally center within that canvas width,
    or x to left-align from that position.
    """
    chars = list(text)
    widths = [_char_w(font, c) for c in chars]
    total_w = sum(widths) + tracking_px * max(0, len(chars) - 1)

    if center_in_w is not None:
        cx = (center_in_w - total_w) / 2
    else:
        cx = x if x is not None else 0

    for i, (char, cw) in enumerate(zip(chars, widths)):
        draw.text((cx, y), char, font=font, fill=fill)
        cx += cw + (tracking_px if i < len(chars) - 1 else 0)


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


def _smart_crop(raw: Image.Image, target_w: int, target_h: int, prefer_top: bool = False) -> Image.Image:
    """Scale-to-cover then entropy-crop to target_w × target_h.

    prefer_top=True anchors vertical crop to the top of the image, preserving
    faces and heads. Horizontal entropy cropping is always applied.
    """
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
        top = 0 if prefer_top else _entropy_offset(raw, target_h, horizontal=False)
        raw = raw.crop((0, top, w, top + target_h))

    return raw


# ── Slide rendering ───────────────────────────────────────────────────────────

def _alpha_rect(canvas: Image.Image, box: tuple, outline: tuple, width: int = 1) -> Image.Image:
    """Draw a rectangle outline with RGBA colour onto a canvas, return merged RGB."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle(box, outline=outline, width=width)
    return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")


def _gradient_overlay(size: tuple, start_y: int, max_alpha: float, top_bar: bool = False) -> Image.Image:
    """Create a vertical RGBA gradient overlay for compositing.

    Bottom gradient: transparent at start_y, easing to max_alpha at the bottom.
    top_bar: also adds a 40%-to-transparent fade over the top 120px for badge readability.
    """
    w, h = size
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(grad)

    if top_bar:
        bar_h = 120
        for y in range(bar_h):
            alpha = int((1 - y / bar_h) * 0.40 * 255)
            draw.line([(0, y), (w - 1, y)], fill=(0, 0, 0, alpha))

    span = h - start_y
    for y in range(start_y, h):
        t = (y - start_y) / span
        t_eased = t ** 0.65  # ease-in: slow start, accelerating toward bottom
        alpha = int(t_eased * max_alpha * 255)
        draw.line([(0, y), (w - 1, y)], fill=(0, 0, 0, alpha))

    return grad


def render_cover(
    date_str: str,
    subline: str,
    cover_img_data: bytes | None,
    out_path: Path,
) -> None:
    import datetime

    canvas = Image.new("RGB", OUTPUT_SIZE, "#111111")
    if cover_img_data:
        try:
            raw = Image.open(BytesIO(cover_img_data)).convert("RGB")
            canvas.paste(_smart_crop(raw, OUTPUT_SIZE[0], OUTPUT_SIZE[1], prefer_top=True), (0, 0))
        except Exception as e:
            print(f"      ⚠️  Cover image failed: {e} — using dark background")

    # 55% dark overlay for drama
    overlay = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, int(255 * 0.55)))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    bebas    = _load_bebas(200)       or _default_font(200)
    inter    = _load_inter_medium(14) or _default_font(14)
    inter_sm = _load_inter_medium(13) or _default_font(13)

    try:
        d = datetime.date.fromisoformat(date_str)
        date_label = d.strftime("%b %d").upper()
    except Exception:
        date_label = date_str.upper()

    # "BLANK" wordmark — top left, Inter Medium 13px, white 55%, +8px tracking
    wm_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    _draw_tracked(ImageDraw.Draw(wm_layer), "BLANK", inter_sm,
                  fill=(255, 255, 255, int(255 * 0.55)),
                  tracking_px=8, x=MARGIN, y=52)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), wm_layer).convert("RGB")

    # Vertically center the date + rule + subline block, shifted slightly above center
    dh      = _text_h(bebas)
    sh      = _text_h(inter)
    block_h = dh + 28 + 2 + 24 + sh
    dy      = (OUTPUT_SIZE[1] - block_h) // 2 - 30

    # Date — Bebas 200px, white, +36px tracking, centered
    draw = ImageDraw.Draw(canvas)
    _draw_tracked(draw, date_label, bebas, fill=(255, 255, 255),
                  tracking_px=36, y=dy, center_in_w=OUTPUT_SIZE[0])

    # Thin rule — 80px centered, 2px, white 30%
    rule_y = dy + dh + 28
    rule_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    rule_x = (OUTPUT_SIZE[0] - 80) // 2
    ImageDraw.Draw(rule_layer).line([(rule_x, rule_y), (rule_x + 80, rule_y)],
                                     fill=(255, 255, 255, int(255 * 0.30)), width=2)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), rule_layer).convert("RGB")

    # Subline — Inter Medium 14px, white 60%, all caps, +6px tracking, centered
    sub_y = rule_y + 2 + 24
    sub_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    _draw_tracked(ImageDraw.Draw(sub_layer), subline.upper(), inter,
                  fill=(255, 255, 255, int(255 * 0.60)),
                  tracking_px=6, y=sub_y, center_in_w=OUTPUT_SIZE[0])
    canvas = Image.alpha_composite(canvas.convert("RGBA"), sub_layer).convert("RGB")

    # 1px white border 60% opacity, inset 20px
    bi = BORDER_INSET
    canvas = _alpha_rect(
        canvas,
        (bi, bi, OUTPUT_SIZE[0] - bi - 1, OUTPUT_SIZE[1] - bi - 1),
        outline=(255, 255, 255, int(255 * 0.60)),
    )

    canvas.save(str(out_path), "JPEG", quality=JPEG_QUALITY, optimize=True)


def render_story_slide(
    pick: dict,
    copy: dict,
    img_data: bytes | None,
    is_editors_pick: bool,
    out_path: Path,
) -> None:
    W, H = OUTPUT_SIZE

    # ── Text-only fallback (no image — Reddit posts, etc.) ───────────────────
    if img_data is None:
        canvas = Image.new("RGB", OUTPUT_SIZE, "#080808")
        grad_draw = ImageDraw.Draw(canvas)
        for y in range(H):
            t = y / H
            val = int(28 * (1 - t) + 8 * t)
            grad_draw.line([(0, y), (W - 1, y)], fill=(val, val, val))

        noise_bytes = os.urandom(H * W * 3)
        noise_gray  = Image.frombytes("RGB", (W, H), noise_bytes).convert("L")
        noise_layer = Image.merge("RGBA", (noise_gray, noise_gray, noise_gray,
                                           Image.new("L", (W, H), 10)))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), noise_layer).convert("RGB")

        cr, cg, cb = _hex_to_rgb(RARITY_MAP.get(pick["score"], RARITY_DEFAULT)[1])
        color_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        color_draw  = ImageDraw.Draw(color_layer)
        for y in range(H // 2, H):
            t = (y - H // 2) / (H // 2)
            color_draw.line([(0, y), (W - 1, y)], fill=(cr, cg, cb, int(t * 0.08 * 255)))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), color_layer).convert("RGB")

        bebas_to = _load_bebas(91)        or _default_font(91)
        inter11  = _load_inter_medium(11) or _default_font(11)
        inter12  = _load_inter_medium(12) or _default_font(12)
        inter_to = _load_inter(19)        or _default_font(19)

        category  = copy.get("category", "").upper()
        hook_lines = pick.get("hook_lines") or []
        source    = "VIA " + html.unescape(pick["source"].split("|")[0].strip()).upper()
        content_w = W - MARGIN * 2

        draw_meas = ImageDraw.Draw(canvas)

        # Measure headline
        if hook_lines:
            head_lines = hook_lines[:3]
        else:
            raw_lines  = _wrap_text(draw_meas, pick["title"], bebas_to, content_w)
            head_lines = _truncate_lines(raw_lines, 3, draw_meas, bebas_to, content_w)
        head_lh    = math.ceil(_text_h(bebas_to) * 1.12)
        head_total = len(head_lines) * head_lh

        # Measure why
        why_raw   = _wrap_text(draw_meas, pick["why"], inter_to, content_w)
        why_lines = _truncate_lines(why_raw, 4, draw_meas, inter_to, content_w)
        why_lh    = math.ceil(_text_h(inter_to) * 1.55)
        why_total = len(why_lines) * why_lh

        # Vertically center the block (headline + 20px gap + divider + 24px gap + why)
        block_h  = head_total + 20 + 24 + why_total
        head_y   = (H - block_h) // 2
        div_y    = head_y + head_total + 20
        why_y    = div_y + 24

        source_h = _text_h(inter12)
        source_y = H - TEXT_BOTTOM_PAD - source_h

        # Category badge — top-left
        badge_y   = 52
        cat_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
        _draw_tracked(ImageDraw.Draw(cat_layer), category, inter11,
                      fill=(255, 255, 255, int(255 * 0.70)),
                      tracking_px=6, x=MARGIN, y=badge_y)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), cat_layer).convert("RGB")

        # Rarity badge — top-right (Editor's Pick only)
        if is_editors_pick:
            label, color_hex = RARITY_MAP.get(pick["score"], RARITY_DEFAULT)
            color_rgb  = _hex_to_rgb(color_hex)
            label_chars = list(label)
            label_w    = sum(_char_w(inter12, c) for c in label_chars) + 6 * max(0, len(label_chars) - 1)
            _draw_tracked(ImageDraw.Draw(canvas), label, inter12, fill=color_rgb,
                          tracking_px=6, x=W - MARGIN - label_w, y=badge_y)

        # Source — pinned 72px from bottom
        src_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
        _draw_tracked(ImageDraw.Draw(src_layer), source, inter12,
                      fill=(255, 255, 255, int(255 * 0.55)),
                      tracking_px=4, x=MARGIN, y=source_y)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), src_layer).convert("RGB")

        # Why it matters — Inter 16px, white 80%, 1.55 lh, 4 lines max
        why_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
        wy_draw   = ImageDraw.Draw(why_layer)
        wy = why_y
        for line in why_lines:
            wy_draw.text((MARGIN, wy), line, fill=(255, 255, 255, int(255 * 0.80)), font=inter_to)
            wy += why_lh
        canvas = Image.alpha_composite(canvas.convert("RGBA"), why_layer).convert("RGB")

        # Divider — 60px wide, 2px, white 25%
        div_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
        ImageDraw.Draw(div_layer).line([(MARGIN, div_y), (MARGIN + 60, div_y)],
                                        fill=(255, 255, 255, int(255 * 0.25)), width=2)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), div_layer).convert("RGB")

        # Headline — Bebas 76px, white, 3 lines max
        draw = ImageDraw.Draw(canvas)
        hy = head_y
        for line in head_lines:
            draw.text((MARGIN, hy), line, fill=(255, 255, 255), font=bebas_to)
            hy += head_lh

        # Left accent bar — Editor's Pick only
        if is_editors_pick:
            _, color_hex = RARITY_MAP.get(pick["score"], RARITY_DEFAULT)
            draw.line([(0, 0), (0, H)], fill=_hex_to_rgb(color_hex), width=4)

        # Outer border — 1px, white 20%, inset 20px
        bi = BORDER_INSET
        canvas = _alpha_rect(
            canvas,
            (bi, bi, W - bi - 1, H - bi - 1),
            outline=(255, 255, 255, int(255 * 0.20)),
        )

        canvas.save(str(out_path), "JPEG", quality=JPEG_QUALITY, optimize=True)
        return

    # ── Full-bleed image path ─────────────────────────────────────────────────
    canvas = Image.new("RGB", OUTPUT_SIZE, "#111111")
    try:
        raw = Image.open(BytesIO(img_data)).convert("RGB")
        canvas.paste(_smart_crop(raw, W, H, prefer_top=True), (0, 0))
    except Exception as e:
        print(f"      ⚠️  Image paste failed: {e} — using dark background")

    # ── Gradient overlays ─────────────────────────────────────────────────────
    grad = _gradient_overlay(OUTPUT_SIZE, GRAD_START_Y, 0.92, top_bar=True)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), grad).convert("RGB")

    # ── Fonts ─────────────────────────────────────────────────────────────────
    bebas76 = _load_bebas(100)        or _default_font(100)
    inter11 = _load_inter_medium(11)  or _default_font(11)
    inter12 = _load_inter_medium(12)  or _default_font(12)
    inter16 = _load_inter(23)         or _default_font(23)

    category  = copy.get("category", "").upper()
    # Headline: use hook lines from picks file (already stripped of [TRIGGER:] prefix);
    # fall back to article title if no hook was parsed.
    hook_lines = pick.get("hook_lines") or []
    source    = "VIA " + html.unescape(pick["source"].split("|")[0].strip()).upper()
    content_w = W - MARGIN * 2

    # ── TOP BADGES (sit on the top-bar gradient) ──────────────────────────────
    badge_y = 52

    cat_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    _draw_tracked(ImageDraw.Draw(cat_layer), category, inter11,
                  fill=(255, 255, 255, int(255 * 0.70)),
                  tracking_px=6, x=MARGIN, y=badge_y)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), cat_layer).convert("RGB")

    if is_editors_pick:
        label, color_hex = RARITY_MAP.get(pick["score"], RARITY_DEFAULT)
        color_rgb = _hex_to_rgb(color_hex)
        label_chars = list(label)
        label_w = sum(_char_w(inter12, c) for c in label_chars) + 6 * max(0, len(label_chars) - 1)
        draw = ImageDraw.Draw(canvas)
        _draw_tracked(draw, label, inter12, fill=color_rgb,
                      tracking_px=6, x=W - MARGIN - label_w, y=badge_y)

    # ── BOTTOM TEXT ZONE (built bottom-up) ───────────────────────────────────
    draw_meas = ImageDraw.Draw(canvas)

    source_h  = _text_h(inter12)
    source_y  = H - TEXT_BOTTOM_PAD - source_h

    # Body: full "Why it matters" from the picks file
    why_raw   = _wrap_text(draw_meas, pick["why"], inter16, content_w)
    why_lines = _truncate_lines(why_raw, 3, draw_meas, inter16, content_w)
    why_lh    = math.ceil(_text_h(inter16) * 1.55)
    why_total = len(why_lines) * why_lh
    why_y     = source_y - 20 - why_total

    div_y = why_y - 24

    # Headline: hook lines (pre-formatted) or title word-wrap fallback
    if hook_lines:
        head_lines = hook_lines[:3]  # max 3 hook lines
    else:
        raw_lines  = _wrap_text(draw_meas, pick["title"], bebas76, content_w)
        head_lines = _truncate_lines(raw_lines, 2, draw_meas, bebas76, content_w)
    head_lh    = math.ceil(_text_h(bebas76) * 1.12)
    head_total = len(head_lines) * head_lh
    head_y     = div_y - 20 - head_total

    # Source — Inter Medium 12px, white 55%, +4px tracking
    src_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    _draw_tracked(ImageDraw.Draw(src_layer), source, inter12,
                  fill=(255, 255, 255, int(255 * 0.55)),
                  tracking_px=4, x=MARGIN, y=source_y)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), src_layer).convert("RGB")

    # Why it matters — Inter Regular 19px, white 80%, 1.55 lh, 3 lines max
    why_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    wy_draw   = ImageDraw.Draw(why_layer)
    wy = why_y
    for line in why_lines:
        wy_draw.text((MARGIN, wy), line, fill=(255, 255, 255, int(255 * 0.80)), font=inter16)
        wy += why_lh
    canvas = Image.alpha_composite(canvas.convert("RGBA"), why_layer).convert("RGB")

    # Divider — 60px wide, 2px, white 25%
    div_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(div_layer).line([(MARGIN, div_y), (MARGIN + 60, div_y)],
                                    fill=(255, 255, 255, int(255 * 0.25)), width=2)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), div_layer).convert("RGB")

    # Headline — Bebas 76px, white, 2 lines max
    draw = ImageDraw.Draw(canvas)
    hy = head_y
    for line in head_lines:
        draw.text((MARGIN, hy), line, fill=(255, 255, 255), font=bebas76)
        hy += head_lh

    # Left accent bar — 4px, full height, rarity color (Editor's Pick only)
    if is_editors_pick:
        _, color_hex = RARITY_MAP.get(pick["score"], RARITY_DEFAULT)
        draw.line([(0, 0), (0, H)], fill=_hex_to_rgb(color_hex), width=4)

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
    if len(sys.argv) > 1:
        picks_files = [sys.argv[1]]
        if not os.path.exists(picks_files[0]):
            sys.exit(f"❌  File not found: {picks_files[0]}")
    else:
        picks_files = find_todays_picks_files()

    date_m   = re.search(r"picks-(\d{4}-\d{2}-\d{2})", picks_files[0])
    date_str = date_m.group(1) if date_m else __import__("datetime").date.today().isoformat()

    print(f"\n📰  Digest Publisher")
    print(f"    Picks files : {len(picks_files)} file(s) for {date_str}")
    print(f"    Output dir  : digests/{date_str}/\n")

    all_picks = []
    for pf in picks_files:
        all_picks.extend(parse_picks(pf))
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

    # Source all story images first (cover uses the Editor's Pick image)
    print("    🖼  Sourcing images…")
    story_images: list[bytes | None] = []
    for idx, pick in enumerate(top5):
        is_ep = (idx == editors_pick_idx)
        ep_tag = " [EDITOR'S PICK]" if is_ep else ""
        print(f"  [{idx+1:02d}] {pick['title'][:60]}{ep_tag}")
        img_data = source_story_image(pick)
        story_images.append(img_data)
        print(f"       🖼  {'sourced' if img_data else 'placeholder'}")
        time.sleep(REQUEST_DELAY)

    # Slide 00 — cover (full-bleed Editor's Pick image + overlay)
    cover_path = out_dir / "slide_00_cover.jpg"
    print(f"\n  [00] Cover slide")
    render_cover(date_str, cover_subline, story_images[editors_pick_idx], cover_path)
    print(f"       ✅ {cover_path.name}")

    # Slides 01–05 — stories
    for idx, (pick, copy, img_data) in enumerate(zip(top5, stories_copy, story_images), start=1):
        is_ep = (idx - 1) == editors_pick_idx
        slide_path = out_dir / f"slide_{idx:02d}.jpg"
        render_story_slide(pick, copy, img_data, is_ep, slide_path)
        print(f"  [{idx:02d}] ✅ {slide_path.name}")

    write_digest_md(top5, copy_data, editors_pick_idx, date_str, out_dir)

    print(f"\n  Done — digest saved to digests/{date_str}/\n")


if __name__ == "__main__":
    main()
