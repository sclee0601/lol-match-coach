import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
BASE_URL = "https://americas.api.riotgames.com"

# Riot match-v5 `mapId`: 11 = Summoner's Rift (excludes ARAM / Howling Abyss map 12, etc.)
MAP_SUMMONERS_RIFT = 11

# ---------------------------------------------------------------------------
# In-memory match cache (avoids re-fetching the same match)
# ---------------------------------------------------------------------------

_match_cache: dict[str, dict] = {}
_CACHE_MAX_SIZE = 200


def _cache_match(match_id: str, data: dict):
    """Store match data in cache, evicting oldest if full."""
    global _match_cache
    if len(_match_cache) >= _CACHE_MAX_SIZE:
        # Remove oldest 50 entries
        keys = list(_match_cache.keys())[:50]
        for k in keys:
            del _match_cache[k]
    _match_cache[match_id] = data


def get_cached_match(match_id: str) -> dict | None:
    """Get match data from cache if available."""
    return _match_cache.get(match_id)

# ---------------------------------------------------------------------------
# Item name lookup (loaded from Data Dragon at startup)
# ---------------------------------------------------------------------------

ITEM_NAMES: dict[int, str] = {}
# Items that are consumables/components not worth mentioning in analysis
MINOR_ITEM_IDS: set[int] = set()


def _load_item_data():
    """Fetch item.json from Data Dragon to map item IDs to names."""
    global ITEM_NAMES, MINOR_ITEM_IDS
    try:
        with httpx.Client(timeout=5) as client:
            # Get latest version
            resp = client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            if resp.status_code != 200:
                print("[riot_api] Failed to fetch DDragon versions")
                return
            versions = resp.json()
            latest = versions[0] if versions else "15.10.1"

            # Get item data
            resp = client.get(f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/item.json")
            if resp.status_code != 200:
                print("[riot_api] Failed to fetch item.json")
                return
            items = resp.json().get("data", {})
            for item_id_str, item_data in items.items():
                item_id = int(item_id_str)
                name = item_data.get("name", "")
                gold = item_data.get("gold", {})
                total_cost = gold.get("total", 0)
                ITEM_NAMES[item_id] = name
                # Mark items under 400g as minor (potions, wards, basic components)
                if total_cost < 400:
                    MINOR_ITEM_IDS.add(item_id)
        print(f"[riot_api] Loaded {len(ITEM_NAMES)} items from DDragon {latest}")
    except Exception as e:
        print(f"[riot_api] Failed to load item data (non-fatal): {e}")


# Load item data on module import
_load_item_data()


def _headers() -> dict:
    return {"X-Riot-Token": RIOT_API_KEY}


# ---------------------------------------------------------------------------
# Summoner lookup helpers
# ---------------------------------------------------------------------------

def get_puuid_by_riot_id(game_name: str, tag_line: str) -> str | None:
    """Resolve a Riot ID (gameName#tagLine) to a PUUID via the Account API."""
    if not RIOT_API_KEY:
        return None
    url = f"{BASE_URL}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=_headers())
            if resp.status_code != 200:
                return None
            return resp.json().get("puuid")
    except Exception:
        return None


def get_match_ids_by_puuid(puuid: str, count: int = 10, start: int = 0) -> list[str]:
    """Fetch match IDs for a PUUID (all queues). Use `start` to page through history."""
    if not RIOT_API_KEY:
        return []
    url = f"{BASE_URL}/lol/match/v5/matches/by-puuid/{puuid}/ids"
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                url,
                headers=_headers(),
                params={"count": min(count, 100), "start": start},
            )
            if resp.status_code == 200:
                return resp.json() or []
            return []
    except Exception:
        return []


def is_summoners_rift_match(match_data: dict) -> bool:
    """True if the game was on Summoner's Rift (excludes ARAM and other maps)."""
    info = match_data.get("info") or {}
    return info.get("mapId") == MAP_SUMMONERS_RIFT


def get_match_summary(match_id: str) -> dict | None:
    """
    Fetch full match data from GET /lol/match/v5/matches/{matchId}.
    Uses in-memory cache to avoid duplicate requests.
    Retries once on rate limit (429).
    """
    # Check cache first
    cached = get_cached_match(match_id)
    if cached:
        return cached

    if not RIOT_API_KEY:
        return None
    url = f"{BASE_URL}/lol/match/v5/matches/{match_id}"
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=_headers())
            if resp.status_code == 429:
                import time
                retry_after = int(resp.headers.get("Retry-After", "2"))
                time.sleep(retry_after)
                resp = client.get(url, headers=_headers())
            if resp.status_code != 200:
                return None
            data = resp.json()
            _cache_match(match_id, data)
            return data
    except Exception:
        return None


