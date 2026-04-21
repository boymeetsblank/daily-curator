"""
daily_curator.py — Daily Intelligence Briefing Curator
"""

import os
import sys
import json
import time
import base64
import html
import calendar
from datetime import datetime, timezone, timedelta

import re
import requests
import feedparser
import anthropic
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

ANTHROPIC_API_KEY       = os.environ.get("ANTHROPIC_API_KEY")
INOREADER_APP_ID        = os.environ.get("INOREADER_APP_ID")
INOREADER_APP_KEY       = os.environ.get("INOREADER_APP_KEY")
INOREADER_TOKEN         = os.environ.get("INOREADER_TOKEN")
INOREADER_REFRESH_TOKEN = os.environ.get("INOREADER_REFRESH_TOKEN")
INOREADER_TOKEN_URL     = "https://www.inoreader.com/oauth2/token"
APIFY_API_TOKEN         = os.environ.get("APIFY_API_TOKEN")

HOURS_BACK              = 48
MAX_ARTICLES_TO_SEND    = 150
MAX_ARTICLES_PER_SOURCE = 15
MAX_ARTICLES_HARD_CAP   = 200  # ceiling after per-source cap; trims oldest articles first
MIN_SCORE               = 6
MAX_PICKS               = 30
DIRECT_RSS_TIMEOUT      = 10   # seconds per feed fetch
SOURCES_JSON_PATH       = "sources.json"
SEEN_URLS_PATH          = "seen_urls.json"
SEEN_URLS_WINDOW_DAYS   = 7    # URLs older than this are pruned from the registry
CLAUDE_SCORING_BATCH_SIZE = 50  # max articles per Claude scoring call

INOREADER_BASE_URL   = "https://www.inoreader.com/reader/api/0"


class InoreaderTokenError(Exception):
    """Raised when the Inoreader refresh token is invalid or expired."""


def check_setup():
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not INOREADER_APP_ID:
        missing.append("INOREADER_APP_ID")
    if not INOREADER_APP_KEY:
        missing.append("INOREADER_APP_KEY")
    if not INOREADER_REFRESH_TOKEN:
        missing.append("INOREADER_REFRESH_TOKEN")
    if not APIFY_API_TOKEN:
        missing.append("APIFY_API_TOKEN")
    if missing:
        print("\n❌ Missing required credentials in your .env file:\n")
        for key in missing:
            print(f"   • {key}")
        print("\nPlease add these to your .env file and try again.")
        sys.exit(1)
    print("✅ Credentials loaded successfully.")


def get_fresh_token() -> str:
    """
    Exchange the stored refresh token for a new Inoreader access token.
    Raises InoreaderTokenError on any failure so callers can degrade gracefully
    instead of hard-exiting the process.
    """
    credentials = base64.b64encode(
        f"{INOREADER_APP_ID}:{INOREADER_APP_KEY}".encode()
    ).decode()
    try:
        response = requests.post(
            INOREADER_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": INOREADER_REFRESH_TOKEN,
            },
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        raise InoreaderTokenError(f"Network error during token refresh: {e}") from e
    if response.status_code != 200:
        raise InoreaderTokenError(
            f"HTTP {response.status_code}: {response.text.strip()}"
        )
    return response.json()["access_token"]


def generate_sources_json():
    """Fetch Inoreader subscription list and write sources.json.

    Preserves existing entries' 'enabled' and 'category' metadata so that
    paused/categorised sources survive a re-seed.
    """
    token = get_fresh_token()
    url = f"{INOREADER_BASE_URL}/subscription/list"
    headers = {
        "Authorization": f"Bearer {token}",
        "AppId": INOREADER_APP_ID,
        "AppKey": INOREADER_APP_KEY,
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, params={"output": "json"}, timeout=30)
        resp.raise_for_status()
        subs = resp.json().get("subscriptions", [])

        # Load existing sources so we can preserve metadata (enabled, category)
        existing: dict[str, dict] = {}
        if os.path.exists(SOURCES_JSON_PATH):
            try:
                with open(SOURCES_JSON_PATH, encoding="utf-8") as f:
                    for entry in json.load(f):
                        if entry.get("rss"):
                            existing[entry["rss"]] = entry
            except Exception:
                pass

        sources = []
        for s in subs:
            rss_url = s.get("url", "")
            title   = s.get("title", "Unknown Source")
            if not rss_url:
                continue
            prev = existing.get(rss_url, {})
            sources.append({
                "name":     title,
                "rss":      rss_url,
                "category": prev.get("category", "other"),
                "enabled":  prev.get("enabled", True),
            })

        # Re-add any existing entries whose URLs are not in Inoreader subscriptions
        ino_urls = {s["rss"] for s in sources}
        for rss_url, entry in existing.items():
            if rss_url not in ino_urls:
                sources.append(entry)

        with open(SOURCES_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(sources, f, indent=2, ensure_ascii=False)
        print(f"   ✅ Wrote {len(sources)} sources to {SOURCES_JSON_PATH}")
    except Exception as e:
        print(f"   ⚠️  Could not generate sources.json: {e}")


def _fetch_single_rss_feed(source: dict, cutoff_ts: int) -> list[dict]:
    """Fetch and parse one RSS feed. Returns list of article dicts, or [] on failure."""
    name = source.get("name", "Unknown")
    rss_url = source.get("rss", "")
    if not rss_url:
        return []
    try:
        resp = requests.get(
            rss_url,
            timeout=DIRECT_RSS_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DailyCurator/1.0)"},
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"   ⚠️  Direct RSS fetch failed [{name}]: {e}")
        return []

    feed = feedparser.parse(resp.content)
    articles = []
    for entry in feed.entries:
        # Resolve published timestamp (UTC)
        published_ts = None
        for attr in ("published_parsed", "updated_parsed"):
            t = getattr(entry, attr, None)
            if t:
                try:
                    published_ts = calendar.timegm(t)
                except Exception:
                    pass
                break

        if published_ts and published_ts < cutoff_ts:
            continue  # Too old

        title = (entry.get("title") or "").strip()
        link  = (entry.get("link")  or "").strip()
        if not title or not link:
            continue

        # Summary
        summary = ""
        content_list = entry.get("content")
        if content_list:
            summary = strip_html(content_list[0].get("value", ""))[:500]
        elif entry.get("summary"):
            summary = strip_html(entry.summary)[:500]

        # Published string
        if published_ts:
            published_str = datetime.fromtimestamp(published_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        else:
            published_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Image — check media_content then enclosures
        image_url = None
        media = getattr(entry, "media_content", [])
        if media and isinstance(media, list):
            image_url = media[0].get("url")
        if not image_url:
            for enc in getattr(entry, "enclosures", []):
                if enc.get("type", "").startswith("image/"):
                    image_url = enc.get("href")
                    break

        articles.append({
            "title":     html.unescape(title),
            "link":      link,
            "summary":   summary,
            "source":    name,
            "published": published_str,
            "image":     image_url,
        })

    return articles


def fetch_articles_from_direct_rss() -> list[dict]:
    """Fetch articles from all sources in sources.json in parallel (10 workers, 10s timeout each)."""
    if not os.path.exists(SOURCES_JSON_PATH):
        print(f"   ⚠️  {SOURCES_JSON_PATH} not found — skipping Direct RSS fetch.")
        return []

    try:
        with open(SOURCES_JSON_PATH, encoding="utf-8") as f:
            sources = json.load(f)
    except Exception as e:
        print(f"   ⚠️  Could not read {SOURCES_JSON_PATH}: {e}")
        return []

    if not sources:
        print(f"   ⚠️  {SOURCES_JSON_PATH} is empty — no direct RSS sources to fetch.")
        return []

    active_sources = [s for s in sources if s.get("enabled", True)]
    print(f"\n📡 Fetching {len(active_sources)} direct RSS sources (parallel, {DIRECT_RSS_TIMEOUT}s timeout each)...")
    cutoff_ts = int(time.time() - (HOURS_BACK * 3600))
    articles = []
    succeeded = 0

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_single_rss_feed, src, cutoff_ts): src for src in active_sources}
        for future in as_completed(futures):
            result = future.result()
            if result:
                articles.extend(result)
                succeeded += 1
            else:
                # result is [] — either empty feed or logged failure
                pass

    print(f"   Direct RSS: {len(articles)} articles collected.")
    return articles


