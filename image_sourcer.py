"""
image_sourcer.py — Source and format Instagram-ready images for daily picks.

Reads the latest picks/*.md, sources one image per story via priority chain:
  1. og:image scraped from the article URL (min 600px on either dimension)
  2. Unsplash API — keywords extracted by Claude Haiku
  3. Pexels API  — same keywords
  4. Placeholder — #F5F5F5 canvas with Bebas Neue headline text

Outputs 1080×1080 JPEG (quality 95) to images/YYYY-MM-DD/, named by slug.
Usage:  python image_sourcer.py [picks/picks-YYYY-MM-DD-HHMM.md]
"""

import glob
import html
import json
import os
import re
import sys
import time
import unicodedata
from io import BytesIO
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY      = os.environ.get("PEXELS_API_KEY")

MIN_IMAGE_DIM  = 600        # px — minimum side for og:image to be acceptable
OUTPUT_SIZE    = (1080, 1080)
BORDER_COLOR   = "#111111"
BORDER_INSET   = 24         # px from each edge
JPEG_QUALITY   = 95
REQUEST_DELAY  = 0.4        # seconds between network calls (rate limiting)

_BEBAS_URL = (
    "https://github.com/dharmatype/Bebas-Neue/raw/master/"
    "fonts/BebasNeue%282018%29ByDhamraType/TTF/BebasNeue-Regular.ttf"
)
_FONT_CACHE = Path("fonts/BebasNeue-Regular.ttf")

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ImageSourcer/1.0)"}


# ── Picks parsing ─────────────────────────────────────────────────────────────

def find_latest_picks_file() -> str:
    files = sorted(glob.glob("picks/picks-*.md"), reverse=True)
    if not files:
        sys.exit("❌  No picks files found in picks/")
    return files[0]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-+", "-", text)[:80].strip("-")


def parse_picks(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    picks = []
    for block in re.split(r"\n## Pick #\d+", content)[1:]:
        # Title + source (first bold/italic pair)
        tm = re.search(r"\*\*([^*\n]+)\*\*\n\*([^*\n]+)\*", block)
        if not tm:
            continue
        title  = tm.group(1).strip()
        source = tm.group(2).strip()

        # Article link — trend items have no link; skip them
        lm = re.search(r"\[Read the full article →\]\(([^)]+)\)", block)
        if not lm:
            continue
        link = lm.group(1).strip()

        # Existing image URL (may contain HTML entities from the picks writer)
        im = re.search(r"\*\*Image:\*\*\s*(\S+)", block)
        existing_image = html.unescape(im.group(1)) if im else None

        # Cluster primary — articles with no cluster metadata are standalone primaries
        cp = re.search(r"\*\*Cluster Primary:\*\*\s*(true|false)", block)
        cluster_primary = (cp.group(1) == "true") if cp else True

        if not cluster_primary:
            continue  # skip perspective articles; one image per story

        picks.append({
            "title":          title,
            "source":         source,
            "link":           link,
            "existing_image": existing_image,
        })

    return picks


# ── Network helpers ───────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 12, **kwargs) -> requests.Response | None:
    try:
        r = requests.get(url, timeout=timeout, headers=_HTTP_HEADERS, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"      ⚠️  GET failed ({url[:70]}): {e}")
        return None


def _fetch_image_bytes(url: str) -> bytes | None:
    r = _get(url)
    return r.content if r else None


def _meets_size(data: bytes) -> bool:
    try:
        img = Image.open(BytesIO(data))
        return max(img.size) >= MIN_IMAGE_DIM
    except Exception:
        return False


# ── Image sourcing chain ──────────────────────────────────────────────────────

def source_og_image(link: str, existing_url: str | None) -> bytes | None:
    # 1a — try the image already extracted by the curator pipeline
    if existing_url:
        data = _fetch_image_bytes(existing_url)
        if data and _meets_size(data):
            return data

    # 1b — scrape article page for og:image
    r = _get(link)
    if not r:
        return None
    try:
        soup = BeautifulSoup(r.content, "html.parser")
        tag = (
            soup.find("meta", property="og:image")
            or soup.find("meta", attrs={"name": "twitter:image"})
        )
        if tag:
            og_url = tag.get("content", "").strip()
            if og_url:
                # Resolve relative URLs
                if og_url.startswith("//"):
                    og_url = "https:" + og_url
                data = _fetch_image_bytes(og_url)
                if data and _meets_size(data):
                    return data
    except Exception as e:
        print(f"      ⚠️  OG scrape error: {e}")
    return None


def _extract_keywords(title: str) -> list[str]:
    if not ANTHROPIC_API_KEY:
        return [w for w in title.split() if len(w) > 4][:3] or ["news"]
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{
                "role": "user",
                "content": (
                    'Extract 2-3 concise visual search keywords for finding a relevant stock photo. '
                    'Return ONLY a JSON array of strings, no markdown, no other text.\n\n'
                    f'Headline: "{title}"'
                ),
            }],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"      ⚠️  Keyword extraction failed: {e}")
        return [w for w in title.split() if len(w) > 4][:3] or ["news"]


