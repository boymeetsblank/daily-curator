# Daily Curator

A Python script that scouts your Inoreader feeds daily and uses Claude AI to
surface the best content for your Instagram, TikTok, and Substack accounts.

---

## What Does This Do?

Every time you run this script, it:

1. **Connects to your Inoreader account** and pulls articles published in the last 48 hours
2. **Sends those articles to Claude** (the AI from Anthropic) for evaluation on 4 criteria:
   - Is it **trending** — are a lot of people talking about it right now?
   - Is it **timely** — did it happen in the last 24–48 hours?
   - Does it connect to something **cultural** or viral?
   - Could it make a **carousel** that a culture-forward media account would post?
3. **Scores each article 1–10** and surfaces only the top 5 picks (nothing below a 7)
4. **Saves a markdown file** named `picks-YYYY-MM-DD.md` with your picks, explanations, and carousel angles

---

## Setup Guide (Step by Step)

Don't skip steps — each one builds on the previous.

### Step 1: Make Sure Python Is Installed

Python is the programming language this script is written in. Think of it as the
engine that runs the code.

**Check if you have it:**

Open your terminal:
- **Mac:** Press `Cmd + Space`, type `Terminal`, press Enter
- **Windows:** Press the Windows key, type `PowerShell`, press Enter
- **Linux:** Press `Ctrl + Alt + T`

Type this and press Enter:
```
python3 --version
```

You should see something like `Python 3.10.0` or higher. If you see an error,
download Python from https://python.org/downloads/ and install it.

---

### Step 2: Download This Project

If you got here from GitHub, clone the project:
```
git clone https://github.com/YOUR-USERNAME/daily-curator.git
cd daily-curator
```

Or if you already have the folder, just navigate into it:
```
cd daily-curator
```

(Replace `daily-curator` with the actual path to your folder if needed.)

---

### Step 3: Install Dependencies

Dependencies are extra tools this script needs. Run this command:
```
pip install -r requirements.txt
```

This installs:
- `anthropic` — lets the script talk to Claude AI
- `requests` — lets the script make web requests to Inoreader
- `python-dotenv` — lets the script read your API keys from a `.env` file

**If you see "pip: command not found"**, try: `pip3 install -r requirements.txt`

---

### Step 4: Get Your Anthropic (Claude) API Key

1. Go to https://console.anthropic.com
2. Create a free account (or log in)
3. Click **"API Keys"** in the left sidebar
4. Click **"Create Key"** and give it a name (e.g., "Daily Curator")
5. **Copy the key immediately** — you won't see it again!
   It looks like: `sk-ant-api03-...`

---

### Step 5: Get Your Inoreader API Credentials

You need 3 things from Inoreader: an **App ID**, an **App Key**, and an **Access Token**.

#### Getting App ID and App Key:

1. Log in to your Inoreader account at https://www.inoreader.com
2. Go to https://www.inoreader.com/developers
3. Click **"Create New Application"**
4. Fill in:
   - **Name:** Daily Curator (or anything you like)
   - **Description:** Personal content curation tool
   - **OAuth2 Redirect URI:** `https://localhost`
5. After creating, you'll see your **App ID** and **App Key** — copy both

#### Getting Your Access Token:

1. Open this URL in your browser (replace `YOUR_APP_ID` with your actual App ID):
   ```
   https://www.inoreader.com/oauth2/auth?client_id=YOUR_APP_ID&redirect_uri=https://localhost&response_type=code&scope=read
   ```
2. Log in and click **"Allow"** to authorize the app
3. Your browser will redirect to a URL that starts with `https://localhost?code=`
   — copy the code after `code=` (it's a long string of letters and numbers)
4. Now run this in your terminal (replace the 3 placeholders):
   ```
   curl -X POST https://www.inoreader.com/oauth2/token \
     -d "code=PASTE_CODE_HERE&redirect_uri=https://localhost&grant_type=authorization_code" \
     -u "YOUR_APP_ID:YOUR_APP_KEY"
   ```
5. You'll get a JSON response. Copy the value after `"access_token":` — that's your token!

> **⚠️ Token expiry:** Inoreader tokens expire after ~30 days. If the script stops
> working, you'll need to repeat this process to get a fresh token.

---

### Step 6: Create Your `.env` File

This file stores your secret credentials safely.

1. In your `daily-curator` folder, copy the example file:
   ```
   cp .env.example .env
   ```
   On Windows PowerShell:
   ```
   copy .env.example .env
   ```

2. Open `.env` in any text editor (Notepad, TextEdit, VS Code, etc.)

3. Replace the placeholder values with your real credentials:
   ```
   ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
   INOREADER_APP_ID=your-actual-app-id
   INOREADER_APP_KEY=your-actual-app-key
   INOREADER_TOKEN=your-actual-access-token
   ```

4. Save the file.

> **⚠️ Important:** Never share your `.env` file or put it on GitHub.
> It's listed in `.gitignore` so Git will ignore it automatically.

---

### Step 7: Run the Script!

```
python3 daily_curator.py
```

The script will:
1. Check your credentials
2. Fetch articles from Inoreader (may take a moment)
3. Send them to Claude for evaluation (may take 15–30 seconds)
4. Save a file like `picks-2026-03-05.md` in your folder
5. Print a summary in the terminal

---

## Reading Your Output

After running, open the `picks-YYYY-MM-DD.md` file in any text editor or Markdown viewer.

Each pick includes:
- The headline, source, and link
- Why Claude scored it high (1–2 sentences)
- A suggested carousel angle or hook

If nothing scored 7+, the file will say **"No Strong Picks Today"** instead of
forcing weak results.

---

## Customizing the Script

Open `daily_curator.py` in a text editor. Near the top, you'll see these settings:

```python
HOURS_BACK           = 48    # Look back this many hours (try 24 or 72)
MAX_ARTICLES_TO_SEND = 60    # Max articles to evaluate (more = slower + costs more)
MIN_SCORE            = 7     # Minimum score to show (lower = more results)
MAX_PICKS            = 5     # Max number of picks to show
```

Change any of these numbers to adjust the script's behavior. Save the file and run again.

---

## Troubleshooting

**"No articles found"**
→ Your Inoreader feeds may not have published anything in the time window.
  Try increasing `HOURS_BACK` from 48 to 72 or 96.

**"Inoreader authentication failed"**
→ Your `INOREADER_TOKEN` has likely expired. Follow Step 5 again to get a new token.

**"Invalid API key" from Claude**
→ Check that `ANTHROPIC_API_KEY` in your `.env` file is correct (no extra spaces).

**"No module named 'anthropic'"**
→ Dependencies aren't installed. Run: `pip install -r requirements.txt`

---

## Files in This Project

| File | What It Is |
|------|-----------|
| `daily_curator.py` | The main script — all the logic lives here |
| `requirements.txt` | List of Python packages to install |
| `.env.example` | Template for your API keys (copy this to `.env`) |
| `.env` | Your actual secrets — **never share this!** |
| `.gitignore` | Tells Git which files to ignore (protects your `.env`) |
| `picks-YYYY-MM-DD.md` | Output file — created each time you run the script |

---

## What Is a Terminal?

A terminal (also called a command line, console, or shell) is a text-based way
to give instructions to your computer — instead of clicking icons, you type commands.

- **Mac:** Press `Cmd + Space`, type `Terminal`, press Enter
- **Windows:** Press the Windows key, type `PowerShell`, press Enter
- **Linux:** Press `Ctrl + Alt + T`

Don't worry if it feels unfamiliar — you only need a few commands for this project,
and they're all written out for you above.