def fetch_articles_from_inoreader() -> list[dict]:
    try:
        token = get_fresh_token()
    except InoreaderTokenError as e:
        print(f"\n⚠️  Inoreader token refresh failed — skipping Inoreader fetch.")
        print(f"   {e}")
        return []

    print(f"\n📡 Fetching articles from the last {HOURS_BACK} hours...")
    cutoff_timestamp = int(time.time() - (HOURS_BACK * 3600))
    headers = {
        "Authorization": f"Bearer {token}",
        "AppId": INOREADER_APP_ID,
        "AppKey": INOREADER_APP_KEY,
        "Accept": "application/json",
    }
    params = {
        "n":  MAX_ARTICLES_TO_SEND,
        "ot": cutoff_timestamp,
        "output": "json",
    }
    url = f"{INOREADER_BASE_URL}/stream/contents/user/-/state/com.google/reading-list"
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            print("\n⚠️  Inoreader authentication failed (401) — skipping Inoreader fetch.")
            print("   Your INOREADER_REFRESH_TOKEN may be expired.")
        else:
            print(f"\n⚠️  Inoreader API error: {e} — skipping Inoreader fetch.")
        return []
    except requests.exceptions.ConnectionError:
        print("\n⚠️  Could not connect to Inoreader — skipping Inoreader fetch.")
        return []
    except requests.exceptions.Timeout:
        print("\n⚠️  Inoreader timed out — skipping Inoreader fetch.")
        return []

    data = response.json()
    items = data.get("items", [])
    if not items:
        print(f"   No articles found in the last {HOURS_BACK} hours.")
        return []
    print(f"   Found {len(items)} articles.")

    articles = []
    for item in items:
        title = html.unescape(item.get("title", "Untitled"))
        canonical = item.get("canonical", [])
        link = canonical[0].get("href", "") if canonical else ""
        if not link:
            alternate = item.get("alternate", [])
            link = alternate[0].get("href", "") if alternate else ""
        summary_obj = item.get("summary") or item.get("content", {})
        raw_summary = summary_obj.get("content", "") if isinstance(summary_obj, dict) else ""
        summary = strip_html(raw_summary)[:500]
        origin = item.get("origin") or {}
        source = origin.get("title", "Unknown Source")
        published_timestamp = item.get("published", 0)
        published_dt = datetime.fromtimestamp(published_timestamp, tz=timezone.utc)
        published_str = published_dt.strftime("%Y-%m-%d %H:%M UTC")

        # Extract thumbnail image URL
        import re as _re
        image_url = None
        visual = item.get("visual") or {}
        v_url = visual.get("url")
        if v_url:
            image_url = v_url
        if not image_url and raw_summary:
            img_m = _re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_summary, _re.IGNORECASE)
            if img_m:
                image_url = img_m.group(1)
        if not image_url:
            enclosure = item.get("enclosure")
            if isinstance(enclosure, list):
                enclosure = enclosure[0] if enclosure else None
            if isinstance(enclosure, dict):
                enc_href = enclosure.get("href")
            else:
                enc_href = None
            if enc_href:
                image_url = enc_href

        if title and link:
            articles.append({
                "title":     title,
                "link":      link,
                "summary":   summary,
                "source":    source,
                "published": published_str,
                "image":     image_url,
            })

    print(f"   Processed {len(articles)} articles with valid titles and links.")
    return articles


def _fetch_og_image(url: str) -> str | None:
    """
    Fetch a single article URL and extract its og:image meta tag.
    Returns the image URL string, or None if not found or on any error.
    Hard timeout of 5 seconds.
    """
    try:
        response = requests.get(
            url,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DailyCurator/1.0)"},
            allow_redirects=True,
        )
        if not response.ok:
            return None
        if "html" not in response.headers.get("content-type", ""):
            return None
        # Read only the first 50 KB — <head> is always near the top
        html = response.text[:50000]
        # Match either attribute order: property then content, or content then property
        match = re.search(
            r'<meta[^>]+(?:'
            r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
            r'|content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
            r')',
            html, re.IGNORECASE
        )
        if match:
            return (match.group(1) or match.group(2)).strip() or None
        return None
    except Exception:
        return None


def enrich_articles_with_og_images(articles: list[dict]) -> list[dict]:
    """
    For articles that have no image URL from the RSS feed, fetch the article
    page and extract the og:image meta tag as a fallback.
    Requests run concurrently (up to 10 workers) with a 5-second per-request
    timeout so this step adds minimal time to the overall run.
    """
    needs_og = [a for a in articles if not a.get("image") and a.get("link")]
    if not needs_og:
        return articles

    print(f"\n🖼️  Fetching OG images for {len(needs_og)} articles without thumbnails...")

    found = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_article = {
            executor.submit(_fetch_og_image, article["link"]): article
            for article in needs_og
        }
        for future in as_completed(future_to_article):
            article = future_to_article[future]
            try:
                og_url = future.result()
                if og_url:
                    article["image"] = og_url
                    found += 1
            except Exception:
                pass

    print(f"   ✅ Found OG images for {found}/{len(needs_og)} articles.")
    return articles


def apply_source_cap(articles: list[dict]) -> list[dict]:
    source_counts = {}
    capped = []
    for article in articles:
        source = article["source"]
        count = source_counts.get(source, 0)
        if count < MAX_ARTICLES_PER_SOURCE:
            capped.append(article)
            source_counts[source] = count + 1
    print(f"   After source cap ({MAX_ARTICLES_PER_SOURCE}/source): {len(capped)} articles remaining.")
    return capped


def strip_html(text: str) -> str:
    import re
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def normalize_url(url: str) -> str:
    """
    Strip tracking parameters, URL fragment, and trailing slashes for dedup comparison.
    Also normalises scheme (http→https), hostname (lowercase, strip www.), and default ports.
    Handles UTM params, fbclid, gclid, ref, and other common tracking tokens.
    """
    if not url:
        return url
    try:
        from urllib.parse import urlparse, urlunparse, urlencode, parse_qs
        TRACKING_PARAMS = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',
            'ref', 'referer', 'referrer', 'fbclid', 'gclid', 'msclkid', 'dclid',
            'mc_cid', 'mc_eid', 'mibextid', 'igshid', 'twclid', 'ncid', 'ocid',
            'source', 'campaign', 'cmpid', 'cmp', 'cid', '_ga', 'sr_share',
        }
        parsed = urlparse(url)
        # Normalise scheme: treat http and https as equivalent
        scheme = 'https'
        # Normalise host: lowercase, strip www., strip default ports
        host = parsed.netloc.lower()
        if host.startswith('www.'):
            host = host[4:]
        if host.endswith(':80') or host.endswith(':443'):
            host = host.rsplit(':', 1)[0]
        # Strip tracking params; preserve other query params
        qs = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in qs.items() if k.lower() not in TRACKING_PARAMS}
        new_query = urlencode(cleaned, doseq=True)
        # Lowercase path and strip trailing slash
        path = parsed.path.rstrip('/')
        normalized = urlunparse((scheme, host, path, '', new_query, ''))
        return normalized
    except Exception:
        return url


