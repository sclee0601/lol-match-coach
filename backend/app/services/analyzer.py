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

ROLE_TO_FILE = {
    "BOTTOM": "adc.md",
    "UTILITY": "support.md",
    "MIDDLE": "mid.md",
    "JUNGLE": "jungle.md",
    "TOP": "top.md",
}


def _load_role_standards(role: str) -> str:
    """Load the role-specific standards markdown for the given position."""
    filename = ROLE_TO_FILE.get(role.upper(), "")
    if not filename:
        return ""
    filepath = STANDARDS_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return ""


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

    # Load role-specific standards
    role_standards = _load_role_standards(role)

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

    # Role standards section (only include if we have them)
    standards_section = ""
    if role_standards:
        standards_section = f"\n## Role Standards (use these benchmarks to evaluate the player)\n{role_standards}\n"

    prompt = f"""## Game Data (All 10 Players)
Length: {game_length_min} min
{all_player_lines}

## Target Player: {champ_name} ({role}) — {result}
{opponent_info}
{timeline_section}
{standards_section}
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

### 3. Mid/Late Game Deaths & Objectives
For each death after 14min, same format as above.

For objectives: state if player was near or far. One line each.

### 4. Top 3 Fixes
ONLY reference events that actually happened. Format:
- "At [time], [what happened]. Fix: [one specific action for {champ_name}]."

If the player played well (few deaths, good CS, won), say so. Do NOT invent problems.
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
        f"You are a Challenger-tier League of Legends coach. "
        f"{lang_instruction}\n\n"
        f"ABSOLUTE RULES (violating any = bad response):\n"
        f"1. ONLY state facts from the data provided. NEVER guess, assume, or infer what happened.\n"
        f"2. If the player got kills, that is GOOD. Say 'Good kill on [champ] at [time]' — never criticize a kill.\n"
        f"3. If the player died, state WHO killed them, WHERE, and whether assists suggest a gank.\n"
        f"4. NEVER say 'enemy's mistake' or 'not a well-executed trade' — you cannot know this from data.\n"
        f"5. NEVER say 'focus on CSing instead of fighting' after a kill — kills are worth more than 1-2 CS.\n"
        f"6. For CS analysis: just state the numbers vs benchmark. If behind, check if a death happened before that timestamp (death = missed CS). If no death, say 'likely missed CS during trades or roam'.\n"
        f"7. BANNED phrases (never use): 'be more cautious', 'be more aggressive', 'enemy's mistake', "
        f"'not a well-executed trade', 'focus on CSing', 'caught off guard', 'unable to react'.\n"
        f"8. For each death: state timestamp, killer, zone, assists. Then ONE actionable fix specific to {champ_name}.\n"
        f"9. If the player had 0 deaths in a phase, say 'Clean phase — no deaths' and move on. Do NOT invent problems.\n"
        f"10. Keep it SHORT. Max 600 words total."
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
