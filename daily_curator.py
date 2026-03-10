"""
daily_curator.py — Daily Content Curator for Instagram, TikTok, and Substack

WHAT THIS SCRIPT DOES:
  1. Connects to your Inoreader account and pulls articles from the last 24–48 hours
  2. Sends those articles to Claude (AI) to score on 4 criteria:
       - Is it trending right now?
       - Is it timely (last 24–48 hours)?
       - Does it connect to something cultural or viral?
       - Could it work as a culturally significant carousel?
  3. Surfaces only the top 5 picks (only if they score above 7/10)
  4. Saves a markdown file named picks-YYYY-MM-DD.md

HOW TO RUN:
  1. Set up your .env file (see .env.example)
  2. Install dependencies: pip install -r requirements.txt
  3. Run: python3 daily_curator.py

UNDERSTANDING THE CODE:
  - Lines starting with # are comments — notes for humans, ignored by the computer
  - Lines starting with \"\"\" are docstrings — descriptions of functions
  - Everything else is actual code

LEARNING TIP:
  Don't try to understand every line at once. Read the comments to follow the
  overall flow, and look up anything you're curious about as you go.
"""

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS — Loading the tools we need (like loading apps on your phone)
# ─────────────────────────────────────────────────────────────────────────────

import os           # Lets Python talk to your operating system (read env vars)
import sys          # Lets us exit the program cleanly if something goes wrong
import json         # Lets Python read and write JSON (a common data format)
import time         # Gives us access to the current time and date
from datetime import datetime, timezone, timedelta  # More precise date/time tools

import requests     # Lets Python make web requests (like a browser, but in code)
import anthropic    # Lets Python talk to Claude AI

# python-dotenv lets us read API keys from a .env file instead of hardcoding them
from dotenv import load_dotenv


# ─────────────────────────────────────────────────────────────────────────────
# SETUP — Load secrets and configure settings
# ─────────────────────────────────────────────────────────────────────────────

# Load all the secrets from your .env file into Python's environment
# This reads lines like: ANTHROPIC_API_KEY=sk-ant-...
# and makes them available via os.environ.get()
load_dotenv()

# Read each API key/credential from the environment
ANTHROPIC_API_KEY    = os.environ.get("ANTHROPIC_API_KEY")
INOREADER_APP_ID     = os.environ.get("INOREADER_APP_ID")
INOREADER_APP_KEY    = os.environ.get("INOREADER_APP_KEY")
INOREADER_TOKEN      = os.environ.get("INOREADER_TOKEN")

# Settings you can adjust:
HOURS_BACK           = 48    # How many hours back to look for articles (24 or 48)
MAX_ARTICLES_TO_SEND = 60    # Max articles to send Claude at once (keeps cost down)
MIN_SCORE            = 7     # Only show picks that score this or higher
MAX_PICKS            = 5     # Maximum number of picks to show

# The Inoreader API base URL — all requests start with this
INOREADER_BASE_URL   = "https://www.inoreader.com/reader/api/0"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: CHECK SETUP
# ─────────────────────────────────────────────────────────────────────────────

def check_setup():
    """
    Checks that all required API keys are present before we do anything else.
    If anything is missing, it tells the user exactly what to fix and exits.
    """
    missing = []  # Start with an empty list of missing items

    # Check each required key — if it's missing (None) or empty, add to list
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not INOREADER_APP_ID:
        missing.append("INOREADER_APP_ID")
    if not INOREADER_APP_KEY:
        missing.append("INOREADER_APP_KEY")
    if not INOREADER_TOKEN:
        missing.append("INOREADER_TOKEN")

    # If any keys are missing, tell the user and stop the program
    if missing:
        print("\n❌ Missing required credentials in your .env file:\n")
        for key in missing:
            print(f"   • {key}")
        print("\nPlease add these to your .env file and try again.")
        print("See .env.example for the format.\n")
        sys.exit(1)  # Exit with error code 1 (means "something went wrong")

    print("✅ Credentials loaded successfully.")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: FETCH ARTICLES FROM INOREADER
# ─────────────────────────────────────────────────────────────────────────────

