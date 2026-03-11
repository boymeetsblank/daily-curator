# Daily Curator

A Python script that scouts your Inoreader feeds daily and uses Claude AI to
surface the best content for your Instagram, TikTok, and Substack accounts.

---

## What Does This Do?

Every time you run this script, it:

1. **Connects to your Inoreader account** and pulls articles published in the last 48 hours
2. **Caps articles per source** to 5 maximum — so no single outlet dominates the results
3. **Sends those articles to Claude** (the AI from Anthropic) for evaluation on 4 criteria:
   - Is it **trending** — are a lot of people talking about it right now?
   - Is it **timely** — did it happen in the last 24–48 hours?
   - Does it connect to something **cultural** or viral?
   - Could it make a **carousel** that a culture-forward media account would post?
4. **Scores each article 1–10** and surfaces only the top 5 picks (nothing below a 7)
5. **Saves a markdown file** named `picks/picks-YYYY-MM-DD-HHMM.md` with your picks, explanations, and carousel angles

> **⚠️ Politics-free by design:** This tool intentionally avoids political content.
> Articles about elections, political figures, legislation, or partisan issues will
> not be surfaced as picks regardless of how much traction they get.

The script runs automatically 3x per day via GitHub Actions:
- 8:30 AM CT
- 3:30 PM CT
- 8:30 PM CT

Each run creates a new timestamped file so no picks are overwritten.

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
git clone https://github.com/boymeetsblank/daily-curator.git
cd daily-curator
```

Or if you already have the folder, just navigate into it:
```
cd daily-curator
```

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

You need 4 things from Inoreader: an **App ID**, an **App Key**, an **Access Token**, and a **Refresh Token**.

#### Getting App ID and App Key:

1. Log in to your Inoreader account at https://www.inoreader.com
2. Go to https://www.inoreader.com/developers
3. Click **"Create New Application"**
4. Fill in:
   - **Name:** Daily Curator (or anything you like)
   - **Description:** Personal content curation tool
   - **OAuth2 Redirect URI:** `https://localhost`
5. After creating, you'll see your **App ID** and **App Key** — copy both

#### Getting Your Access Token and Refresh Token:

1. Open this URL in your browser (replace `YOUR_APP_ID` with your actual App ID):
```
   https://www.inoreader.com/oauth2/auth?client_id=YOUR_APP_ID&redirect_uri=https://localhost&response_type=code&scope=read&state=xyz
```
2. Log in and click **"Allow"** to authorize the app
3. Your browser will redirect to a URL that starts with `https://localhost?code=`
   — copy the code after `code=`
4. In PowerShell, run this (replace the placeholders):
```
   Invoke-RestMethod -Method Post -Uri "https://www.inoreader.com/oauth2/token" -Body "code=PASTE_CODE_HERE&redirect_uri=https://localhost&grant_type=authorization_code" -Headers @{Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("YOUR_APP_ID:YOUR_APP_KEY"))}
```
5. Copy both the `access_token` and `refresh_token` from the response.

> **⚠️ Token expiry:** The access token expires every 24 hours but the script
> auto-refreshes it using the refresh token. The refresh token itself lasts ~30 days.
> When it expires, repeat this process.

---

### Step 6: Create Your `.env` File

1. In your `daily-curator` folder, run:
```
   copy .env.example .env
```

2. Open `.env` in Notepad and fill in your credentials:
```
   ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
   INOREADER_APP_ID=your-actual-app-id
   INOREADER_APP_KEY=your-actual-app-key
   INOREADER_TOKEN=your-actual-access-token
   INOREADER_REFRESH_TOKEN=your-actual-refresh-token
```

3. Save the file.

> **⚠️ Important:** Never share your `.env` file or put it on GitHub.
> It's listed in `.gitignore` so Git will ignore it automatically.

---

### Step 7: Add Secrets to GitHub Actions

For the automated runs to work, add all 5 credentials as GitHub Secrets:

1. Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"** for each:
   - `ANTHROPIC_API_KEY`
   - `INOREADER_APP_ID`
   - `INOREADER_APP_KEY`
   - `INOREADER_TOKEN`
   - `INOREADER_REFRESH_TOKEN`

Also make sure Actions has write permissions:
- **Settings** → **Actions** → **General** → **Workflow permissions** → select **Read and write permissions**

---

### Step 8: Run the Script!
```
python3 daily_curator.py
```

Or trigger a manual run anytime via GitHub Actions → **Daily Curator** → **Run workflow**.

---

## Reading Your Output

Picks are saved to the `picks/` folder as `picks-YYYY-MM-DD-HHMM.md`.

Each pick includes:
- The headline, source, and link
- Why Claude scored it high (1–2 sentences)
- A suggested carousel angle or hook

If nothing scored 7+, the file will say **"No Strong Picks Today"**.

---

## Customizing the Script

Open `daily_curator.py` in a text editor. Near the top, you'll see these settings:
```python
HOURS_BACK              = 48   # Look back this many hours
MAX_ARTICLES_TO_SEND    = 60   # Max articles to fetch from Inoreader
MAX_ARTICLES_PER_SOURCE = 5    # Max articles allowed per source (prevents one outlet dominating)
MIN_SCORE               = 7    # Minimum score to surface a pick
MAX_PICKS               = 5    # Max number of picks per run
```

---

## Troubleshooting

**"No articles found"**
→ Try increasing `HOURS_BACK` to 72 or 96.

**"Inoreader authentication failed"**
→ Your refresh token has expired (~30 days). Follow Step 5 to get new tokens.

**"Invalid API key" from Claude**
→ Check `ANTHROPIC_API_KEY` in your `.env` file.

**"No module named 'anthropic'"**
→ Run: `pip install -r requirements.txt`

**GitHub Actions push rejected**
→ Run `git pull --rebase` then `git push`

---

## Files in This Project

| File | What It Is |
|------|-----------|
| `daily_curator.py` | The main script |
| `requirements.txt` | Python packages to install |
| `.env.example` | Template for your API keys |
| `.env` | Your actual secrets — **never share this!** |
| `.gitignore` | Protects your `.env` from being uploaded |
| `picks/picks-YYYY-MM-DD-HHMM.md` | Output files — one per run |
| `.github/workflows/daily_curator.yml` | GitHub Actions automation |