async def get_match_summary_async(match_id: str, client: httpx.AsyncClient) -> tuple[str, dict | None]:
    """Async version of get_match_summary for parallel fetching. Returns (match_id, data)."""
    # Check cache first
    cached = get_cached_match(match_id)
    if cached:
        return match_id, cached

    if not RIOT_API_KEY:
        return match_id, None
    url = f"{BASE_URL}/lol/match/v5/matches/{match_id}"
    try:
        resp = await client.get(url, headers=_headers())
        if resp.status_code == 429:
            # Rate limited — wait and retry once
            retry_after = min(int(resp.headers.get("Retry-After", "2")), 5)
            await asyncio.sleep(retry_after)
            resp = await client.get(url, headers=_headers())
        if resp.status_code != 200:
            return match_id, None
        data = resp.json()
        _cache_match(match_id, data)
        return match_id, data
    except Exception:
        return match_id, None


async def get_match_summaries_parallel(match_ids: list[str], max_concurrent: int = 5) -> dict[str, dict | None]:
    """Fetch multiple match summaries in parallel with concurrency limit.
    
    Uses max 5 concurrent requests to stay within Riot API rate limits.
    Total operation times out after 30 seconds.
    """
    results: dict[str, dict | None] = {}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_limit(mid: str, client: httpx.AsyncClient):
        async with semaphore:
            await asyncio.sleep(0.15)
            return await get_match_summary_async(mid, client)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            tasks = [fetch_with_limit(mid, client) for mid in match_ids]
            # Total timeout of 30s for all fetches
            done = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30
            )
            for item in done:
                if isinstance(item, tuple) and len(item) == 2:
                    mid, data = item
                    results[mid] = data
    except asyncio.TimeoutError:
        print(f"[riot_api] Parallel fetch timed out after 30s, got {len(results)}/{len(match_ids)} matches")
    except Exception as e:
        print(f"[riot_api] Parallel fetch error: {e}")

    return results


def extract_players_from_match(match_data: dict) -> list[dict]:
    """
    Convert a Riot match API response into the player dict format used by the analyzer.

    IMPORTANT: participants are sorted by participantId (1-10) so the list
    index matches the timeline's 1-based participantId exactly.
    """
    info = match_data.get("info", {})
    game_length_seconds = info.get("gameDuration", 0)
    # Sort by participantId so index 0 = participantId 1, index 1 = participantId 2, etc.
    participants = sorted(
        info.get("participants", []),
        key=lambda p: p.get("participantId", 0)
    )

    result = []
    for p in participants:
        result.append({
            "summoner_name": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
            "champion": p.get("championName", "Unknown"),
            "team": "Blue" if p.get("teamId") == 100 else "Red",
            "position": p.get("individualPosition") or p.get("teamPosition") or "UNKNOWN",
            "kills": p.get("kills", 0),
            "deaths": p.get("deaths", 0),
            "assists": p.get("assists", 0),
            "cs": p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
            "gold": p.get("goldEarned", 0),
            "damage_dealt": p.get("totalDamageDealtToChampions", 0),
            "vision_score": p.get("visionScore", 0),
            "wards_placed": p.get("wardsPlaced", 0),
            "wards_killed": p.get("wardsKilled", 0),
            "game_length_seconds": game_length_seconds,
            "win": p.get("win", False),
            "puuid": p.get("puuid", ""),
        })
    return result


# ---------------------------------------------------------------------------
# Timeline helpers
# ---------------------------------------------------------------------------

def _zone(x: int, y: int) -> str:
    """Map Riot API coordinates to a human-readable zone.
    
    Summoner's Rift coordinate system:
    - Origin (0, 0) = bottom-left corner (Blue fountain area)
    - Max (~14870, ~14870) = top-right corner (Red fountain area)
    - Top lane runs along the LEFT and TOP edges (low X or high Y)
    - Bot lane runs along the BOTTOM and RIGHT edges (low Y or high X)
    - Mid lane is the diagonal from bottom-left to top-right
    """
    # Bases
    if x < 2000 and y < 2000:
        return "Blue Fountain"
    if x > 13000 and y > 13000:
        return "Red Fountain"
    
    # Mid lane (diagonal corridor ~2000 units wide)
    # The diagonal goes from roughly (2000,2000) to (13000,13000)
    if abs(x - y) < 2200 and 2000 < x < 13000:
        if x < 5500:
            return "Mid Lane (inner Blue)"
        elif x > 9500:
            return "Mid Lane (inner Red)"
        else:
            return "Mid Lane (center)"
    
    # Top lane (left edge going up, then top edge going right)
    if x < 3000 and y > 4000:
        return "Top Lane (Blue side)"
    if y > 12000 and x < 10000:
        return "Top Lane (near Red tower)"
    if x < 5000 and y > 9000:
        return "Top Lane (Red side)"
    
    # Bot lane (bottom edge going right, then right edge going up)
    if y < 3000 and x > 4000:
        return "Bot Lane (Blue side)"
    if x > 12000 and y < 10000:
        return "Bot Lane (near Red tower)"
    if x > 9000 and y < 5000:
        return "Bot Lane (Red side)"
    
    # Dragon pit area
    if 8500 < x < 11000 and 3000 < y < 5500:
        return "Dragon Pit area"
    
    # Baron pit area
    if 3500 < x < 6000 and 9500 < y < 12000:
        return "Baron Pit area"
    
    # River
    if abs(x - y) < 3000 and 4000 < x < 11000:
        if y < 7500:
            return "River (bot side)"
        else:
            return "River (top side)"
    
    # Jungle quadrants
    if x < 7500 and y > 7500:
        return "Blue Jungle (topside)"
    if x < 7500 and y < 7500:
        return "Blue Jungle (botside)"
    if x > 7500 and y < 7500:
        return "Red Jungle (botside)"
    if x > 7500 and y > 7500:
        return "Red Jungle (topside)"
    
    return "Unknown area"


