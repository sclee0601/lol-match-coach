import re
from pathlib import Path
from dotenv import load_dotenv
import os
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------------------------------------------------------------------------
# Role standards loader
# ---------------------------------------------------------------------------

STANDARDS_DIR = Path(__file__).resolve().parent.parent.parent / "standards"
CHALLENGER_BEHAVIOR_PATH = Path(__file__).resolve().parent.parent.parent / "challenger_behavior.md"

ROLE_TO_FILE = {
    "BOTTOM": "adc.md",
    "UTILITY": "support.md",
    "MIDDLE": "mid.md",
    "JUNGLE": "jungle.md",
    "TOP": "top.md",
}


def _load_challenger_behavior() -> str:
    """Load the challenger behavior decision guide."""
    if CHALLENGER_BEHAVIOR_PATH.exists():
        return CHALLENGER_BEHAVIOR_PATH.read_text(encoding="utf-8")
    return ""


def _load_role_standards(role: str) -> str:
    """Load the role-specific standards markdown for the given position."""
    filename = ROLE_TO_FILE.get(role.upper(), "")
    if not filename:
        return ""
    filepath = STANDARDS_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return ""


def _get_relevant_standards(role: str, has_laning_deaths: bool, has_late_deaths: bool, has_objectives: bool) -> str:
    """Load only the relevant sections of role standards based on what happened in the game."""
    full_standards = _load_role_standards(role)
    if not full_standards:
        return ""

    sections = full_standards.split("\n## ")
    relevant = []

    # Sections to skip (LLM can infer these, saves tokens)
    skip_keywords = {"cooldown tracking", "game clock", "power spike"}

    for section in sections:
        lower = section.lower()
        # Skip token-heavy sections the LLM can infer
        if any(kw in lower for kw in skip_keywords):
            continue
        # Always include CS & Gold benchmarks
        if "cs" in lower and "gold" in lower:
            relevant.append("## " + section)
        # Include laning if there were laning deaths
        if has_laning_deaths and ("laning" in lower or "trading" in lower or "wave" in lower):
            relevant.append("## " + section)
        # Include teamfight positioning if there were late game deaths
        if has_late_deaths and ("teamfight" in lower or "positioning" in lower or "late game" in lower):
            relevant.append("## " + section)
        # Include vision if relevant
        if has_objectives and "vision" in lower:
            relevant.append("## " + section)
        # Always include general rules
        if "general" in lower:
            relevant.append("## " + section)
        # Include matchup adjustments
        if "matchup" in lower:
            relevant.append("## " + section)

    return "\n".join(relevant) if relevant else full_standards


def _call_llm(messages: list) -> tuple[str, str]:
    """Call LLM with fallback chain: Groq 70B → Claude → Groq 8B → error."""

    # Primary: Groq 70B (best free option)
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY, timeout=30.0)
        print("=== Calling Groq (llama-3.3-70b-versatile) ===")
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.45,
                max_tokens=6000,
            )
            text = response.choices[0].message.content
            if text:
                print("=== Groq 70B succeeded ===")
                return text, "llama-3.3-70b-versatile"
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e):
                print("=== Groq 70B rate limited ===")
            else:
                print(f"=== Groq 70B failed: {e} ===")

    # Fallback: Claude (if key works)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        print("=== Trying Claude ===")
        try:
            import httpx

            system_msg = ""
            user_msg = ""
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                elif msg["role"] == "user":
                    user_msg = msg["content"]

            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 4000,
                "system": system_msg,
                "messages": [{"role": "user", "content": user_msg}],
            }

            with httpx.Client(timeout=60) as http_client:
                resp = http_client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("content", [{}])[0].get("text", "")
                    if text:
                        print("=== Claude succeeded ===")
                        return text, "claude-3-5-sonnet"
                else:
                    print(f"=== Claude returned {resp.status_code} ===")
        except Exception as e:
            print(f"=== Claude failed: {e} ===")

    # Fallback: Groq 8B
    if GROQ_API_KEY:
        print("=== Trying Groq 8B ===")
        try:
            client = Groq(api_key=GROQ_API_KEY, timeout=30.0)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.45,
                max_tokens=4000,
            )
            text = response.choices[0].message.content
            if text:
                print("=== Groq 8B succeeded ===")
                return text, "llama-3.1-8b-instant (fallback)"
        except Exception as e:
            print(f"=== Groq 8B failed: {e} ===")

    raise RuntimeError("AI analysis is temporarily unavailable due to rate limits. Please try again in a few minutes.")


