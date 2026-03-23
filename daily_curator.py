"""
daily_curator.py — Daily Content Curator for Instagram, TikTok, and Substack
"""

import os
import sys
import json
import time
import base64
from datetime import datetime, timezone, timedelta

import requests
import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY       = os.environ.get("ANTHROPIC_API_KEY")
INOREADER_APP_ID        = os.environ.get("INOREADER_APP_ID")
INOREADER_APP_KEY       = os.environ.get("INOREADER_APP_KEY")
INOREADER_TOKEN         = os.environ.get("INOREADER_TOKEN")
INOREADER_REFRESH_TOKEN = os.environ.get("INOREADER_REFRESH_TOKEN")
INOREADER_TOKEN_URL     = "https://www.inoreader.com/oauth2/token"

HOURS_BACK              = 48
MAX_ARTICLES_TO_SEND    = 60
MAX_ARTICLES_PER_SOURCE = 5
MIN_SCORE               = 7
MAX_PICKS               = 10

INOREADER_BASE_URL   = "https://www.inoreader.com/reader/api/0"


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
    if missing:
        print("\n❌ Missing required credentials in your .env file:\n")
        for key in missing:
            print(f"   • {key}")
        print("\nPlease add these to your .env file and try again.")
        sys.exit(1)
    print("✅ Credentials loaded successfully.")


def get_fresh_token() -> str:
    credentials = base64.b64encode(
        f"{INOREADER_APP_ID}:{INOREADER_APP_KEY}".encode()
    ).decode()
    response = requests.post(
        INOREADER_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": INOREADER_REFRESH_TOKEN,
        },
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
    )
    if response.status_code != 200:
        print("❌ Could not refresh Inoreader token.")
        print("Your INOREADER_REFRESH_TOKEN may be expired.")
        sys.exit(1)
    return response.json()["access_token"]