def dedup_articles_by_url(articles: list[dict]) -> list[dict]:
    """
    Remove articles whose normalized URLs have already been seen in this batch.
    Handles exact URL duplicates, tracking-param variants, http/https, and www/non-www.
    When the same URL appears from multiple sources (e.g. Inoreader + Direct RSS),
    keeps the version with the richest metadata (image > summary length > source name).
    """
    seen: dict[str, int] = {}  # normalized url → index in deduped list
    deduped: list[dict] = []
    removed = 0

    def _meta_score(a: dict) -> tuple:
        return (
            bool(a.get('image')),
            len(a.get('summary') or ''),
            bool(a.get('source')),
        )

    for article in articles:
        link = article.get('link', '')
        if not link:
            deduped.append(article)
            continue
        key = normalize_url(link)
        if key not in seen:
            seen[key] = len(deduped)
            deduped.append(article)
        else:
            # Keep the richer version in-place
            existing_idx = seen[key]
            if _meta_score(article) > _meta_score(deduped[existing_idx]):
                deduped[existing_idx] = article
            removed += 1

    if removed:
        print(f"   URL dedup: removed {removed} duplicate URL(s) (kept richer metadata version).")
    return deduped


# ── Persistent cross-run seen-URL registry ────────────────────────────────────

def load_seen_urls() -> dict[str, str]:
    """
    Load seen_urls.json and return a dict of {normalized_url: iso_timestamp}.
    Returns an empty dict if the file is missing or unreadable.
    """
    if not os.path.exists(SEEN_URLS_PATH):
        return {}
    try:
        with open(SEEN_URLS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("urls", {})
    except Exception:
        return {}


def prune_seen_urls(urls: dict[str, str]) -> dict[str, str]:
    """
    Remove entries older than SEEN_URLS_WINDOW_DAYS days.
    Malformed timestamp entries are also dropped.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=SEEN_URLS_WINDOW_DAYS)
    pruned = {}
    for url, ts_str in urls.items():
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                pruned[url] = ts_str
        except Exception:
            pass  # drop malformed entries
    removed = len(urls) - len(pruned)
    if removed:
        print(f"   Pruned {removed} expired URL(s) from seen registry (>{SEEN_URLS_WINDOW_DAYS}d old).")
    return pruned


def filter_seen_urls(articles: list[dict], seen_urls: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """
    Split articles into (unseen, already_seen) based on the seen registry.
    Already-seen articles are returned separately so their URLs can still be
    added to the registry (they were seen this run even if skipped for scoring).
    """
    if not seen_urls:
        return articles, []
    unseen = []
    already_seen = []
    for article in articles:
        link = article.get("link", "")
        if link and normalize_url(link) in seen_urls:
            already_seen.append(article)
        else:
            unseen.append(article)
    if already_seen:
        print(f"   Cross-run dedup: skipping {len(already_seen)} already-seen article(s) (seen within {SEEN_URLS_WINDOW_DAYS} days).")
    return unseen, already_seen


def update_seen_urls(seen_urls: dict[str, str], articles: list[dict]) -> dict[str, str]:
    """
    Add normalized URLs from this batch of articles to the registry.
    Only real articles (those with a link) are recorded. Trend items are skipped.
    """
    now_str = datetime.now(tz=timezone.utc).isoformat()
    added = 0
    for article in articles:
        link = article.get("link", "")
        if link:
            key = normalize_url(link)
            if key not in seen_urls:
                seen_urls[key] = now_str
                added += 1
    return seen_urls, added


def save_seen_urls(urls: dict[str, str]) -> None:
    """Persist the seen-URL registry to disk."""
    with open(SEEN_URLS_PATH, "w", encoding="utf-8") as f:
        json.dump({"urls": urls}, f, ensure_ascii=False, indent=2)


def _run_apify_actor(actor_id: str, input_data: dict) -> list[dict]:
    """
    Start an Apify actor run, poll until it finishes (up to 60 seconds),
    then return the dataset items.
    Raises on HTTP errors, actor failure, or timeout.
    """
    # Step 1: start the run
    run_resp = requests.post(
        f"https://api.apify.com/v2/acts/{actor_id}/runs",
        json=input_data,
        params={"token": APIFY_API_TOKEN},
        timeout=30,
    )
    run_resp.raise_for_status()
    run_data = run_resp.json()["data"]
    run_id = run_data["id"]
    dataset_id = run_data["defaultDatasetId"]

    # Step 2: poll until finished or 60-second timeout
    deadline = time.time() + 60
    while time.time() < deadline:
        status_resp = requests.get(
            f"https://api.apify.com/v2/acts/{actor_id}/runs/{run_id}",
            params={"token": APIFY_API_TOKEN},
            timeout=10,
        )
        status_resp.raise_for_status()
        status = status_resp.json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify actor run {status.lower()}")
        time.sleep(3)
    else:
        raise TimeoutError("Apify actor run did not finish within 60 seconds")

    # Step 3: fetch dataset items
    items_resp = requests.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items",
        params={"token": APIFY_API_TOKEN},
        timeout=30,
    )
    items_resp.raise_for_status()
    return items_resp.json()


def fetch_twitter_trends() -> list[dict]:
    """
    Fetch top trending topics in the US from X (Twitter) via Apify.
    Returns a list of trend items ready for Claude scoring, or [] if unavailable.
    """
    print(f"\n🐦 Fetching X (Twitter) trends via Apify...")
    try:
        items = _run_apify_actor(
            "karamelo~twitter-trends-scraper",
            {"country": "2", "live": True},  # "2" = United States
        )
        now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        trends = []
        for item in items[:20]:
            name = (item.get("name") or item.get("trend") or
                    item.get("title") or item.get("keyword") or "").strip()
            if not name:
                continue
            trends.append({
                "title":     name,
                "link":      None,
                "summary":   "",
                "source":    "X (Twitter) Trending",
                "published": now_str,
            })
        print(f"   ✅ Got {len(trends)} trending topics from X.")
        return trends
    except Exception as e:
        print(f"   ⚠️  X trends unavailable (continuing without): {e}")
        return []


def fetch_google_trends() -> list[dict]:
    """
    Fetch top trending search terms in the US from Google Trends via Apify.
    Returns a list of trend items ready for Claude scoring, or [] if unavailable.
    """
    print(f"\n📈 Fetching Google Trends via Apify...")
    try:
        items = _run_apify_actor(
            "apify~google-trends-scraper",
            {"searchTerms": [""], "geo": "US"},
        )
        now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        trends = []
        for item in items[:20]:
            name = (item.get("title") or item.get("keyword") or
                    item.get("query") or item.get("topic") or
                    item.get("name") or "").strip()
            if not name:
                continue
            trends.append({
                "title":     name,
                "link":      None,
                "summary":   "",
                "source":    "Google Trends",
                "published": now_str,
            })
        print(f"   ✅ Got {len(trends)} trending topics from Google.")
        return trends
    except Exception as e:
        print(f"   ⚠️  Google Trends unavailable (continuing without): {e}")
        return []


def apply_hard_article_cap(articles: list[dict]) -> list[dict]:
    """
    After per-source capping, enforce a hard ceiling of MAX_ARTICLES_HARD_CAP
    total articles entering the scoring pipeline.  When trimming, keep the
    most recently published articles so the briefing stays timely.
    """
    if len(articles) <= MAX_ARTICLES_HARD_CAP:
        return articles

    def _pub_key(a):
        pub = a.get('published', '') or ''
        for fmt in ('%Y-%m-%d %H:%M UTC', '%Y-%m-%dT%H:%M:%SZ',
                    '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(pub[:len(fmt)], fmt)
            except (ValueError, TypeError):
                pass
        return datetime.min

    trimmed = len(articles) - MAX_ARTICLES_HARD_CAP
    kept = sorted(articles, key=_pub_key, reverse=True)[:MAX_ARTICLES_HARD_CAP]
    print(f"   ⚠️  Hard article cap: trimmed {trimmed} older article(s) "
          f"({len(articles)} → {MAX_ARTICLES_HARD_CAP})")
    return kept


def detect_cross_source_trends(articles: list[dict]) -> list[dict]:
    """
    Identify articles covering the same story across 3+ different sources.
    Adds 'trending_across_sources' and 'trending_source_count' flags.
    """
    if len(articles) < 3:
        for article in articles:
            article["trending_across_sources"] = False
        return articles

    print(f"\n🔍 Detecting cross-source trends...")

    articles_text = ""
    for i, article in enumerate(articles, start=1):
        articles_text += f"""
ARTICLE {i} ({article['source']}):
  Title: {article['title']}
  Summary: {article['summary'][:250] if article['summary'] else '(no summary)'}
---"""

    prompt = f"""Analyze these articles and identify which ones are covering the same story or event.

Group articles by topic/story. For each group, list the article numbers and the sources covering them.

Return ONLY valid JSON in this exact format, with no other text:

{{
  "topic_clusters": [
    {{
      "topic": "Brief description of the story",
      "article_numbers": [1, 3, 5],
      "sources": ["Source A", "Source B", "Source C"]
    }}
  ]
}}

If no articles group together, return:
{{
  "topic_clusters": []
}}

Articles to analyze:
{articles_text}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
    except Exception as e:
        print(f"   ⚠️  Could not detect trends (continuing without): {e}")
        for article in articles:
            article["trending_across_sources"] = False
        return articles

    response_text = response.content[0].text.strip()
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                print("   ⚠️  Could not parse trend response (continuing without).")
                for article in articles:
                    article["trending_across_sources"] = False
                return articles
        else:
            for article in articles:
                article["trending_across_sources"] = False
            return articles

    # Initialize all articles as not trending
    for article in articles:
        article["trending_across_sources"] = False

    # Process each Claude-identified topic group
    trending_count  = 0
    new_cluster_idx = 0
    for cluster in result.get("topic_clusters", []):
        article_nums = cluster.get("article_numbers", [])
        sources      = cluster.get("sources", [])
        num_sources  = len(sources)

        # Only process groups with 2+ valid article references
        valid_nums = [n for n in article_nums if 1 <= n <= len(articles)]
        if len(valid_nums) < 2:
            continue

        # Assign cluster_id to articles that don't already have one from
        # tag_story_clusters().  Existing algorithmic cluster IDs take priority.
        untagged = [n for n in valid_nums if not articles[n - 1].get("cluster_id")]
        if len(untagged) >= 2:
            cid = f"trend_{new_cluster_idx}"
            new_cluster_idx += 1
            actual_sources = list({
                articles[n - 1].get("source", "")
                for n in untagged
                if articles[n - 1].get("source")
            })
            for article_num in untagged:
                articles[article_num - 1].update({
                    "cluster_id":      cid,
                    "cluster_size":    len(untagged),
                    "cluster_sources": actual_sources,
                })

        # Set trending signal for 3+ source clusters (all members, not just untagged)
        if num_sources >= 3:
            for article_num in valid_nums:
                articles[article_num - 1]["trending_across_sources"]  = True
                articles[article_num - 1]["trending_source_count"]    = num_sources
                trending_count += 1

    print(
        f"   ✅ Cross-source trends: {trending_count} articles across 3+ sources; "
        f"{new_cluster_idx} new cluster(s) assigned."
    )
    return articles


def _build_scoring_prompt(articles: list[dict], trending_context_block: str, recently_covered: list[str] | None = None) -> str:
    """Build the Claude scoring prompt for a batch of articles (numbered 1..N)."""
    articles_text = ""
    for i, article in enumerate(articles, start=1):
        trending_flag = ""
        if article.get("trending_across_sources"):
            source_count = article.get("trending_source_count", 3)
            trending_flag = f"\n  🔥 TRENDING: Covered by {source_count} sources"
        articles_text += f"""
ARTICLE {i}:{trending_flag}
  Title:     {article['title']}
  Source:    {article['source']}
  Published: {article['published']}
  Link:      {article['link'] or '(trending topic — no article link)'}
  Summary:   {(article['summary'] or '(no summary — evaluate based on the topic name alone)')[:300]}
---"""

    if recently_covered:
        recently_covered_block = "\n".join(f"- {t}" for t in recently_covered)
    else:
        recently_covered_block = "(none — all stories are fresh)"

    static_preamble = f"""You are a senior editor curating a daily intelligence briefing. Your job is simple: surface what matters today, across any subject, without bias toward any topic or category.

I'll give you a list of recent articles. Evaluate EACH article on these 4 criteria:

1. TRENDING: Is this something a lot of people are actively discussing right now?
2. TIMELY: Use the Published timestamp to apply recency weighting:
   - Published within the last 12 hours → +1 to the final score (very fresh)
   - Published 12–24 hours ago → score normally (still timely)
   - Published 24–48 hours ago → -1 to the final score, UNLESS the story is still actively developing, trending, or unresolved (in which case score normally)
3. CULTURAL: Does it connect to a broader cultural moment, movement, or shift in how people think or behave?
4. SIGNIFICANCE: Is this a story that earns its place in a finite, carefully curated daily briefing?

Score each article from 1–10 overall. Be ruthlessly selective. Most articles should score 4–6.

Scoring anchors:
- 10: A cultural moment — someone will reference this a year from now. Genuinely rare, never forced.
- 9: You have to tell someone about this today.
- 8: You'd bring this up in conversation today.
- 7: Worth your time — earned its place in The Edit.
- 6: Made the cut — relevant and real, but not urgent. A signal for you to tune.
- 1–5: Filtered out — noise, too dry, too predictable, or irrelevant.

When in doubt between a 6 and a 7, score it a 6.

10/10 RARITY RULE: A 10/10 story should feel genuinely rare — roughly once every 1–3 runs, but only when truly earned. Never award 10 just to fill the tier. If nothing clears the bar today, that's correct. When a story genuinely clears this bar, do not hesitate to award it. Holding back a deserved 10 is as much an editorial failure as awarding an undeserved one.

POLITICS RULE: Automatically score any article a 1 if it is primarily about elections, political parties, politicians, legislation, government policy, or partisan issues. This briefing does not cover politics.

CELEBRITY GOSSIP RULE: Automatically score any article a 1 if it is purely about celebrity rumors, relationships, dating, breakups, paparazzi stories, or celebrity gossip. This briefing does not cover celebrity gossip.

CATEGORY DIVERSITY RULE: No single topic area should dominate the high scores in a single run. If multiple stories from the same subject area are scoring 7+, ask yourself whether they are each truly independently significant or whether one is just riding the coattails of another. Diversity of subject matter is a core editorial value — a well-rounded briefing covers the breadth of what matters today, not just what's loudest in one corner of the internet.

RECENTLY COVERED RULE: The following story titles were already featured in this briefing within the past 3 days. If an article covers the SAME underlying story as any item on this list — even from a different source, angle, or with a new headline — score it a 1. Exception: if the article reports a genuinely significant NEW development on the story (e.g. an arrest made, a major reversal, a historic outcome), score it on its own merits as a new story.

Recently covered (do not re-pick):
{recently_covered_block}

TREND ITEMS: Some items have Source "X (Twitter) Trending" or "Google Trends" — these are raw trending topics, not articles. Evaluate them on whether the topic itself is culturally significant and worth a reader's attention. Score them as you would any other item.

CROSS-SOURCE TREND BONUS: If an article is marked with 🔥 TRENDING and covered by 3+ sources, treat this as evidence of cultural relevance. Add 1 point to the score (if it's already strong across other criteria).

CULTURAL VELOCITY SIGNALS: The following topics are currently trending live on X (Twitter) and Google Trends. If an article's subject directly intersects with one of these topics, that's a signal of real-time cultural momentum — treat it as additional evidence for the TRENDING and CULTURAL criteria. Do not add points mechanically; use this to inform your editorial judgment about whether the story is landing in the cultural conversation right now.
{trending_context_block}

For articles that score 6 or above, also provide:
- WHY: 1–2 sentences written as a brief editor's note — explain why this story is significant and why it matters to the reader right now. Write in clear, direct editorial prose. No references to social media, posting, or content.
- HOOK: A scroll-stopping hook for a social media hook slide. Use this exact format:

  [TRIGGER: X] Line one / Line two / Line three

  Rules:
  - TRIGGER must be one of: Curiosity, FOMO, Disbelief, Defensiveness, Relief, Greed
  - Lines separated by /
  - Each line is 7 words or fewer; maximum 3 lines
  - Write it like you're stopping a thumb mid-scroll — visceral, punchy, surprising

IMPORTANT: Return your response as valid JSON in EXACTLY this format, with no other text before or after:

{{
  "evaluations": [
    {{
      "article_number": 1,
      "score": 8,
      "why": "This story marks a turning point in how the industry...",
      "hook": "[TRIGGER: Disbelief] Nobody saw this coming. / Not even the insiders. / It changes everything."
    }},
    {{
      "article_number": 2,
      "score": 4,
      "why": null,
      "hook": null
    }}
  ]
}}

Here are the articles to evaluate:"""

    dynamic_articles = articles_text + "\n\nRemember: Return ONLY the JSON object. No preamble, no explanation, no markdown code blocks."
    return static_preamble, dynamic_articles


def _score_batch(batch: list[dict], trending_context_block: str, label: str, recently_covered: list[str] | None = None) -> list[dict]:
    """
    Score a single batch of articles via Claude.
    Articles are numbered 1..N locally within the batch.
    On parse failure after one retry, logs a warning and returns the batch
    with score=0 rather than terminating the pipeline.
    """
    static_preamble, dynamic_articles = _build_scoring_prompt(batch, trending_context_block, recently_covered)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def call_claude():
        try:
            return client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": static_preamble,
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": dynamic_articles,
                        },
                    ],
                }],
            )
        except anthropic.AuthenticationError:
            print("❌ Claude API key is invalid. Please check your ANTHROPIC_API_KEY.")
            sys.exit(1)
        except anthropic.RateLimitError:
            print("❌ Claude rate limit hit. Please wait a minute and try again.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Claude error: {e}")
            sys.exit(1)

    def parse_response(response):
        response_text = response.content[0].text.strip()
        # Strip markdown code fences if present
        response_text = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.MULTILINE)
        response_text = re.sub(r'\s*```$', '', response_text, flags=re.MULTILINE)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Fall back to extracting the outermost JSON object
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    return None
            return None

    result = parse_response(call_claude())
    if result is None:
        print(f"   ⚠️  Claude returned unexpected format for {label} — retrying once...")
        result = parse_response(call_claude())

    if result is None:
        print(f"   ❌ Claude returned unexpected format for {label} on both attempts — assigning score 0 to this batch.")
        for article in batch:
            article.setdefault("score", 0)
            article.setdefault("why", None)
            article.setdefault("hook", None)
        return batch

    evaluations = result.get("evaluations", [])
    eval_by_number = {e["article_number"]: e for e in evaluations if e.get("article_number") is not None}
    enriched = []
    for i, article in enumerate(batch, start=1):
        eval_data = eval_by_number.get(i, {})
        article["score"] = eval_data.get("score", 0)
        article["why"]   = eval_data.get("why")
        article["hook"]  = eval_data.get("hook")
        enriched.append(article)

    return enriched