def _dist_to_objective(x: int, y: int, obj: str) -> str:
    """Rough distance label to Dragon or Baron pit."""
    obj_lower = obj.lower()
    if "dragon" in obj_lower or "DRAGON" in obj:
        ox, oy = 9800, 4400
    elif "baron" in obj_lower or "BARON" in obj:
        ox, oy = 5000, 10400
    else:
        return ""
    dist = ((x - ox) ** 2 + (y - oy) ** 2) ** 0.5
    if dist < 2000:  return "near objective"
    if dist < 5000:  return "mid-range from objective"
    return "far from objective"


def get_match_timeline(match_id: str) -> dict | None:
    """
    Fetch detailed timeline from GET /lol/match/v5/matches/{matchId}/timeline.
    Returns per-minute frames with every player's position, HP, gold, CS,
    plus every in-game event (kills, objectives, wards, buildings).
    Retries once on rate limit (429).
    """
    if not RIOT_API_KEY:
        return None
    url = f"{BASE_URL}/lol/match/v5/matches/{match_id}/timeline"
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(url, headers=_headers())
            if resp.status_code == 429:
                import time
                retry_after = int(resp.headers.get("Retry-After", "2"))
                time.sleep(retry_after)
                resp = client.get(url, headers=_headers())
            if resp.status_code != 200:
                return None
            return resp.json()
    except Exception:
        return None


