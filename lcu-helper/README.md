# LoL Match Coach — Live Draft Helper

A standalone local app that connects to your League client during champ select and shows ban/pick recommendations.

## How to Use

### Option 1: Run directly (requires Python)
```bash
pip install -r requirements.txt
python lcu_helper.py
```

### Option 2: Build as .exe (no Python needed to run)
```bash
build.bat
```
Then share `dist/LoL-Match-Coach-Helper.exe` — just double-click to run.

## Setup

1. Make sure you've searched your Riot ID in the web app at least once (this builds your profile)
2. Run this helper
3. Enter your Riot ID when prompted (or set `SUMMONER` env var)
4. Queue for a game — recommendations appear automatically in champ select

## Environment Variables (optional)

| Variable | Description |
|----------|-------------|
| `SUMMONER` | Your Riot ID (e.g., `Faker#KR1`) — skips the prompt |
| `CLOUD_API_URL` | URL of the deployed backend API (default: `http://localhost:8000/api`) |

## What it Shows

During champ select:
- 🚫 **Ban suggestions** — enemies you historically lose against
- ✅ **Pick suggestions** — your best champions for your assigned role
- 🤝 **Synergy** — allies on your team that you win with often