def fetch_articles_from_inoreader() -> list[dict]:
    """
    Connects to Inoreader and retrieves articles published in the last
    HOURS_BACK hours (default: 48 hours).

    Returns:
        A list of article dictionaries. Each dictionary (dict) is like a
        mini-record with fields like "title", "link", "summary", "source".

    About the Inoreader API:
        Inoreader uses a Google Reader-compatible API. We're using the
        "stream/contents" endpoint to get our reading list items.
        We filter by timestamp to only get recent articles.
    """

    print(f"\n📡 Fetching articles from the last {HOURS_BACK} hours...")

    # Calculate the "not older than" timestamp.
    # time.time() gives us the current time as a number (Unix timestamp).
    # We subtract HOURS_BACK * 3600 seconds to get HOURS_BACK hours ago.
    cutoff_timestamp = int(time.time() - (HOURS_BACK * 3600))

    # These are the HTTP headers we send with every Inoreader request.
    # Headers are metadata that tell the server who we are and how we're
    # authorized to access the data.
    headers = {
        "Authorization": f"Bearer {INOREADER_TOKEN}",
        "AppId": INOREADER_APP_ID,
        "AppKey": INOREADER_APP_KEY,
        "Accept": "application/json",
    }

    # These are "query parameters" — options we send in the URL to filter results.
    # It's like adding filters when you search for something online.
    params = {
        "n":  MAX_ARTICLES_TO_SEND,  # Max number of articles to return
        "ot": cutoff_timestamp,       # "older than" — only items NEWER than this
        "output": "json",             # We want the response in JSON format
    }

    # Build the URL for the Inoreader reading list endpoint
    url = f"{INOREADER_BASE_URL}/stream/contents/user/-/state/com.google/reading-list"

    # Make the web request to Inoreader
    # requests.get() is like opening a URL in your browser, but in Python
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        # .raise_for_status() checks if the request was successful.
        # If the server returned an error (like 401 "Unauthorized" or
        # 404 "Not Found"), this will raise an exception that we can catch.
        response.raise_for_status()

    except requests.exceptions.HTTPError as e:
        # This catches HTTP errors (like wrong credentials, server errors, etc.)
        if response.status_code == 401:
            print("\n❌ Inoreader authentication failed.")
            print("Your INOREADER_TOKEN may be expired or incorrect.")
            print("Please generate a new token (see README for instructions).")
        else:
            print(f"\n❌ Inoreader API error: {e}")
        sys.exit(1)

    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to Inoreader. Check your internet connection.")
        sys.exit(1)

    except requests.exceptions.Timeout:
        print("\n❌ Inoreader took too long to respond. Try again in a moment.")
        sys.exit(1)

    # Parse the JSON response into a Python dictionary
    # JSON is a text format that represents structured data — like a spreadsheet
    # stored as text. .json() converts it into Python objects we can work with.
    data = response.json()

    # The articles are inside data["items"] — a list of article objects
    items = data.get("items", [])

    if not items:
        print(f"   No articles found in the last {HOURS_BACK} hours.")
        return []

    print(f"   Found {len(items)} articles.")

    # Now we extract the useful fields from each article
    articles = []

    for item in items:
        # Get the title — use a fallback if it's missing
        title = item.get("title", "Untitled")

        # Get the URL/link — articles can have multiple links, we take the first
        # The "canonical" list usually contains the main article URL
        canonical = item.get("canonical", [])
        link = canonical[0].get("href", "") if canonical else ""

        # Also check "alternate" links if canonical was empty
        if not link:
            alternate = item.get("alternate", [])
            link = alternate[0].get("href", "") if alternate else ""

        # Get the article summary/snippet
        # Inoreader stores the content in a nested structure:
        # item["summary"]["content"] or item["content"]["content"]
        summary_obj = item.get("summary") or item.get("content", {})
        raw_summary = summary_obj.get("content", "") if summary_obj else ""

        # Strip HTML tags from the summary (we just want plain text)
        # This is a simple approach — good enough for our needs
        summary = strip_html(raw_summary)

        # Limit summary length to avoid sending too much text to Claude
        # [:500] takes the first 500 characters
        summary = summary[:500]

        # Get the source/feed name
        origin = item.get("origin", {})
        source = origin.get("title", "Unknown Source")

        # Get the publication timestamp (when the article was published)
        # Inoreader uses "published" as a Unix timestamp (seconds since 1970)
        published_timestamp = item.get("published", 0)
        published_dt = datetime.fromtimestamp(published_timestamp, tz=timezone.utc)
        published_str = published_dt.strftime("%Y-%m-%d %H:%M UTC")

        # Build a clean article record and add it to our list
        # Only include articles that have at least a title and a link
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