def fetch_articles_from_inoreader() -> list[dict]:
    token = get_fresh_token()
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
            print("\n❌ Inoreader authentication failed.")
            print("Your INOREADER_REFRESH_TOKEN may be expired.")
        else:
            print(f"\n❌ Inoreader API error: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to Inoreader. Check your internet connection.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("\n❌ Inoreader took too long to respond. Try again in a moment.")
        sys.exit(1)

    data = response.json()
    items = data.get("items", [])
    if not items:
        print(f"   No articles found in the last {HOURS_BACK} hours.")
        return []
    print(f"   Found {len(items)} articles.")

    articles = []
    for item in items:
        title = item.get("title", "Untitled")
        canonical = item.get("canonical", [])
        link = canonical[0].get("href", "") if canonical else ""
        if not link:
            alternate = item.get("alternate", [])
            link = alternate[0].get("href", "") if alternate else ""
        summary_obj = item.get("summary") or item.get("content", {})
        raw_summary = summary_obj.get("content", "") if summary_obj else ""
        summary = strip_html(raw_summary)[:500]
        origin = item.get("origin", {})
        source = origin.get("title", "Unknown Source")
        published_timestamp = item.get("published", 0)
        published_dt = datetime.fromtimestamp(published_timestamp, tz=timezone.utc)
        published_str = published_dt.strftime("%Y-%m-%d %H:%M UTC")
        if title and link:
            articles.append({
                "title":     title,
                "link":      link,
                "summary":   summary,
                "source":    source,
                "published": published_str,
            })

    print(f"   Processed {len(articles)} articles with valid titles and links.")
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
            model="claude-opus-4-6",
            max_tokens=2048,
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

    # Mark articles in clusters with 3+ sources
    trending_count = 0
    for cluster in result.get("topic_clusters", []):
        article_nums = cluster.get("article_numbers", [])
        sources = cluster.get("sources", [])
        num_sources = len(sources)

        if num_sources >= 3:
            for article_num in article_nums:
                if 1 <= article_num <= len(articles):
                    articles[article_num - 1]["trending_across_sources"] = True
                    articles[article_num - 1]["trending_source_count"] = num_sources
                    trending_count += 1

    print(f"   ✅ Found {trending_count} articles trending across 3+ sources.")
    return articles


def fetch_google_trends() -> list[str]:
    """
    Fetch the top trending searches in the US from Google Trends.
    Returns a list of trending topic strings, or an empty list if unavailable.
    """
    print(f"\n📈 Fetching Google Trends...")
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        df = pytrends.trending_searches(pn="united_states")
        topics = df[0].tolist()[:20]
        print(f"   ✅ Got {len(topics)} trending topics from Google.")
        return topics
    except ImportError:
        print("   ⚠️  pytrends not installed — skipping Google Trends.")
        return []
    except Exception as e:
        print(f"   ⚠️  Google Trends unavailable (continuing without): {e}")
        return []


def evaluate_articles_with_claude(articles: list[dict], trending_topics: list[str] = None) -> list[dict]:
    print(f"\n🤖 Sending {len(articles)} articles to Claude for evaluation...")
    print("   (This may take 15–30 seconds...)\n")

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
  Link:      {article['link']}
  Summary:   {article['summary'] or '(no summary available)'}
---"""

    google_trends_section = ""
    if trending_topics:
        topics_list = "\n".join(f"- {t}" for t in trending_topics)
        google_trends_section = f"""
GOOGLE TRENDS CONTEXT: These are the top trending searches in the US right now:
{topics_list}

GOOGLE TRENDS BONUS: If an article's topic closely matches one of these trending searches, treat it as additional evidence that people are actively searching for this right now. Add 1–2 points to the score (only if the article is already strong on other criteria).

"""

    prompt = f"""You are a content strategist for culture-forward media accounts on Instagram, TikTok, and Substack.

I'll give you a list of recent articles. Evaluate EACH article on these 4 criteria:

1. TRENDING: Is this something a lot of people are actively discussing right now?
2. TIMELY: Did this happen or break in the last 24–48 hours? Is it fresh?
3. CULTURAL: Does it connect to a broader cultural moment, meme, movement, or viral conversation?
4. CAROUSEL: Could this become a carousel post that a culture-forward media account would post?

Score each article from 1–10 overall. Be ruthlessly selective. A 7+ means this is genuinely strong. Most articles should score 4–6.

POLITICS RULE: Automatically score any article a 1 if it is primarily about elections, political parties, politicians, legislation, government policy, or partisan issues. This account does not cover politics.

CELEBRITY GOSSIP RULE: Automatically score any article a 1 if it is purely about celebrity rumors, relationships, dating, breakups, paparazzi stories, or celebrity gossip. This account does not cover celebrity gossip.

CROSS-SOURCE TREND BONUS: If an article is marked with 🔥 TRENDING and covered by 3+ sources, treat this as strong evidence of cultural relevance. Add 1–2 points to the score (if it's already strong across other criteria).
{google_trends_section}
For articles that score 7 or above, also provide:
- WHY: 1–2 sentences explaining why it scored high
- ANGLE: A carousel hook following these rules:

CAROUSEL HOOK RULES:
- Identify which psychological trigger the hook uses: Curiosity, FOMO, Disbelief, Defensiveness, Relief, or Greed
- Write the hook with intentional line breaks using "/" to show where each break goes
- Each line must be 7 words or fewer
- Maximum 3 lines total
- The hook must stop the scroll — it should feel punchy, not like a headline

Format the ANGLE field like this:
"[TRIGGER: Disbelief] The last Laker to score 60 / was Kobe. / In his final game."

IMPORTANT: Return your response as valid JSON in EXACTLY this format, with no other text before or after:

{{
  "evaluations": [
    {{
      "article_number": 1,
      "score": 8,
      "why": "This story is being widely shared...",
      "angle": "Hook: 'Everyone is talking about X...'"
    }},
    {{
      "article_number": 2,
      "score": 4,
      "why": null,
      "angle": null
    }}
  ]
}}

Here are the articles to evaluate:
{articles_text}

Remember: Return ONLY the JSON object. No preamble, no explanation, no markdown code blocks."""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
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
                print("❌ Claude returned an unexpected format.")
                sys.exit(1)
        else:
            print("❌ Could not parse Claude's response as JSON.")
            sys.exit(1)

    evaluations = result.get("evaluations", [])
    eval_by_number = {e["article_number"]: e for e in evaluations}
    enriched_articles = []
    for i, article in enumerate(articles, start=1):
        eval_data = eval_by_number.get(i, {})
        article["score"] = eval_data.get("score", 0)
        article["why"]   = eval_data.get("why")
        article["angle"] = eval_data.get("angle")
        enriched_articles.append(article)

    print(f"✅ Claude evaluated all {len(enriched_articles)} articles.")
    return enriched_articles


def select_top_picks(articles: list[dict]) -> list[dict]:
    strong_picks = [a for a in articles if a["score"] >= MIN_SCORE]
    strong_picks.sort(key=lambda a: a["score"], reverse=True)
    return strong_picks[:MAX_PICKS]


def deduplicate_within_run(picks: list[dict]) -> list[dict]:
    """
    Drop lower-scoring picks that cover the same story as a higher-scoring pick.
    Uses simple word-overlap on titles. Picks must already be sorted by score descending.
    """
    import re

    def title_words(title: str) -> set:
        stopwords = {"the", "a", "an", "of", "in", "on", "at", "to", "for",
                     "is", "are", "was", "were", "and", "or", "but", "with",
                     "how", "why", "what", "who", "as", "by", "its", "it"}
        words = re.findall(r"[a-z]+", title.lower())
        return {w for w in words if w not in stopwords and len(w) > 2}

    kept = []
    for pick in picks:
        words = title_words(pick["title"])
        duplicate = False
        for existing in kept:
            existing_words = title_words(existing["title"])
            if not words or not existing_words:
                continue
            overlap = len(words & existing_words) / min(len(words), len(existing_words))
            if overlap >= 0.6:
                duplicate = True
                print(f"   ↩️  Deduped (same story): \"{pick['title'][:60]}\"")
                break
        if not duplicate:
            kept.append(pick)

    removed = len(picks) - len(kept)
    if removed:
        print(f"   Within-run dedup: removed {removed} duplicate(s).")
    return kept


def filter_already_picked_today(picks: list[dict]) -> list[dict]:
    """
    Remove picks whose URLs already appear in any picks file saved today.
    """
    import glob as glob_module

    today_str = datetime.now().strftime("%Y-%m-%d")
    pattern = f"picks/picks-{today_str}-*.md"
    existing_files = glob_module.glob(pattern)

    if not existing_files:
        return picks

    already_picked_urls = set()
    url_pattern = r"\[Read the full article →\]\((https?://[^\)]+)\)"
    import re
    for filepath in existing_files:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        for url in re.findall(url_pattern, content):
            already_picked_urls.add(url)

    if not already_picked_urls:
        return picks

    filtered = []
    for pick in picks:
        if pick["link"] in already_picked_urls:
            print(f"   ↩️  Already picked today: \"{pick['title'][:60]}\"")
        else:
            filtered.append(pick)

    removed = len(picks) - len(filtered)
    if removed:
        print(f"   Cross-run dedup: removed {removed} already-picked article(s).")
    return filtered


def write_markdown_output(picks: list[dict], all_articles_count: int) -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H%M")
    os.makedirs("picks", exist_ok=True)
    filename = f"picks/picks-{today_str}-{time_str}.md"

    content = f"""# Daily Content Picks — {today_str} at {datetime.now().strftime("%I:%M %p")}

> **Source:** Inoreader feeds from the last {HOURS_BACK} hours
> **Articles reviewed:** {all_articles_count}
> **Picks surfaced:** {len(picks)} (minimum score: {MIN_SCORE}/10)

---

"""
    if not picks:
        content += f"""## No Strong Picks Today

None of today's {all_articles_count} articles scored {MIN_SCORE} or above.

This is normal — not every day has carousel-worthy content. Check back tomorrow!
"""
    else:
        for i, pick in enumerate(picks, start=1):
            content += f"""## Pick #{i} — Score: {pick['score']}/10

**{pick['title']}**
*{pick['source']}*
[Read the full article →]({pick['link']})

**Why it scored high:**
{pick.get('why', 'N/A')}

**Suggested carousel angle / hook:**
{pick.get('angle', 'N/A')}

---

"""
    content += f"""*Generated by Daily Curator on {datetime.now().strftime("%Y-%m-%d at %H:%M")}*
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename


def main():
    print("\n" + "=" * 55)
    print("  📰 Daily Curator — Content Scouting with Claude AI")
    print("=" * 55)

    check_setup()
    articles = fetch_articles_from_inoreader()

    if not articles:
        print(f"\n⚠️  No articles found from the last {HOURS_BACK} hours.")
        sys.exit(0)

    articles = apply_source_cap(articles)
    articles = detect_cross_source_trends(articles)
    google_trends = fetch_google_trends()
    evaluated_articles = evaluate_articles_with_claude(articles, trending_topics=google_trends)
    top_picks = select_top_picks(evaluated_articles)

    print(f"\n🔎 Deduplicating picks...")
    top_picks = deduplicate_within_run(top_picks)
    top_picks = filter_already_picked_today(top_picks)

    print(f"\n📝 Writing output file...")
    output_file = write_markdown_output(top_picks, len(articles))

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