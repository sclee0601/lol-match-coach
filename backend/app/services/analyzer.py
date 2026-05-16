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


def _call_llm(messages: list) -> str:
    """Call Groq llama-3.3-70b with fallback to llama-3.1-8b-instant on rate limit."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set in .env")
    client = Groq(api_key=GROQ_API_KEY)

    models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]

    for model in models:
        print(f"=== Calling Groq ({model}) ===")
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.45,
                max_tokens=6000,
            )
            text = response.choices[0].message.content
            if not text:
                raise RuntimeError("Groq returned an empty response")
            print(f"=== Groq succeeded ({model}) ===")
            return text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str:
                print(f"=== {model} rate limited, trying fallback ===")
                continue
            print(f"=== Groq failed: {type(e).__name__}: {e} ===")
            raise RuntimeError(f"Groq API error: {e}") from e

    raise RuntimeError("All Groq models rate limited. Please try again later.")


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
Using the CS snapshots from the timeline, compare to the {role} benchmark:
- State the ACTUAL CS numbers at each snapshot (3/5/8/10/14 min) and whether they are ahead or behind benchmark.
- If behind: explain WHY using kill/death events that happened before that timestamp.
- Gold comparison vs lane opponent at key moments.

### 2. Deaths in Laning Phase (before 14 min)
For each death that occurred before 14 min in the timeline:
- Quote the exact event line (timestamp, killer, zone)
- Was it a gank (multiple enemies in assists)? A lost 1v1 trade? A bad all-in?
- What should {champ_name} have done differently in that specific matchup vs {opponents[0]['champion'] if opponents else 'unknown'}?

If there are NO deaths before 14 min, say so and move on.

### 3. Mid/Late Game Deaths & Objectives
For each death AFTER 14 min:
- Quote the exact event line (timestamp, killer, zone, HP%)
- Categorize: POSITIONING ERROR, PEEL FAILURE, or COOLDOWN MISTAKE
- One specific fix

For objectives: check the player's zone during each objective event. Were they present or far away?

### 4. Top 3 Game-Specific Fixes
Based ONLY on what happened in this game:
- Fix 1: "At [timestamp], you [what happened from timeline]. Instead, [specific action for {champ_name}] because [reason]."
- Fix 2: same format
- Fix 3: same format

Keep each fix to 1-2 sentences. No generic advice.
"""
    return lang_instruction, prompt


# ---------------------------------------------------------------------------
# Main analyze function
# ---------------------------------------------------------------------------

def analyze(players: list[dict], champion_filter: str | None = None, timeline_summary: str = "", language: str = "English") -> dict:
    lang_instruction, prompt = build_prompt(players, champion_filter, timeline_summary, language)

    print("=== PROMPT LENGTH ===", len(prompt))
    print("=== TIMELINE INCLUDED ===", bool(timeline_summary))

    system_msg = (
        f"You are a Challenger-tier League of Legends coach giving a post-game review. "
        f"{lang_instruction}\n\n"
        f"STRICT RULES:\n"
        f"- You are analyzing ONE SPECIFIC GAME. Every sentence must reference data from the game "
        f"(timestamps, zones, CS numbers, kill events, gold values). If you cannot cite specific "
        f"game data for a point, do not include it.\n"
        f"- NEVER use vague phrases: 'be more cautious', 'be more aggressive', 'be more aware', "
        f"'could have been avoided by positioning better', 'being more careful', 'play safer', "
        f"'be more cautious and aware of the enemy'. These are USELESS.\n"
        f"- INSTEAD: reference the EXACT event from the timeline — 'At 8min you died to [champion] "
        f"at [zone] because [specific reason from data]'.\n"
        f"- Compare the player's actual CS/gold numbers against the role benchmarks provided.\n"
        f"- For each death in the timeline: state the timestamp, killer, zone, and player's HP%. "
        f"Then categorize and give ONE specific fix.\n"
        f"- Every bullet must contain a timestamp OR a specific number from the game data OR a "
        f"zone/position from the timeline. If a bullet has none of these, delete it.\n"
        f"- Tailor advice to the SPECIFIC champion and matchup. A Caitlyn fix is different from "
        f"an Ezreal fix even if both are ADC.\n"
        f"- Keep the whole report under 900 words."
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]

    analysis_text = _call_llm(messages)
    print("=== ANALYSIS GENERATED ===")

    targets = players
    if champion_filter:
        filtered = [p for p in players if p["champion"].lower() == champion_filter.lower()]
        if filtered:
            targets = filtered

    return {
        "analysis": analysis_text,
        "players_analyzed": [p["champion"] for p in targets],
        "champion_filter": champion_filter,
    }
