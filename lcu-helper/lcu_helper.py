"""
LoL Match Coach — Live Champ Select Helper
A standalone local app that connects to your League client during champ select
and shows ban/pick recommendations based on your match history.

Usage: Double-click to run, or: python lcu_helper.py
"""

import asyncio
import base64
import os
import sys
import json
import time
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LEAGUE_PATH = r"C:\Riot Games\League of Legends"
LOCKFILE_PATH = os.path.join(LEAGUE_PATH, "lockfile")

# Cloud API URL (change this to your deployed URL)
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "http://localhost:8000/api")

# Your Riot ID (set via env var or hardcode for personal use)
SUMMONER = os.getenv("SUMMONER", "")

POLL_INTERVAL = 2  # seconds


# ---------------------------------------------------------------------------
# LCU Connection
# ---------------------------------------------------------------------------

def read_lockfile() -> dict | None:
    """Read the League client lockfile."""
    if not os.path.exists(LOCKFILE_PATH):
        return None
    try:
        with open(LOCKFILE_PATH, "r") as f:
            content = f.read().strip()
        parts = content.split(":")
        if len(parts) < 5:
            return None
        return {
            "port": int(parts[2]),
            "password": parts[3],
        }
    except Exception:
        return None


def get_auth_header(password: str) -> str:
    token = base64.b64encode(f"riot:{password}".encode()).decode()
    return f"Basic {token}"


async def get_champ_select_session(port: int, auth: str) -> dict | None:
    """Get current champ select session from LCU."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=5) as client:
            resp = await client.get(
                f"https://127.0.0.1:{port}/lol-champ-select/v1/session",
                headers={"Authorization": auth},
            )
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


async def get_gameflow_phase(port: int, auth: str) -> str | None:
    """Get current gameflow phase."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=5) as client:
            resp = await client.get(
                f"https://127.0.0.1:{port}/lol-gameflow/v1/gameflow-phase",
                headers={"Authorization": auth},
            )
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Champion ID mapping (loaded from Data Dragon)
# ---------------------------------------------------------------------------

CHAMP_ID_TO_NAME: dict[int, str] = {}