def strip_html(text: str) -> str:
    """
    Removes HTML tags from text.

    HTML tags look like <p>, <div>, <strong>, etc. We don't want those
    in the text we send to Claude — just the plain words.

    This is a simple version that works for most cases.
    For a more robust solution, a library like BeautifulSoup would be used,
    but we're keeping dependencies minimal here.
    """
    import re  # "re" is Python's tool for pattern matching (called regex)

    # Remove everything that looks like <tag> or </tag>
    # re.sub() finds patterns and replaces them with something else
    # r'<[^>]+>' is the pattern: "< followed by anything that's not >, then >"
    clean = re.sub(r'<[^>]+>', ' ', text)

    # Replace multiple spaces with a single space
    clean = re.sub(r'\s+', ' ', clean)

    return clean.strip()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: EVALUATE ARTICLES WITH CLAUDE
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_articles_with_claude(articles: list[dict]) -> list[dict]:
    """
    Sends all articles to Claude and asks it to score each one on 4 criteria.

    Claude evaluates:
      1. Trending — Is a lot of people talking about this right now?
      2. Timely    — Did it happen in the last 24–48 hours?
      3. Cultural  — Does it connect to something cultural or viral?
      4. Carousel  — Would it make a culturally significant carousel post?

    Returns:
        A list of article dictionaries enriched with:
          - "score": the overall score (1–10)
          - "why": why it scored high (1–2 sentences)
          - "angle": suggested carousel angle or hook
    """

    print(f"\n🤖 Sending {len(articles)} articles to Claude for evaluation...")
    print("   (This may take 15–30 seconds...)\n")

    # Build a numbered list of articles to send to Claude.
    # We format it as plain text so Claude can easily read it.
    articles_text = ""
    for i, article in enumerate(articles, start=1):
        # enumerate() gives us both the index (i) and the item (article)
        # start=1 means we count from 1 instead of 0
        articles_text += f"""
ARTICLE {i}:
  Title:     {article['title']}
  Source:    {article['source']}
  Published: {article['published']}
  Link:      {article['link']}
  Summary:   {article['summary'] or '(no summary available)'}
---"""

    # This is the instruction we give Claude.
    # A "prompt" is like a detailed request or brief.
    # We're very specific so Claude gives us exactly the output format we need.
    prompt = f"""You are a content strategist for culture-forward media accounts on Instagram, TikTok, and Substack.

I'll give you a list of recent articles. Evaluate EACH article on these 4 criteria:

1. TRENDING: Is this something a lot of people are actively discussing right now? (Not just newsworthy — actively viral or buzzy)
2. TIMELY: Did this happen or break in the last 24–48 hours? Is it fresh?
3. CULTURAL: Does it connect to a broader cultural moment, meme, movement, or viral conversation?
4. CAROUSEL: Could this become a carousel post that feels like something a culture-forward media account (like The Cut, Diet Prada, GQ, Vox, or a savvy creator) would post? Avoid generic listicles, corporate press releases, or niche-only stories. Think: would a smart, culture-aware person share this to their 100k+ followers?

Score each article from 1–10 overall. Be ruthlessly selective. A 7+ means this is genuinely strong. Most articles should score 4–6.

For articles that score 7 or above, also provide:
- WHY: 1–2 sentences explaining why it scored high
- ANGLE: A specific carousel hook or angle that would perform well

IMPORTANT: Return your response as valid JSON in EXACTLY this format, with no other text before or after:

{{
  "evaluations": [
    {{
      "article_number": 1,
      "score": 8,
      "why": "This story is being widely shared and connects to the ongoing conversation about...",
      "angle": "Hook: 'Everyone is talking about X, but here's what they're missing...'"
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

    # Create a Claude client using our API key
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Send the request to Claude
    # We use claude-opus-4-6 — Anthropic's most capable model
    # max_tokens=4096 gives Claude room to write detailed evaluations
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
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

    # Get Claude's text response
    response_text = response.content[0].text.strip()

    # Parse the JSON response
    # Claude was asked to return JSON — now we convert it back into Python objects
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        # If Claude didn't return valid JSON, try to extract it
        # Sometimes Claude adds a tiny bit of extra text despite our instructions
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                print("❌ Claude returned an unexpected format. Please try again.")
                print(f"   Raw response: {response_text[:300]}")
                sys.exit(1)
        else:
            print("❌ Could not parse Claude's response as JSON.")
            sys.exit(1)

    # Merge Claude's evaluations back into our article records
    evaluations = result.get("evaluations", [])

    # Build a lookup dictionary for quick access by article number
    # {1: {...eval data...}, 2: {...eval data...}, ...}
    eval_by_number = {e["article_number"]: e for e in evaluations}

    # Add Claude's scores to each article
    enriched_articles = []
    for i, article in enumerate(articles, start=1):
        eval_data = eval_by_number.get(i, {})
        article["score"] = eval_data.get("score", 0)
        article["why"]   = eval_data.get("why")
        article["angle"] = eval_data.get("angle")
        enriched_articles.append(article)

    print(f"✅ Claude evaluated all {len(enriched_articles)} articles.")
    return enriched_articles


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: SELECT TOP PICKS
# ─────────────────────────────────────────────────────────────────────────────

def select_top_picks(articles: list[dict]) -> list[dict]:
    """
    Filters articles to only those scoring MIN_SCORE (7) or above,
    then returns up to MAX_PICKS (5) of the highest-scoring ones.

    "sorted()" sorts a list. "reverse=True" means highest first.
    "key=lambda a: a['score']" means "sort by the 'score' field".
    A lambda is a mini one-line function — here it means:
    "for each article (a), give me its score".
    """
    # Filter to only high-scoring articles
    strong_picks = [a for a in articles if a["score"] >= MIN_SCORE]

    # Sort by score, highest first
    strong_picks.sort(key=lambda a: a["score"], reverse=True)

    # Take only the top MAX_PICKS
    return strong_picks[:MAX_PICKS]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: WRITE THE MARKDOWN OUTPUT FILE
# ─────────────────────────────────────────────────────────────────────────────

def write_markdown_output(picks: list[dict], all_articles_count: int) -> str:
    """
    Creates a markdown file named picks-YYYY-MM-DD.md with today's top picks.

    Markdown is a simple formatting language. You've probably seen it on GitHub
    or in note-taking apps. # makes a heading, ** makes bold text, etc.

    Returns:
        The filename that was created.
    """
    # Get today's date in YYYY-MM-DD format (e.g., "2026-03-05")
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"picks-{today_str}.md"

    # Build the markdown content as one big string
    # Triple quotes (""") let us write a multi-line string
    content = f"""# Daily Content Picks — {today_str}

> **Source:** Inoreader feeds from the last {HOURS_BACK} hours
> **Articles reviewed:** {all_articles_count}
> **Picks surfaced:** {len(picks)} (minimum score: {MIN_SCORE}/10)

---

"""

    # If no strong picks were found, say so clearly
    if not picks:
        content += f"""## No Strong Picks Today

None of today's {all_articles_count} articles scored {MIN_SCORE} or above.

This is normal — not every day has carousel-worthy content. Check back tomorrow!

*Tip: If you want to lower the bar, change MIN_SCORE in daily_curator.py.*
"""
    else:
        # Add each pick as a section
        for i, pick in enumerate(picks, start=1):
            # Add a section for each pick
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

    # Add a footer
    content += f"""*Generated by Daily Curator on {datetime.now().strftime("%Y-%m-%d at %H:%M")}*
"""

    # Write the content to a file
    # "w" means "write" (create or overwrite)
    # "encoding='utf-8'" ensures special characters work correctly
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — Tie everything together
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """
    The main function — the starting point of the script.

    This is the "conductor" that calls each step in order:
      1. Check setup
      2. Fetch articles from Inoreader
      3. Evaluate with Claude
      4. Select top picks
      5. Write output file
    """

    print("\n" + "=" * 55)
    print("  📰 Daily Curator — Content Scouting with Claude AI")
    print("=" * 55)

    # Step 1: Verify all credentials are present
    check_setup()

    # Step 2: Fetch recent articles from Inoreader
    articles = fetch_articles_from_inoreader()

    # If there are no articles at all, exit early
    if not articles:
        print(f"\n⚠️  No articles found from the last {HOURS_BACK} hours.")
        print("Try increasing HOURS_BACK in the script, or check your Inoreader feeds.")
        sys.exit(0)

    # Step 3: Send articles to Claude for evaluation
    evaluated_articles = evaluate_articles_with_claude(articles)

    # Step 4: Select the best picks
    top_picks = select_top_picks(evaluated_articles)

    # Step 5: Write the output file
    print(f"\n📝 Writing output file...")
    output_file = write_markdown_output(top_picks, len(articles))

    # Print a summary to the terminal
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


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

# This tells Python: "only run main() if this file is being run directly."
# (Not if it's being imported by another file — a best practice in Python.)
if __name__ == "__main__":
    main()