def source_unsplash(keywords: list[str]) -> bytes | None:
    if not UNSPLASH_ACCESS_KEY:
        return None
    r = _get(
        "https://api.unsplash.com/search/photos",
        params={"query": " ".join(keywords), "per_page": 5, "orientation": "squarish"},
        headers={**_HTTP_HEADERS, "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
    )
    if not r:
        return None
    for photo in r.json().get("results", []):
        url = photo.get("urls", {}).get("regular")
        if url:
            data = _fetch_image_bytes(url)
            if data and _meets_size(data):
                return data
    return None


def source_pexels(keywords: list[str]) -> bytes | None:
    if not PEXELS_API_KEY:
        return None
    r = _get(
        "https://api.pexels.com/v1/search",
        params={"query": " ".join(keywords), "per_page": 5, "orientation": "square"},
        headers={**_HTTP_HEADERS, "Authorization": PEXELS_API_KEY},
    )
    if not r:
        return None
    for photo in r.json().get("photos", []):
        url = photo.get("src", {}).get("large")
        if url:
            data = _fetch_image_bytes(url)
            if data and _meets_size(data):
                return data
    return None


# ── Image formatting ──────────────────────────────────────────────────────────

def _load_bebas_neue(size: int = 68) -> ImageFont.FreeTypeFont | None:
    if not _FONT_CACHE.exists():
        _FONT_CACHE.parent.mkdir(parents=True, exist_ok=True)
        print("   📥 Downloading Bebas Neue font…", end=" ", flush=True)
        r = _get(_BEBAS_URL, timeout=20)
        if r:
            _FONT_CACHE.write_bytes(r.content)
            print("done.")
        else:
            print("failed — using default font.")
            return None
    try:
        return ImageFont.truetype(str(_FONT_CACHE), size=size)
    except Exception as e:
        print(f"      ⚠️  Font load failed: {e}")
        return None


def _make_placeholder(title: str) -> Image.Image:
    img  = Image.new("RGB", OUTPUT_SIZE, color="#F5F5F5")
    draw = ImageDraw.Draw(img)

    font = _load_bebas_neue(size=68)
    if font is None:
        try:
            font = ImageFont.load_default(size=48)
        except TypeError:
            font = ImageFont.load_default()

    pad   = 80
    max_w = OUTPUT_SIZE[0] - pad * 2

    # Word-wrap
    words, lines, current = title.split(), [], []
    for word in words:
        test_line = " ".join(current + [word])
        try:
            w = draw.textlength(test_line, font=font)
        except Exception:
            w = len(test_line) * 30
        if w <= max_w:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))

    # Measure line height
    try:
        bbox = font.getbbox("A")
        line_h = (bbox[3] - bbox[1]) + 14
    except Exception:
        line_h = 60

    total_h = len(lines) * line_h
    y = (OUTPUT_SIZE[1] - total_h) / 2

    for line in lines:
        try:
            w = draw.textlength(line, font=font)
        except Exception:
            w = len(line) * 30
        x = (OUTPUT_SIZE[0] - w) / 2
        draw.text((x, y), line, fill="#111111", font=font)
        y += line_h

    return img