def evaluate_articles_with_claude(articles: list[dict], trending_topics: list[str] | None = None, recently_covered: list[str] | None = None) -> list[dict]:
    if not articles:
        return []

    # Build the trending context block once — shared across all batches
    if trending_topics:
        topics_list = "\n".join(f"  • {t}" for t in trending_topics[:30])
        trending_context_block = f"Live trending topics right now:\n{topics_list}"
        print(f"   📊 Injecting {len(trending_topics[:30])} live trending topics into scoring prompt.")
    else:
        trending_context_block = "(No live trending data available for this run.)"

    total = len(articles)
    batches = [articles[i:i + CLAUDE_SCORING_BATCH_SIZE] for i in range(0, total, CLAUDE_SCORING_BATCH_SIZE)]
    n_batches = len(batches)

    if n_batches == 1:
        print(f"\n🤖 Sending {total} articles to Claude for evaluation...")
    else:
        print(f"\n🤖 Scoring {total} articles in {n_batches} batches of up to {CLAUDE_SCORING_BATCH_SIZE}...")

    enriched = []
    for n, batch in enumerate(batches, 1):
        label = f"batch {n}/{n_batches}" if n_batches > 1 else "batch"
        print(f"   Scoring {label} ({len(batch)} items)...")
        enriched.extend(_score_batch(batch, trending_context_block, label, recently_covered))

    print(f"✅ Claude evaluated all {len(enriched)} articles.")
    return enriched


