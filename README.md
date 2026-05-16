# LoL Match Coach

Challenger-style League of Legends coaching from **recent Riot match data** (Summoner's Rift). Enter your **Riot ID (Name#TAG)**, pick a match and champion, and get an AI coaching report grounded in role standards and timeline data.

## Features

- **Match Analysis** — AI-generated coaching reports with CS benchmarks, death analysis, and game-specific fixes
- **Top Champions** — Your best-performing champions by winrate, KDA, and CS
- **Comp Analysis** — Which team comp styles you win most with, broken down by role
- **Live Champ Select** — Real-time ban/pick recommendations during champion selection (requires League client running locally)
- **Multi-language** — English, Korean, Japanese, Chinese, Spanish, Portuguese, French, German

## Tech Stack

- **Backend:** Python, FastAPI, Groq (LLama 3.3 70B)
- **Frontend:** Angular 21, TypeScript, SCSS
- **APIs:** Riot Games Match-v5, Account-v1, LCU (local client)

## Setup

### Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env     # Add your API keys
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
ng serve
```

Open `http://localhost:4200`

### Environment Variables

| Key | Description |
|-----|-------------|
| `RIOT_API_KEY` | Riot Games API key ([developer.riotgames.com](https://developer.riotgames.com)) |
| `GROQ_API_KEY` | Groq API key ([console.groq.com](https://console.groq.com)) |

### Live Champ Select (optional)

Requires League of Legends client running on the same PC. The app reads the local LCU API to detect champion select and provide real-time recommendations.

## Usage

1. Search your Riot ID (e.g. `Faker#KR1`)
2. View your stats (top champions, best comp styles)
3. Select a match → pick your champion → get AI coaching
4. Queue for a game → Live Draft panel appears during champ select

## License

Personal project. Not affiliated with or endorsed by Riot Games.