def load_champion_ids():
    global CHAMP_ID_TO_NAME
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            latest = resp.json()[0]
            resp = client.get(f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json")
            champions = resp.json().get("data", {})
            for name, data in champions.items():
                CHAMP_ID_TO_NAME[int(data["key"])] = name
        print(f"  Loaded {len(CHAMP_ID_TO_NAME)} champions")
    except Exception as e:
        print(f"  Warning: Could not load champion data: {e}")


def champ_name(cid: int) -> str:
    return CHAMP_ID_TO_NAME.get(cid, f"#{cid}")


# ---------------------------------------------------------------------------
# Profile (fetched from cloud API or cached locally)
# ---------------------------------------------------------------------------

PROFILE_CACHE_FILE = os.path.join(os.path.dirname(__file__), "profile_cache.json")


def load_cached_profile() -> dict | None:
    if os.path.exists(PROFILE_CACHE_FILE):
        try:
            with open(PROFILE_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_profile_cache(profile: dict):
    try:
        with open(PROFILE_CACHE_FILE, "w") as f:
            json.dump(profile, f, indent=2)
    except Exception:
        pass


async def fetch_profile(summoner: str) -> dict | None:
    """Fetch ban/pick profile from the cloud API."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{CLOUD_API_URL}/banpick-profile",
                params={"summoner": summoner},
            )
            if resp.status_code == 200:
                profile = resp.json()
                save_profile_cache(profile)
                return profile
            else:
                print(f"  Could not fetch profile: {resp.status_code}")
                return None
    except Exception as e:
        print(f"  Could not reach cloud API: {e}")
        return None


# ---------------------------------------------------------------------------
# Recommendation engine (local version)
# ---------------------------------------------------------------------------

def get_recommendations(profile: dict, my_role: str, ally_picks: list, enemy_picks: list, banned: list) -> dict:
    banned_lower = {b.lower() for b in banned}
    enemy_lower = {e.lower() for e in enemy_picks}
    ally_lower = {a.lower() for a in ally_picks}

    # Ban suggestions
    ban_suggestions = []
    for threat in profile.get("enemy_threats", []):
        champ = threat["champion"]
        if champ.lower() not in banned_lower and champ.lower() not in enemy_lower:
            ban_suggestions.append(threat)
        if len(ban_suggestions) >= 3:
            break

    # Pick suggestions
    pick_suggestions = []
    role_map = {"top": "TOP", "jungle": "JUNGLE", "middle": "MIDDLE", "bottom": "BOTTOM", "utility": "UTILITY"}
    normalized_role = role_map.get(my_role.lower(), my_role.upper())

    for pick in profile.get("best_picks", []):
        champ = pick["champion"]
        if champ.lower() in banned_lower or champ.lower() in ally_lower or champ.lower() in enemy_lower:
            continue
        if pick.get("role") == normalized_role or not normalized_role:
            pick_suggestions.append(pick)
        if len(pick_suggestions) >= 3:
            break

    if len(pick_suggestions) < 3:
        for pick in profile.get("best_picks", []):
            champ = pick["champion"]
            if champ.lower() in banned_lower or champ.lower() in ally_lower or champ.lower() in enemy_lower:
                continue
            if pick not in pick_suggestions:
                pick_suggestions.append(pick)
            if len(pick_suggestions) >= 3:
                break

    # Synergy
    synergy_matches = []
    for syn in profile.get("synergies", []):
        if syn["champion"].lower() in ally_lower:
            synergy_matches.append(syn)

    return {
        "ban_suggestions": ban_suggestions,
        "pick_suggestions": pick_suggestions,
        "synergy_matches": synergy_matches,
    }


# ---------------------------------------------------------------------------
# Parse champ select session
# ---------------------------------------------------------------------------

def parse_session(session: dict) -> dict:
    local_cell = session.get("localPlayerCellId", -1)

    my_role = ""
    my_champ = 0
    ally_picks = []
    enemy_picks = []
    bans = []

    # Bans from actions
    for action_group in session.get("actions", []):
        for action in action_group:
            if action.get("type") == "ban" and action.get("completed") and action.get("championId", 0) > 0:
                bans.append(champ_name(action["championId"]))

    # My team
    for p in session.get("myTeam", []):
        cid = p.get("championId", 0) or p.get("championPickIntent", 0)
        if p.get("cellId") == local_cell:
            my_role = p.get("assignedPosition", "")
            my_champ = cid
        elif cid > 0:
            ally_picks.append(champ_name(cid))

    # Their team
    for p in session.get("theirTeam", []):
        cid = p.get("championId", 0)
        if cid > 0:
            enemy_picks.append(champ_name(cid))

    return {
        "my_role": my_role,
        "my_champ": champ_name(my_champ) if my_champ > 0 else "",
        "ally_picks": ally_picks,
        "enemy_picks": enemy_picks,
        "bans": bans,
    }


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def display_recommendations(draft: dict, recs: dict):
    clear_screen()
    print("=" * 60)
    print("  ⚡ LoL Match Coach — Live Draft Assistant")
    print("=" * 60)
    print()
    print(f"  Role: {draft['my_role'].upper() or 'Unknown'}")
    if draft["my_champ"]:
        print(f"  Your pick: {draft['my_champ']}")
    print()

    if draft["bans"]:
        print(f"  Bans: {', '.join(draft['bans'])}")
    if draft["ally_picks"]:
        print(f"  Allies: {', '.join(draft['ally_picks'])}")
    if draft["enemy_picks"]:
        print(f"  Enemies: {', '.join(draft['enemy_picks'])}")
    print()

    print("-" * 60)

    if recs["ban_suggestions"]:
        print("  🚫 BAN THESE:")
        for b in recs["ban_suggestions"]:
            print(f"     {b['champion']} — you lose {b['loss_rate']}% against them")
        print()

    if recs["pick_suggestions"]:
        print("  ✅ PICK THESE:")
        for p in recs["pick_suggestions"]:
            print(f"     {p['champion']} — {p['winrate']}% WR ({p['games']} games)")
        print()

    if recs["synergy_matches"]:
        print("  🤝 SYNERGY WITH ALLIES:")
        for s in recs["synergy_matches"]:
            print(f"     {s['champion']} — {s['winrate']}% WR together")
        print()

    print("-" * 60)
    print("  Updating every 2 seconds... Press Ctrl+C to exit.")


def display_waiting(phase: str | None):
    clear_screen()
    print("=" * 60)
    print("  ⚡ LoL Match Coach — Live Draft Assistant")
    print("=" * 60)
    print()
    if phase:
        print(f"  Status: {phase}")
    else:
        print("  Waiting for League client...")
    print()
    print("  The assistant will activate when you enter champ select.")
    print("  Press Ctrl+C to exit.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def main():
    print("=" * 60)
    print("  ⚡ LoL Match Coach — Live Draft Assistant")
    print("=" * 60)
    print()

    # Get summoner name
    summoner = SUMMONER
    if not summoner:
        summoner = input("  Enter your Riot ID (Name#TAG): ").strip()
        if not summoner or "#" not in summoner:
            print("  Invalid Riot ID. Use format: Name#TAG")
            input("  Press Enter to exit...")
            return

    print(f"\n  Summoner: {summoner}")
    print("  Loading champion data...")
    load_champion_ids()

    # Load or fetch profile
    print("  Loading your ban/pick profile...")
    profile = load_cached_profile()
    if not profile:
        profile = await fetch_profile(summoner)
    if not profile:
        print("  Could not load profile. Make sure you've searched in the web app first.")
        print("  Or check that the cloud API is running.")
        input("  Press Enter to exit...")
        return

    print(f"  Profile loaded! ({len(profile.get('enemy_threats', []))} threats, {len(profile.get('best_picks', []))} picks)")
    print("\n  Waiting for League client and champ select...")
    time.sleep(2)

    # Main polling loop
    last_phase = None
    try:
        while True:
            lockfile = read_lockfile()
            if not lockfile:
                if last_phase != "disconnected":
                    display_waiting(None)
                    last_phase = "disconnected"
                await asyncio.sleep(POLL_INTERVAL)
                continue

            port = lockfile["port"]
            auth = get_auth_header(lockfile["password"])

            phase = await get_gameflow_phase(port, auth)

            if phase == "ChampSelect":
                session = await get_champ_select_session(port, auth)
                if session:
                    draft = parse_session(session)
                    recs = get_recommendations(
                        profile,
                        draft["my_role"],
                        draft["ally_picks"],
                        draft["enemy_picks"],
                        draft["bans"],
                    )
                    display_recommendations(draft, recs)
                    last_phase = "ChampSelect"
            else:
                if last_phase != phase:
                    display_waiting(phase)
                    last_phase = phase

            await asyncio.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n  Goodbye! Good luck in your games.")


if __name__ == "__main__":
    # Suppress SSL warnings for LCU self-signed cert
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    asyncio.run(main())