CLUSTER_SIMILARITY_THRESHOLD = 0.65   # minimum title similarity to consider same story
CLUSTER_MAX_SIZE             = 6      # max articles kept per cluster (by score, post-scoring)

# Common English stopwords for entity extraction
_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'up', 'as', 'is', 'was', 'are', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'shall', 'can',
    'not', 'no', 'its', 'it', 'this', 'that', 'these', 'those', 'how',
    'why', 'what', 'when', 'where', 'who', 'which', 'after', 'before',
    'over', 'under', 'about', 'into', 'through', 'during', 'just', 'now',
    'new', 'says', 'said', 'report', 'reports', 'first', 'show', 'shows',
    'til', 'ama', 'lpt', 'eli5', 'smh', 'fyi', 'imo', 'imho', 'psa', 'dae', 'ask',
}


def _extract_primary_entity(title: str) -> str | None:
    """
    Extract the primary named entity from an article title.
    Returns the first run of 1–3 consecutive title-cased words that are not
    stopwords, lowercased and space-joined.  Returns None if nothing found.
    """
    words = re.sub(r'[^\w\s\'-]', ' ', title).split()
    entity_words: list[str] = []
    for word in words:
        clean = re.sub(r"['\-]", '', word)
        if clean and clean[0].isupper() and clean.lower() not in _STOPWORDS and len(clean) > 1:
            entity_words.append(clean.lower())
            if len(entity_words) == 3:
                break
        else:
            if entity_words:
                break  # end of consecutive run
    return ' '.join(entity_words) if entity_words else None