# ---------------------------------------------------------------------------
# Language config
# ---------------------------------------------------------------------------

LANGUAGE_INSTRUCTIONS = {
    "Korean": (
        "You MUST write everything in Korean (한국어). "
        "Champion names and LoL terms (CS, KDA, Baron, Dragon, HP) stay in English. "
        "Speak like a real Korean coach — short, direct, punchy."
    ),
    "Japanese": "Write in Japanese. Champion names and LoL terms stay in English.",
    "Chinese": "Write in Simplified Chinese. Champion names and LoL terms stay in English.",
    "Spanish": "Write in Spanish. Champion names and LoL terms stay in English.",
    "Portuguese": "Write in Portuguese. Champion names and LoL terms stay in English.",
    "French": "Write in French. Champion names and LoL terms stay in English.",
    "German": "Write in German. Champion names and LoL terms stay in English.",
    "English": "Write in English.",
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(players: list[dict], champion_filter: str | None, timeline_summary: str = "", language: str = "English") -> tuple[str, str]:
    targets = players
    if champion_filter:
        filtered = [p for p in players if p["champion"].lower() == champion_filter.lower()]
        if filtered:
            targets = filtered

    game_length_min = targets[0]["game_length_seconds"] // 60 if targets else 0
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["English"])

    # All 10 players for full game context
    all_player_lines = "\n".join(
        f"- {p['summoner_name']} ({p['champion']}, {p['team']}, {p['position']}): "
        f"{p['kills']}/{p['deaths']}/{p['assists']} KDA, {p['cs']} CS in {game_length_min}min "
        f"({round(p['cs'] / max(game_length_min, 1), 1)} CS/min), "
        f"{p['gold']}g, {p['damage_dealt']} dmg, "
        f"Vision {p['vision_score']}, "
        f"{'WIN' if p['win'] else 'LOSS'}"
        for p in players
    )

    # Get the champion and role
    champ_name = targets[0]["champion"] if targets else "Unknown"
    role = targets[0].get("position", "UNKNOWN").upper() if targets else "UNKNOWN"
    result = "WIN" if targets[0]["win"] else "LOSS"

    # Load role-specific standards based on what happened in the game
    has_laning_deaths = "killed" in timeline_summary.lower() and any(
        int(line.split(":")[0]) < 14 for line in timeline_summary.split("\n")
        if "killed" in line and line[0].isdigit()
    ) if timeline_summary else False
    has_late_deaths = "killed" in timeline_summary.lower() if timeline_summary else False
    has_objectives = "DRAGON" in timeline_summary or "BARON" in timeline_summary or "HERALD" in timeline_summary if timeline_summary else False
    role_standards = _get_relevant_standards(role, has_laning_deaths, has_late_deaths, has_objectives)

    # Identify lane opponent
    opponent_info = ""
    if targets and len(players) == 10:
        target_team = targets[0]["team"]
        target_role = targets[0].get("position", "").upper()
        opponents = [p for p in players if p["team"] != target_team and p.get("position", "").upper() == target_role]
        if opponents:
            opp = opponents[0]
            opponent_info = (
                f"\nLane Opponent: {opp['champion']} — "
                f"{opp['kills']}/{opp['deaths']}/{opp['assists']} KDA, "
                f"{opp['cs']} CS ({round(opp['cs'] / max(game_length_min, 1), 1)} CS/min), "
                f"{opp['gold']}g, {opp['damage_dealt']} dmg"
            )

    timeline_section = f"\n{timeline_summary}" if timeline_summary else ""

    # Role standards section
    standards_section = ""
    if role_standards:
        standards_section = f"\n## Role Standards (APPLY these rules when evaluating each event)\n{role_standards}\n"

    # Challenger behavior decision guide (applies to all roles)
    behavior_guide = _load_challenger_behavior()
    behavior_section = ""
    if behavior_guide:
        behavior_section = f"\n## Decision Framework (USE this to analyze each death/mistake)\n{behavior_guide}\n"

    prompt = f"""## Game Data (All 10 Players)
Length: {game_length_min} min
{all_player_lines}

## Target Player: {champ_name} ({role}) — {result}
{opponent_info}
{timeline_section}
{standards_section}
{behavior_section}
## Coaching Report for {champ_name} ({role}) — {result}

Analyze THIS SPECIFIC GAME using the timeline data above. Every point must reference actual events from the data. Do NOT give generic advice.

### 1. CS & Gold Analysis
For each CS snapshot, write ONE line in this exact format:
- [X]min: [Y]cs — [ahead/behind] benchmark by [Z]cs. [If behind and a death happened before this time, say "Lost CS due to death at [time]". Otherwise say nothing.]

Gold vs opponent: state gold difference at 5min and 10min only.

### 2. Deaths in Laning Phase (before 14 min)
If 0 deaths before 14min: write "Clean laning phase — no deaths." and stop.

For each death, use this EXACT format:
- [time]: Killed by [champion] at [zone]. Assists: [list or none]. HP was [X]%. 
  → [ONE fix: what {champ_name} should do in this matchup to avoid this specific death]

### 3. Mid/Late Game Deaths & Teamfight Analysis
For each death AFTER 14 min:
- Quote the event (timestamp, killer, zone, HP%)
- Look at ALL player positions provided. Who was nearby? Who was out of position?
- State the PRIORITY TARGET: who should the team have focused? (the most dangerous enemy near the fight)
- Was this death caused by: wrong target focus, bad spacing from teammates, or being caught alone?
- One fix: where should {champ_name} have been relative to teammates?

For objectives: check ALL player positions. Was the team grouped? Was anyone split? Did enemy contest?

### 4. Top 3 Strategic Fixes
For teamfight deaths, answer:
- Who should the team have focused? (e.g., "Qiyana was at Mid — frontline should zone her before she reaches ADC")
- Where should {champ_name} have stood relative to teammates? (e.g., "Stay within Morgana's Black Shield range")
- What was the team's win condition and did they play around it?

ONLY reference actual events. If the player played well, say so.
"""
    return lang_instruction, prompt


