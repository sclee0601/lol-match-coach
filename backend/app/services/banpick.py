"""
Ban/Pick recommendation engine.
Uses accumulated match data to suggest bans and picks during champ select.
"""

from app.services.riot_api import (
    get_puuid_by_riot_id,
    get_match_ids_by_puuid,
    get_match_summaries_parallel,
    is_summoners_rift_match,
)
from app.services.comp_classifier import classify_comp, get_team_champions_for_player


# ---------------------------------------------------------------------------
# Champion ID <-> Name mapping (loaded from Data Dragon)
# ---------------------------------------------------------------------------

CHAMP_ID_TO_NAME: dict[int, str] = {}
CHAMP_NAME_TO_ID: dict[str, int] = {}


def _load_champion_ids():
    """Load champion ID mapping from Data Dragon."""
    global CHAMP_ID_TO_NAME, CHAMP_NAME_TO_ID
    import httpx
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            if resp.status_code != 200:
                return
            latest = resp.json()[0]
            resp = client.get(f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json")
            if resp.status_code != 200:
                return
            champions = resp.json().get("data", {})
            for name, data in champions.items():
                champ_id = int(data.get("key", 0))
                CHAMP_ID_TO_NAME[champ_id] = name
                CHAMP_NAME_TO_ID[name] = champ_id
        print(f"[banpick] Loaded {len(CHAMP_ID_TO_NAME)} champion IDs")
    except Exception as e:
        print(f"[banpick] Failed to load champion IDs: {e}")


_load_champion_ids()


def champ_name(champ_id: int) -> str:
    """Convert champion ID to name."""
    return CHAMP_ID_TO_NAME.get(champ_id, f"Champion#{champ_id}")


def champ_id(name: str) -> int:
    """Convert champion name to ID."""
    return CHAMP_NAME_TO_ID.get(name, 0)


# ---------------------------------------------------------------------------
# Ban/Pick profile builder
# ---------------------------------------------------------------------------

async def build_banpick_profile(puuid: str) -> dict:
    """
    Build a ban/pick profile from the player's match history.
    Returns:
    - enemy_threats: champions the player loses against most
    - best_picks_by_role: best champions per role
    - synergies: teammates that boost winrate
    """
    # Fetch match history (reuses cache from lookup)
    all_ids: list[str] = []
    start = 0
    while len(all_ids) < 20 and start < 100:
        batch = get_match_ids_by_puuid(puuid, count=100, start=start)
        if not batch:
            break
        all_ids.extend(batch)
        start += len(batch)
    all_ids = all_ids[:20]

    match_data_map = await get_match_summaries_parallel(all_ids, max_concurrent=5)

    # Track stats
    enemy_stats: dict[str, dict] = {}  # enemy champ -> {games, losses}
    my_picks: dict[str, dict] = {}  # my champ -> {games, wins, role}
    ally_stats: dict[str, dict] = {}  # ally champ -> {games, wins}

    for mid in all_ids:
        data = match_data_map.get(mid)
        if not data or not is_summoners_rift_match(data):
            continue

        info = data.get("info", {})
        participants = info.get("participants", [])
        player = next((p for p in participants if p.get("puuid") == puuid), None)
        if not player:
            continue

        my_team_id = player.get("teamId", 0)
        won = player.get("win", False)
        my_champ = player.get("championName", "Unknown")
        my_role = (player.get("individualPosition") or player.get("teamPosition") or "").upper()

        # Track my picks
        if my_champ not in my_picks:
            my_picks[my_champ] = {"games": 0, "wins": 0, "role": my_role}
        my_picks[my_champ]["games"] += 1
        my_picks[my_champ]["wins"] += 1 if won else 0

        for p in participants:
            p_champ = p.get("championName", "Unknown")
            p_team = p.get("teamId", 0)

            if p_team != my_team_id:
                # Enemy
                if p_champ not in enemy_stats:
                    enemy_stats[p_champ] = {"games": 0, "losses": 0}
                enemy_stats[p_champ]["games"] += 1
                if not won:
                    enemy_stats[p_champ]["losses"] += 1
            elif p.get("puuid") != puuid:
                # Ally (not me)
                if p_champ not in ally_stats:
                    ally_stats[p_champ] = {"games": 0, "wins": 0}
                ally_stats[p_champ]["games"] += 1
                ally_stats[p_champ]["wins"] += 1 if won else 0

    # Build enemy threats (champions you lose against most, min 2 games)
    enemy_threats = []
    for champ, stats in enemy_stats.items():
        if stats["games"] >= 2:
            loss_rate = stats["losses"] / stats["games"]
            enemy_threats.append({
                "champion": champ,
                "games": stats["games"],
                "loss_rate": round(loss_rate * 100),
            })
    enemy_threats.sort(key=lambda x: (-x["loss_rate"], -x["games"]))

    # Build best picks (min 2 games)
    best_picks = []
    for champ, stats in my_picks.items():
        if stats["games"] >= 2:
            winrate = stats["wins"] / stats["games"]
            best_picks.append({
                "champion": champ,
                "games": stats["games"],
                "winrate": round(winrate * 100),
                "role": stats["role"],
            })
    best_picks.sort(key=lambda x: (-x["winrate"], -x["games"]))

    # Build ally synergies (min 2 games, high winrate)
    synergies = []
    for champ, stats in ally_stats.items():
        if stats["games"] >= 2:
            winrate = stats["wins"] / stats["games"]
            synergies.append({
                "champion": champ,
                "games": stats["games"],
                "winrate": round(winrate * 100),
            })
    synergies.sort(key=lambda x: (-x["winrate"], -x["games"]))

    return {
        "enemy_threats": enemy_threats[:10],
        "best_picks": best_picks[:10],
        "synergies": synergies[:10],
    }


def get_recommendations(
    profile: dict,
    my_role: str,
    ally_picks: list[str],
    enemy_picks: list[str],
    banned: list[str],
) -> dict:
    """
    Generate ban/pick recommendations based on profile and current draft state.
    """
    banned_lower = {b.lower() for b in banned}
    enemy_lower = {e.lower() for e in enemy_picks}
    ally_lower = {a.lower() for a in ally_picks}

    # Ban suggestions: enemies you lose to that aren't already banned/picked
    ban_suggestions = []
    for threat in profile.get("enemy_threats", []):
        champ = threat["champion"]
        if champ.lower() not in banned_lower and champ.lower() not in enemy_lower:
            ban_suggestions.append(threat)
        if len(ban_suggestions) >= 3:
            break

    # Pick suggestions: your best champs for the assigned role that aren't banned
    pick_suggestions = []
    role_map = {"top": "TOP", "jungle": "JUNGLE", "middle": "MIDDLE", "bottom": "BOTTOM", "utility": "UTILITY"}
    normalized_role = role_map.get(my_role.lower(), my_role.upper())

    for pick in profile.get("best_picks", []):
        champ = pick["champion"]
        if champ.lower() in banned_lower or champ.lower() in ally_lower or champ.lower() in enemy_lower:
            continue
        # Prefer same role, but include all
        if pick["role"] == normalized_role or not normalized_role:
            pick_suggestions.append(pick)
        if len(pick_suggestions) >= 3:
            break

    # If not enough role-specific picks, add any good picks
    if len(pick_suggestions) < 3:
        for pick in profile.get("best_picks", []):
            champ = pick["champion"]
            if champ.lower() in banned_lower or champ.lower() in ally_lower or champ.lower() in enemy_lower:
                continue
            if pick not in pick_suggestions:
                pick_suggestions.append(pick)
            if len(pick_suggestions) >= 3:
                break

    # Synergy info: which allies on your team have good winrate with you
    synergy_matches = []
    for syn in profile.get("synergies", []):
        if syn["champion"].lower() in ally_lower:
            synergy_matches.append(syn)

    return {
        "ban_suggestions": ban_suggestions,
        "pick_suggestions": pick_suggestions,
        "synergy_matches": synergy_matches,
    }