def _parse_published_ts(published: str) -> int | None:
    """Parse 'YYYY-MM-DD HH:MM UTC' → Unix timestamp, or None on failure."""
    if not published:
        return None
    try:
        return int(datetime.strptime(published[:16], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        return None


def _title_similarity(a: str, b: str) -> float:
    """Normalized similarity ratio between two cleaned article titles (0.0–1.0)."""
    from difflib import SequenceMatcher
    a_clean = re.sub(r'[^\w\s]', '', a.lower().strip())
    b_clean = re.sub(r'[^\w\s]', '', b.lower().strip())
    return SequenceMatcher(None, a_clean, b_clean).ratio()


def tag_story_clusters(articles: list[dict]) -> list[dict]:
    """
    Group articles by title similarity (≥ CLUSTER_SIMILARITY_THRESHOLD) using union-find.
    Tags each article with:
      - cluster_id   : str  — shared label for all members of a cluster (None for singletons)
      - cluster_size : int  — number of articles in the cluster (1 for singletons)
      - cluster_sources : list[str] — distinct source names in the cluster

    For clusters with 3+ distinct sources, also sets:
      - trending_across_sources = True
      - trending_source_count   = number of distinct sources

    All articles are kept in the batch — nothing is dropped.
    Replaces the old deduplicate_articles_pre_scoring() call.
    """
    from collections import defaultdict

    n = len(articles)
    if n == 0:
        return articles

    # ── Union-Find ─────────────────────────────────────────────────
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            sim = _title_similarity(
                articles[i].get('title', ''),
                articles[j].get('title', ''),
            )
            if sim >= CLUSTER_SIMILARITY_THRESHOLD:
                union(i, j)

    # ── Secondary pass: entity + time-window clustering ────────────
    # If two articles share the same primary named entity AND were published
    # within 6 hours of each other, group them regardless of title similarity.
    SIX_HOURS = 6 * 3600
    entities  = [_extract_primary_entity(a.get('title', '')) for a in articles]
    pub_times = [_parse_published_ts(a.get('published', '')) for a in articles]

    for i in range(n):
        if not entities[i] or pub_times[i] is None:
            continue
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            if not entities[j] or pub_times[j] is None:
                continue
            if entities[i] == entities[j] and abs(pub_times[i] - pub_times[j]) <= SIX_HOURS:
                union(i, j)

    # ── Group by root ──────────────────────────────────────────────
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    # ── Tag articles ───────────────────────────────────────────────
    cluster_idx = 0
    clustered_articles = 0
    for root, members in groups.items():
        if len(members) == 1:
            # Singleton — minimal tags, no cluster_id
            articles[members[0]].update({
                'cluster_id':      None,
                'cluster_size':    1,
                'cluster_sources': [articles[members[0]].get('source', '')],
            })
            continue

        cid = f"c{cluster_idx}"
        cluster_idx += 1
        sources = list({articles[m].get('source', '') for m in members if articles[m].get('source')})
        clustered_articles += len(members)

        for m in members:
            articles[m].update({
                'cluster_id':      cid,
                'cluster_size':    len(members),
                'cluster_sources': sources,
            })

        # Set cross-source trend signal for 3+ distinct sources
        if len(sources) >= 3:
            for m in members:
                articles[m]['trending_across_sources']  = True
                articles[m]['trending_source_count']    = len(sources)

    if cluster_idx > 0:
        print(f"   Story clustering: {clustered_articles} articles → {cluster_idx} cluster(s).")
    else:
        print("   Story clustering: no duplicate titles found.")
    return articles


def mark_cluster_primaries(articles: list[dict]) -> list[dict]:
    """
    After scoring, mark the highest-scoring article in each cluster as
    cluster_primary=True.  Singletons are always their own primary.

    Handles clusters from both tag_story_clusters() (IDs like "c0", "c1") and
    detect_cross_source_trends() (IDs like "trend_0", "trend_1") — any non-None
    cluster_id is treated the same way.

    Call this immediately after evaluate_articles_with_claude().
    """
    # Find best score per cluster
    best: dict[str, tuple[int, int]] = {}  # cluster_id → (score, idx)
    for i, a in enumerate(articles):
        cid = a.get('cluster_id')
        if cid is None:
            continue
        score = a.get('score', 0)
        if cid not in best or score > best[cid][0]:
            best[cid] = (score, i)

    primaries_marked = 0
    for i, a in enumerate(articles):
        cid = a.get('cluster_id')
        if cid is None:
            a['cluster_primary'] = True   # singletons are always primary
            continue
        is_primary = (best.get(cid, (None, -1))[1] == i)
        a['cluster_primary'] = is_primary
        if is_primary:
            primaries_marked += 1

    if primaries_marked:
        print(f"   Cluster primaries marked: {primaries_marked} cluster(s).")
    return articles


def cap_cluster_sizes(articles: list[dict]) -> list[dict]:
    """
    After scoring and marking cluster primaries, limit each cluster to at most
    CLUSTER_MAX_SIZE total members (primary + non-primaries).  If a cluster has
    more members, the lowest-scoring non-primaries are dropped.
    Singletons are always kept.
    """
    from collections import defaultdict

    # Group non-primary members by cluster_id
    nonprimaries: dict[str, list[dict]] = defaultdict(list)
    for a in articles:
        cid = a.get('cluster_id')
        if cid and not a.get('cluster_primary', True):
            nonprimaries[cid].append(a)

    # Identify articles to drop
    to_drop: set[int] = set()
    trimmed = 0
    for cid, members in nonprimaries.items():
        # Primary always survives, so budget = CLUSTER_MAX_SIZE - 1 non-primaries
        budget = CLUSTER_MAX_SIZE - 1
        if len(members) > budget:
            sorted_members = sorted(members, key=lambda a: a.get('score', 0), reverse=True)
            for excess in sorted_members[budget:]:
                to_drop.add(id(excess))
                trimmed += 1

    if not trimmed:
        return articles

    kept = [a for a in articles if id(a) not in to_drop]
    print(f"   Cluster cap ({CLUSTER_MAX_SIZE}/cluster): trimmed {trimmed} excess member(s) from oversized cluster(s).")
    return kept


def deduplicate_after_scoring(articles: list[dict]) -> list[dict]:
    """
    After scoring, identify any same-topic duplicates that survived pre-scoring
    dedup and cluster capping. Uses a broader 'same underlying event or topic'
    prompt to catch sparse-entity matches (e.g. two arrest headlines naming the
    subject differently). Only inspects articles scoring >= MIN_SCORE.
    Keeps the highest-scored duplicate; ties broken by metadata richness.
    """
    candidates = [a for a in articles if a.get("score", 0) >= MIN_SCORE]
    if len(candidates) <= 1:
        return articles

    print(f"\n🔍 Post-scoring dedup: checking {len(candidates)} scored picks for same-topic duplicates...")

    articles_text = ""
    for i, article in enumerate(candidates, start=1):
        snippet = (article.get('summary') or '')[:120] or '(no summary)'
        articles_text += f"{i}. [{article['score']}/10] \"{article['title']}\" ({article['source']})\n   {snippet}\n"

    prompt = f"""Here are {len(candidates)} articles that scored highly in an editorial evaluation. Some may cover the same underlying event or topic — even if their headlines use different phrasing, name the same person differently, or focus on different angles of the same story.

{articles_text}

Your job:
1. Identify groups of articles about the same underlying event or topic. Use BROAD matching — for example:
   - Two headlines about the same person's arrest, even if one names the victim and the other describes them differently
   - Two headlines about the same person leaving a company, even if worded differently
   - Two articles about the same product launch, album drop, or sports result from different angles
2. Do NOT group articles that are merely in the same category (e.g. two unrelated sports stories). They must be the same specific event.
3. Articles covering genuinely different stories should not be listed.

Return ONLY valid JSON in this exact format, with no other text:

{{
  "clusters": [
    {{
      "topic": "Brief description of the shared underlying event",
      "article_numbers": [1, 4]
    }}
  ]
}}

If no articles cover the same underlying event, return:
{{
  "clusters": []
}}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def _call(p):
        try:
            return client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                messages=[{"role": "user", "content": p}]
            ).content[0].text.strip()
        except Exception as e:
            print(f"   ⚠️  Post-scoring dedup API call failed: {e}")
            return None

    def _parse(text):
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return None

    result = _parse(_call(prompt))
    if result is None:
        print("   ⚠️  Post-scoring dedup: Claude returned unparseable JSON — retrying with stricter prompt...")
        strict = prompt + "\n\nIMPORTANT: Your previous response could not be parsed as JSON. Return ONLY the raw JSON object with absolutely no other text, no markdown, no code fences."
        result = _parse(_call(strict))
    if result is None:
        print("   ❌ Post-scoring dedup SKIPPED — Claude returned unparseable JSON on both attempts.")
        return articles

    clusters = result.get("clusters", [])
    if not clusters:
        print("   ✅ No same-topic duplicates found after scoring.")
        return articles

    def _richness(article):
        score = 0
        if article.get('image'):
            score += 2
        score += min(len(article.get('summary') or ''), 500) // 100
        if article.get('why'):
            score += 1
        return score

    merged = 0
    for cluster in clusters:
        nums = cluster.get("article_numbers", [])
        topic = cluster.get("topic", "unknown topic")
        valid = [n for n in nums if 1 <= n <= len(candidates)]
        if len(valid) < 2:
            continue
        cluster_arts = [(n, candidates[n - 1]) for n in valid]
        winner_num, winner_art = max(cluster_arts, key=lambda x: (x[1]["score"], _richness(x[1])))

        # Assign or adopt a cluster_id for the winner
        cid = winner_art.get("cluster_id") or f"pd{winner_num}"
        winner_art["cluster_id"] = cid
        winner_art["cluster_primary"] = True

        # Collect all source names for the cluster_sources field
        all_sources = list(dict.fromkeys(
            art["source"] for _, art in cluster_arts if art.get("source")
        ))
        if len(all_sources) > 1:
            winner_art["cluster_sources"] = all_sources

        for num, art in cluster_arts:
            if num != winner_num:
                art["cluster_id"] = cid
                art["cluster_primary"] = False
                merged += 1
                print(f"   ↩️  Post-dedup ({topic}): kept \"{art['title'][:60]}\" as perspective (score {art['score']})")

    if not merged:
        print("   ✅ No same-topic duplicates found after scoring.")
        return articles

    print(f"   Post-scoring dedup: merged {merged} article(s) into perspective panels.")
    return articles


def select_top_picks(articles: list[dict]) -> list[dict]:
    strong = [a for a in articles if a.get("score", 0) >= MIN_SCORE]
    primaries = [a for a in strong if a.get("cluster_primary", True) is not False]
    primaries.sort(key=lambda a: a["score"], reverse=True)
    top = primaries[:MAX_PICKS]
    selected_cids = {a["cluster_id"] for a in top if a.get("cluster_id")}
    members = [
        a for a in strong
        if a.get("cluster_primary") is False and a.get("cluster_id") in selected_cids
    ]
    return top + members


def filter_already_picked_today(picks: list[dict]) -> list[dict]:
    """
    Remove picks whose URLs already appear in any picks file saved today.
    Uses normalized URLs to catch tracking-parameter variants of the same URL.
    """
    import glob as glob_module

    today_str = datetime.now().strftime("%Y-%m-%d")
    pattern = f"picks/picks-{today_str}-*.md"
    existing_files = glob_module.glob(pattern)

    if not existing_files:
        return picks

    already_picked_urls: set[str] = set()
    url_pattern = r"\[Read the full article →\]\((https?://[^\)]+)\)"
    for filepath in existing_files:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        for url in re.findall(url_pattern, content):
            already_picked_urls.add(normalize_url(url))

    if not already_picked_urls:
        return picks

    filtered = []
    for pick in picks:
        if normalize_url(pick.get("link", "")) in already_picked_urls:
            print(f"   ↩️  Already picked today: \"{pick['title'][:60]}\"")
        else:
            filtered.append(pick)

    removed = len(picks) - len(filtered)
    if removed:
        print(f"   Cross-run dedup: removed {removed} already-picked article(s).")
    return filtered


def load_recently_covered_topics(days: int = 3) -> list[str]:
    """
    Return "Title — Why summary" strings from the last N days of picks files.
    Used to inject into the scoring prompt so Claude can suppress re-picks
    of the same underlying story across runs and across days.
    """
    import glob as glob_module
    entries = []
    today = datetime.now().date()
    for filepath in glob_module.glob("picks/picks-*.md"):
        m = re.search(r"picks-(\d{4}-\d{2}-\d{2})-", filepath)
        if not m:
            continue
        try:
            file_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - file_date).days > days:
            continue
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        for title, why in re.findall(
            r"\*\*([^*\n]+)\*\*\n\*[^*\n]+\*\n\[Read the full article"
            r".*?\n\n\*\*Why it (?:matters|scored high):\*\*\n(.*?)(?=\n\n\*\*Hook|\n\n\*\*Suggested|\n\n---|\Z)",
            content, re.DOTALL
        ):
            why_short = re.sub(r'\s+', ' ', why.strip())[:120]
            entries.append(f"{title.strip()} — {why_short}")
    return entries


def write_all_articles_json(evaluated_articles: list[dict], exclude_urls: set[str] | None = None) -> str:
    """
    Write scored articles (before MIN_SCORE / MAX_PICKS filters) to all_articles/.
    Articles whose normalized URLs appear in exclude_urls are omitted — this ensures
    The Feed only shows stories that did NOT make The Edit.
    Trend items (no link) are always excluded.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    time_str  = datetime.now().strftime("%H%M")
    os.makedirs("all_articles", exist_ok=True)
    filename = f"all_articles/all-{today_str}-{time_str}.json"

    excluded = exclude_urls or set()
    articles = []
    actually_excluded = 0
    for a in evaluated_articles:
        link = a.get("link")
        if not link:
            continue  # drop trend items (no URL)
        if normalize_url(link) in excluded:
            actually_excluded += 1
            continue  # drop articles that made The Edit
        articles.append({
            "title":           a.get("title", ""),
            "source":          a.get("source", ""),
            "link":            link,
            "score":           a.get("score", 0),
            "why":             a.get("why"),
            "hook":            a.get("hook"),
            "image":           a.get("image"),
            "published":       a.get("published"),
            "cluster_id":      f"{today_str}-{time_str}-{a['cluster_id']}" if a.get("cluster_id") else None,
            "cluster_size":    a.get("cluster_size", 1),
            "cluster_primary": a.get("cluster_primary", True),
            "cluster_sources": a.get("cluster_sources"),
        })

    # Sort by score descending so highest-signal articles appear first within the run
    articles.sort(key=lambda a: a["score"], reverse=True)

    data = {"date": today_str, "time": time_str, "articles": articles}
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"   📁 Saved {len(articles)} Feed articles → {filename}"
          + (f" ({actually_excluded} Edit pick(s) excluded)" if actually_excluded else ""))
    return filename


def write_markdown_output(
    picks: list[dict],
    all_articles_count: int,
    twitter_trends: list[dict] = None,
    inoreader_unavailable: bool = False,
) -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H%M")
    os.makedirs("picks", exist_ok=True)
    filename = f"picks/picks-{today_str}-{time_str}.md"

    x_trends_line = ""
    if twitter_trends:
        names = [t["title"] for t in twitter_trends if t.get("title")]
        if names:
            x_trends_line = f"\n> **X Trends:** {' · '.join(names)}"

    ino_note = (
        "\n> ⚠️ **Inoreader unavailable** — sources reflect Direct RSS only for this run."
        if inoreader_unavailable else ""
    )
    source_label = "Direct RSS feeds" if inoreader_unavailable else "Inoreader feeds"

    content = f"""# Daily Content Picks — {today_str} at {datetime.now().strftime("%I:%M %p")}

> **Source:** {source_label} from the last {HOURS_BACK} hours
> **Articles reviewed:** {all_articles_count}
> **Picks surfaced:** {len(picks)} (minimum score: {MIN_SCORE}/10){x_trends_line}{ino_note}

---

"""
    if not picks:
        content += f"""## No Strong Picks Today

None of today's {all_articles_count} articles scored {MIN_SCORE} or above.

This is normal — not every day has strong enough signal. Check back tomorrow!
"""
    else:
        for i, pick in enumerate(picks, start=1):
            if pick['link']:
                link_line = f"[Read the full article →]({pick['link']})"
            elif pick['source'] == "X (Twitter) Trending":
                link_line = "*Trending on X right now*"
            elif pick['source'] == "Google Trends":
                link_line = "*Trending on Google right now*"
            else:
                link_line = ""
            image_line = f"\n**Image:** {pick['image']}" if pick.get('image') else ""
            hook_section = f"\n**Hook:**\n{pick['hook']}\n" if pick.get('hook') else ""

            # Cluster metadata lines (omitted for singletons / trend items)
            cluster_lines = ""
            if pick.get('cluster_id'):
                cid       = pick['cluster_id']
                csize     = pick.get('cluster_size', 1)
                cprimary  = "true" if pick.get('cluster_primary', True) else "false"
                csources  = " · ".join(pick.get('cluster_sources') or [])
                cluster_lines = (
                    f"\n**Cluster ID:** {cid}"
                    f"\n**Cluster Size:** {csize}"
                    f"\n**Cluster Primary:** {cprimary}"
                    + (f"\n**Cluster Sources:** {csources}" if csources else "")
                )

            content += f"""## Pick #{i} — Score: {pick['score']}/10

**{pick['title']}**
*{pick['source']}*
{link_line}{image_line}{cluster_lines}

**Why it matters:**
{pick.get('why', 'N/A')}
{hook_section}
---

"""
    content += f"""*Generated by Daily Curator on {datetime.now().strftime("%Y-%m-%d at %H:%M")}*
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename


def _get_today_pick_urls() -> set[str]:
    """
    Return normalized URLs for every article already picked in today's earlier runs.
    Used to ensure those articles are also excluded from The Feed, even when they
    were removed from top_picks by filter_already_picked_today().
    """
    import glob as glob_module
    today_str = datetime.now().strftime("%Y-%m-%d")
    pattern = f"picks/picks-{today_str}-*.md"
    existing_files = glob_module.glob(pattern)
    urls: set[str] = set()
    url_pattern = r"\[Read the full article →\]\((https?://[^\)]+)\)"
    for filepath in existing_files:
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            for url in re.findall(url_pattern, content):
                urls.add(normalize_url(url))
        except Exception:
            pass
    return urls


def main():
    print("\n" + "=" * 55)
    print("  📰 Daily Curator — Content Scouting with Claude AI")
    print("=" * 55)

    check_setup()

    # ── Inoreader token health check ──────────────────────────────────────────
    # Try to refresh the token before any fetching.  If it fails, the run
    # continues on Direct RSS only — a partial run beats no run.
    print("\n🔑 Checking Inoreader token...")
    inoreader_available = True
    try:
        get_fresh_token()
        print("   ✅ Inoreader token is valid.")
    except InoreaderTokenError as e:
        inoreader_available = False
        print(f"\n⚠️  Inoreader token invalid — this run will use Direct RSS only.")
        print(f"   Details: {e}")
        print("   Run get_inoreader_token.py locally to obtain a fresh refresh token,")
        print("   then update the INOREADER_REFRESH_TOKEN secret in GitHub.")

    # ── Load persistent seen-URL registry (rolling 7-day window) ─────────────
    print("\n📋 Loading seen-URL registry...")
    seen_urls = load_seen_urls()
    seen_urls = prune_seen_urls(seen_urls)
    print(f"   Registry: {len(seen_urls)} known URL(s) from the past {SEEN_URLS_WINDOW_DAYS} days.")

    # Auto-generate sources.json from Inoreader subscriptions on first run
    if not os.path.exists(SOURCES_JSON_PATH):
        if inoreader_available:
            print("\n📋 sources.json not found — generating from Inoreader subscriptions...")
            generate_sources_json()
        else:
            print("\n⚠️  sources.json not found and Inoreader is unavailable — Direct RSS only.")

    # Fetch Inoreader and Direct RSS in parallel (or Direct RSS only if token expired)
    if inoreader_available:
        print("\n🔀 Fetching Inoreader and Direct RSS in parallel...")
        with ThreadPoolExecutor(max_workers=2) as ex:
            ino_future = ex.submit(fetch_articles_from_inoreader)
            rss_future = ex.submit(fetch_articles_from_direct_rss)
            inoreader_articles = ino_future.result()
            direct_rss_articles = rss_future.result()
    else:
        print("\n🔀 Fetching Direct RSS only (Inoreader unavailable)...")
        inoreader_articles = []
        direct_rss_articles = fetch_articles_from_direct_rss()

    print(f"   Inoreader: {len(inoreader_articles)} articles | Direct RSS: {len(direct_rss_articles)} articles")
    articles = inoreader_articles + direct_rss_articles
    articles = enrich_articles_with_og_images(articles)

    if not articles:
        print(f"\n⚠️  No articles found from the last {HOURS_BACK} hours.")
        sys.exit(0)

    articles = apply_source_cap(articles)
    articles = dedup_articles_by_url(articles)

    # ── Cross-run dedup: skip articles already seen in the past 7 days ───────
    print(f"\n🔍 Checking articles against seen-URL registry...")
    articles, skipped_articles = filter_seen_urls(articles, seen_urls)
    if articles:
        print(f"   {len(articles)} unseen article(s) will proceed to scoring.")

    # ── Hard cap: keep at most MAX_ARTICLES_HARD_CAP articles entering scoring ─
    articles = apply_hard_article_cap(articles)

    # ── Phase 1 story clustering: fuzzy title matching ───────────────────────
    print(f"\n🔗 Clustering articles by title similarity (threshold {CLUSTER_SIMILARITY_THRESHOLD:.0%})...")
    articles = tag_story_clusters(articles)
    articles = detect_cross_source_trends(articles)
    twitter_trends = fetch_twitter_trends()
    google_trends = fetch_google_trends()
    all_items = articles + twitter_trends + google_trends

    # Extract plain topic names from trend items for the velocity signal prompt
    trending_topics = [t["title"] for t in twitter_trends + google_trends if t.get("title")]

    # ── Topic-level cross-run dedup: load recent pick titles for Claude to suppress ──
    recently_covered = load_recently_covered_topics(days=3)
    if recently_covered:
        print(f"   📚 Loaded {len(recently_covered)} recently-covered topic(s) for dedup.")

    evaluated_articles = evaluate_articles_with_claude(all_items, trending_topics=trending_topics, recently_covered=recently_covered)

    # ── Mark highest-scorer in each cluster as the primary ───────────────────
    print(f"\n🔗 Marking cluster primaries...")
    evaluated_articles = mark_cluster_primaries(evaluated_articles)

    # ── Cap oversized clusters to CLUSTER_MAX_SIZE members ───────────────────
    evaluated_articles = cap_cluster_sizes(evaluated_articles)

    # ── Post-scoring dedup: catch same-topic pairs that survived clustering ───
    evaluated_articles = deduplicate_after_scoring(evaluated_articles)

    # ── Update seen-URL registry with everything scored this run ─────────────
    seen_urls, new_count = update_seen_urls(seen_urls, evaluated_articles)
    save_seen_urls(seen_urls)
    print(f"   📋 Seen registry updated: +{new_count} new URL(s), {len(seen_urls)} total.")

    top_picks = select_top_picks(evaluated_articles)

    print(f"\n🔎 Filtering already-picked URLs...")
    top_picks = filter_already_picked_today(top_picks)

    # Prune non-primary cluster members whose primary was removed by cross-run dedup.
    # Without this, orphaned members appear as separate picks in The Edit and can't
    # be grouped on the website because their primary is absent.
    surviving_primary_cids = {
        p["cluster_id"] for p in top_picks
        if p.get("cluster_primary") is not False and p.get("cluster_id")
    }
    orphaned = [
        p for p in top_picks
        if p.get("cluster_primary") is False
        and p.get("cluster_id")
        and p["cluster_id"] not in surviving_primary_cids
    ]
    if orphaned:
        top_picks = [p for p in top_picks if p not in orphaned]
        print(f"   Pruned {len(orphaned)} orphaned cluster member(s) whose primary was already picked.")

    # Build set of normalized pick URLs to exclude from The Feed.
    # Include both this run's new picks AND any picks from earlier runs today —
    # filter_already_picked_today() may have removed articles that scored highly
    # but were already in The Edit, and their URLs must still be excluded.
    pick_urls = {normalize_url(p["link"]) for p in top_picks if p.get("link")}
    prior_today_urls = _get_today_pick_urls()
    prior_only = prior_today_urls - pick_urls
    if prior_only:
        print(f"   +{len(prior_only)} URL(s) from earlier runs today added to Feed exclusion set.")
    pick_urls |= prior_today_urls

    print(f"\n📁 Saving Feed articles (excluding {len(pick_urls)} Edit pick URL(s))...")
    write_all_articles_json(evaluated_articles, exclude_urls=pick_urls)

    print(f"\n📝 Writing output file...")
    output_file = write_markdown_output(
        top_picks, len(all_items), twitter_trends,
        inoreader_unavailable=not inoreader_available,
    )

    print(f"\n{'=' * 55}")
    if top_picks:
        print(f"  ✅ Found {len(top_picks)} strong pick(s) today!\n")
        for i, pick in enumerate(top_picks, start=1):
            print(f"  #{i} [{pick['score']}/10] {pick['title'][:55]}...")
        print(f"\n  📄 Full details saved to: {output_file}")
    else:
        print(f"  📭 No strong picks today (nothing scored {MIN_SCORE}+).")
        print(f"  📄 Report saved to: {output_file}")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()