# ---------------------------------------------------------------------------
# Main analyze function
# ---------------------------------------------------------------------------

def analyze(players: list[dict], champion_filter: str | None = None, timeline_summary: str = "", language: str = "English") -> dict:
    lang_instruction, prompt = build_prompt(players, champion_filter, timeline_summary, language)

    print("=== PROMPT LENGTH ===", len(prompt))
    print("=== TIMELINE INCLUDED ===", bool(timeline_summary))

    # Get champion name for system message
    targets_for_msg = players
    if champion_filter:
        filtered = [p for p in players if p["champion"].lower() == champion_filter.lower()]
        if filtered:
            targets_for_msg = filtered
    champ_name = targets_for_msg[0]["champion"] if targets_for_msg else "Unknown"

    system_msg = (
        f"You are a Challenger-tier LoL coach. {lang_instruction}\n\n"
        f"RULES:\n"
        f"- Only state facts from the data. Never guess.\n"
        f"- Kills are GOOD. Never criticize a kill.\n"
        f"- Each death: WHO, WHERE, assists, ONE fix. Analyze each death ONCE only.\n"
        f"- Section 4 must give NEW macro insights, not repeat earlier deaths.\n"
        f"- 0 deaths in a phase = 'Clean phase.' Move on.\n"
        f"- No vague advice. Every sentence needs a timestamp, zone, or number.\n"
        f"- Max 500 words."
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]

    analysis_text, model_used = _call_llm(messages)
    print(f"=== ANALYSIS GENERATED ({model_used}) ===")

    targets = players
    if champion_filter:
        filtered = [p for p in players if p["champion"].lower() == champion_filter.lower()]
        if filtered:
            targets = filtered

    return {
        "analysis": analysis_text,
        "players_analyzed": [p["champion"] for p in targets],
        "champion_filter": champion_filter,
        "model_used": model_used,
    }