def format_image(data: bytes | None, title: str) -> Image.Image:
    img: Image.Image | None = None

    if data:
        try:
            raw = Image.open(BytesIO(data)).convert("RGB")
            w, h  = raw.size
            side  = min(w, h)
            left  = (w - side) // 2
            top   = (h - side) // 2
            raw   = raw.crop((left, top, left + side, top + side))
            img   = raw.resize(OUTPUT_SIZE, Image.LANCZOS)
        except Exception as e:
            print(f"      ⚠️  Image open/crop failed: {e} — using placeholder")

    if img is None:
        img = _make_placeholder(title)

    # 1 px inset border at BORDER_INSET from each edge
    draw = ImageDraw.Draw(img)
    i = BORDER_INSET
    draw.rectangle(
        [i, i, OUTPUT_SIZE[0] - i - 1, OUTPUT_SIZE[1] - i - 1],
        outline=BORDER_COLOR,
        width=1,
    )

    return img


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    picks_file = sys.argv[1] if len(sys.argv) > 1 else find_latest_picks_file()
    if not os.path.exists(picks_file):
        sys.exit(f"❌  File not found: {picks_file}")

    date_m = re.search(r"picks-(\d{4}-\d{2}-\d{2})", picks_file)
    date_str = date_m.group(1) if date_m else __import__("datetime").date.today().isoformat()

    print(f"\n🖼️   Image Sourcer")
    print(f"    Picks file : {picks_file}")
    print(f"    Output dir : images/{date_str}/\n")

    picks = parse_picks(picks_file)
    if not picks:
        print("⚠️  No cluster-primary picks found — nothing to do.")
        return

    print(f"    {len(picks)} story/stories to source.\n")

    out_dir = Path(f"images/{date_str}")
    out_dir.mkdir(parents=True, exist_ok=True)

    sourced, placeholder, skipped = 0, 0, 0

    for idx, pick in enumerate(picks, start=1):
        title = pick["title"]
        slug  = slugify(title)
        dest  = out_dir / f"{slug}.jpg"

        print(f"  [{idx:02d}/{len(picks):02d}] {title[:65]}")

        if dest.exists():
            print(f"          ⏭  exists — skipping")
            skipped += 1
            continue

        # ── Priority 1: og:image ──────────────────────────────────────────
        img_data = source_og_image(pick["link"], pick["existing_image"])
        source_label = "og:image"

        # ── Priority 2 & 3: stock photo APIs ─────────────────────────────
        if img_data is None:
            keywords = _extract_keywords(title)
            kw_str   = " · ".join(keywords)
            print(f"          🔍 keywords: {kw_str}")

            time.sleep(REQUEST_DELAY)
            img_data = source_unsplash(keywords)
            source_label = "Unsplash"

            if img_data is None:
                time.sleep(REQUEST_DELAY)
                img_data = source_pexels(keywords)
                source_label = "Pexels"

        # ── Priority 4: placeholder ───────────────────────────────────────
        if img_data is None:
            source_label = "placeholder"
            placeholder += 1
        else:
            sourced += 1

        img = format_image(img_data, title)
        img.save(str(dest), "JPEG", quality=JPEG_QUALITY, optimize=True)
        print(f"          ✅ {source_label} → {dest.name}")

        time.sleep(REQUEST_DELAY)

    total = sourced + placeholder + skipped
    print(f"\n  Done — {sourced} sourced, {placeholder} placeholder(s), {skipped} skipped  ({total} total)")
    print(f"  Images saved to: images/{date_str}/\n")


if __name__ == "__main__":
    main()