def extract_timeline_summary(timeline: dict, champion_filter: str | None, players: list[dict]) -> str:
    """Compact timeline: kills, deaths, objectives, items, wards, and laning CS for the target player."""
    if not timeline:
        return ""

    frames = timeline.get("info", {}).get("frames", [])
    if not frames:
        return ""

    # Build participant ID maps
    timeline_participants = timeline.get("info", {}).get("participants", [])
    if timeline_participants:
        puuid_to_player = {p.get("puuid", ""): p for p in players if p.get("puuid")}
        pid_to_champ: dict[int, str] = {}
        pid_to_team:  dict[int, str] = {}
        for tp in timeline_participants:
            pid = tp.get("participantId", 0)
            player = puuid_to_player.get(tp.get("puuid", ""))
            if player:
                pid_to_champ[pid] = player["champion"]
                pid_to_team[pid]  = player["team"]
        for i, p in enumerate(players):
            pid = i + 1
            if pid not in pid_to_champ:
                pid_to_champ[pid] = p["champion"]
                pid_to_team[pid]  = p["team"]
    else:
        pid_to_champ = {i + 1: p["champion"] for i, p in enumerate(players)}
        pid_to_team  = {i + 1: p["team"]     for i, p in enumerate(players)}

    if champion_filter:
        target_pids = {pid for pid, c in pid_to_champ.items() if c.lower() == champion_filter.lower()}
    else:
        target_pids = set(pid_to_champ.keys())

    # Collect snapshots and events
    all_snapshots: dict[int, dict[int, dict]] = {}
    target_cs: list[tuple] = []  # (min, cs, gold, level)
    kill_events: list[str] = []
    objective_events: list[str] = []
    item_events: list[str] = []
    ward_events: list[str] = []

    # Key item names (Riot item IDs for major components)
    # We'll just track the event and let the LLM interpret

    for frame in frames:
        t_min = frame.get("timestamp", 0) // 60000

        frame_state: dict[int, dict] = {}
        for pid_str, pf in frame.get("participantFrames", {}).items():
            pid = int(pid_str)
            pos = pf.get("position", {})
            stats = pf.get("championStats", {})
            hp_max = stats.get("healthMax", 1) or 1
            x, y = pos.get("x", 0), pos.get("y", 0)
            frame_state[pid] = {
                "zone": _zone(x, y),
                "hp_pct": round(stats.get("health", 0) / hp_max * 100),
                "cs": pf.get("minionsKilled", 0) + pf.get("jungleMinionsKilled", 0),
                "total_gold": pf.get("totalGold", 0),
                "level": pf.get("level", 1),
                "x": x,
                "y": y,
            }
        all_snapshots[t_min] = frame_state

        # CS snapshots at key laning minutes
        if t_min in (3, 5, 8, 10, 14):
            for tpid in target_pids:
                if tpid in frame_state:
                    s = frame_state[tpid]
                    target_cs.append((t_min, s["cs"], s["total_gold"], s["level"]))

        # Events
        for event in frame.get("events", []):
            etype = event.get("type")
            t_sec = event.get("timestamp", 0)
            t_min_e = t_sec // 60000
            t_sec_display = f"{t_min_e}:{(t_sec % 60000) // 1000:02d}"
            killer_id = event.get("killerId", 0)
            victim_id = event.get("victimId", 0)
            pos = event.get("position", {})
            zone = _zone(pos.get("x", 0), pos.get("y", 0)) if pos else ""

            if etype == "CHAMPION_KILL":
                if killer_id in target_pids or victim_id in target_pids:
                    k = pid_to_champ.get(killer_id, "?")
                    v = pid_to_champ.get(victim_id, "?")
                    # Assisters
                    assists = event.get("assistingParticipantIds", [])
                    assist_champs = [pid_to_champ.get(a, "?") for a in assists]
                    assist_str = f" (assists: {', '.join(assist_champs)})" if assist_champs else ""
                    # Target player's state at that moment
                    target_state = ""
                    for tpid in target_pids:
                        ts = all_snapshots.get(t_min_e, {}).get(tpid)
                        if ts:
                            target_state = f" [player at {ts['zone']}, {ts['hp_pct']}%HP, lvl{ts['level']}]"
                    # Victim state
                    victim_state = ""
                    vs = all_snapshots.get(t_min_e, {}).get(victim_id)
                    if vs:
                        victim_state = f" [victim was at {vs['hp_pct']}%HP, lvl{vs['level']}]"
                    kill_events.append(
                        f"{t_sec_display}: {k} killed {v} at {zone}{assist_str}{target_state}{victim_state}"
                    )

            elif etype == "ELITE_MONSTER_KILL":
                monster = event.get("monsterSubType") or event.get("monsterType", "")
                # Where was the target player?
                target_pos = ""
                for tpid in target_pids:
                    ts = all_snapshots.get(t_min_e, {}).get(tpid)
                    if ts:
                        dist = _dist_to_objective(ts.get("x", 0), ts.get("y", 0), monster)
                        target_pos = f" [player at {ts['zone']}, {dist}]"
                allied = killer_id in target_pids or any(
                    pid_to_team.get(killer_id) == pid_to_team.get(t) for t in target_pids
                )
                who = "Allied" if allied else "Enemy"
                objective_events.append(f"{t_sec_display}: {who} took {monster}{target_pos}")

            elif etype == "ITEM_PURCHASED":
                pid = event.get("participantId", 0)
                if pid in target_pids:
                    item_id = event.get("itemId", 0)
                    # Skip minor items (potions, wards, cheap components)
                    if item_id > 0 and item_id not in MINOR_ITEM_IDS:
                        item_name = ITEM_NAMES.get(item_id, f"item#{item_id}")
                        item_events.append(f"{t_sec_display}: bought {item_name}")

            elif etype == "WARD_PLACED":
                pid = event.get("creatorId", 0)
                if pid in target_pids:
                    ward_type = event.get("wardType", "UNKNOWN")
                    ward_events.append(f"{t_sec_display}: placed {ward_type}")

            elif etype == "WARD_KILL":
                pid = event.get("killerId", 0)
                if pid in target_pids:
                    ward_type = event.get("wardType", "UNKNOWN")
                    ward_events.append(f"{t_sec_display}: destroyed {ward_type}")

    # Build compact summary
    lines = []

    if target_cs:
        lines.append("## Laning CS Snapshots")
        lines.append(" | ".join(f"{m}min: {cs}cs, {g}g, lvl{l}" for m, cs, g, l in target_cs))

    if kill_events:
        lines.append("\n## Kill/Death Events (chronological)")
        lines.extend(f"  {e}" for e in kill_events[:20])

    if objective_events:
        lines.append("\n## Objective Events")
        lines.extend(f"  {e}" for e in objective_events[:15])

    if item_events:
        # Only show first few major purchases (skip early consumables)
        lines.append("\n## Item Purchases (first 10)")
        lines.extend(f"  {e}" for e in item_events[:10])

    if ward_events:
        lines.append(f"\n## Vision (total wards placed/killed: {len(ward_events)})")
        # Just show count and a few examples
        lines.extend(f"  {e}" for e in ward_events[:5])

    return "\n".join(lines)