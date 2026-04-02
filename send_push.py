"""
send_push.py — Briefing Push Notification Sender

Called by the GitHub Actions daily_curator.yml workflow after each run.
Detects which scheduled run this is from the current UTC hour, picks the
appropriate message, and sends a Web Push notification to all subscribers.

Expired or unsubscribed endpoints (HTTP 404/410) are pruned from
subscriptions.json automatically.

Required environment variables (set as GitHub Actions secrets):
    VAPID_PRIVATE_KEY — base64url-encoded raw EC P-256 private key
    VAPID_PUBLIC_KEY  — base64url-encoded uncompressed EC P-256 public key
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS      = {"sub": "mailto:mjaffry1@gmail.com"}
FEED_URL          = "https://boymeetsblank.github.io/daily-curator/"

SUBSCRIPTIONS_FILE = "subscriptions.json"

# Map UTC hour → (title, body) matching each scheduled cron run
# Cron: 14:30 UTC = 8:30 AM CT | 19:30 UTC = 1:30 PM CT | 01:30 UTC = 7:30 PM CT
RUN_MESSAGES = {
    14: ("Blank", "Your morning briefing is ready. See what's worth your time today."),
    19: ("Blank", "Your afternoon picks are in. Take a break and catch up."),
    1:  ("Blank", "Your evening briefing is ready. End the day informed."),
}


def has_picks_today() -> bool:
    """Return True if today's latest picks file contains at least one pick."""
    today = datetime.now().strftime("%Y-%m-%d")
    files = sorted(glob.glob(f"picks/picks-{today}-*.md"))
    if not files:
        return False
    with open(files[-1], encoding="utf-8") as f:
        return "## Pick #" in f.read()


def load_subscriptions() -> list[dict]:
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        return []
    try:
        with open(SUBSCRIPTIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_subscriptions(subs: list[dict]) -> None:
    with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    print("\n🔔 Push notification sender starting...")

    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        print("   ⚠️  VAPID_PRIVATE_KEY or VAPID_PUBLIC_KEY not set — skipping push.")
        sys.exit(0)

    if not has_picks_today():
        print("   ℹ️  No picks found for today — skipping push.")
        sys.exit(0)

    subscriptions = load_subscriptions()
    if not subscriptions:
        print("   ℹ️  No subscribers in subscriptions.json — skipping push.")
        sys.exit(0)

    utc_hour = datetime.now(timezone.utc).hour
    title, body = RUN_MESSAGES.get(utc_hour, ("Blank", "New picks are available."))
    print(f"   📨 Sending: \"{body}\" to {len(subscriptions)} subscriber(s)...")

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        print("   ❌ pywebpush not installed. Run: pip install pywebpush")
        sys.exit(1)

    payload = json.dumps({
        "title": title,
        "body":  body,
        "tag":   "daily-briefing",
        "url":   FEED_URL,
    })

    expired = []
    sent = 0

    for i, sub in enumerate(subscriptions):
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
            )
            sent += 1
            print(f"   ✅ Subscriber {i + 1} notified.")
        except WebPushException as e:
            status = e.response.status_code if e.response else None
            if status in (404, 410):
                expired.append(i)
                print(f"   ↩️  Subscriber {i + 1} expired (HTTP {status}) — will prune.")
            else:
                print(f"   ⚠️  Subscriber {i + 1} failed: {e}")
        except Exception as e:
            print(f"   ⚠️  Subscriber {i + 1} error: {e}")

    if expired:
        for idx in reversed(expired):
            subscriptions.pop(idx)
        save_subscriptions(subscriptions)
        print(f"   🗑️  Pruned {len(expired)} expired subscription(s).")

    print(f"\n   ✅ Done — {sent} notification(s) sent, {len(expired)} pruned.\n")


if __name__ == "__main__":
    main()
