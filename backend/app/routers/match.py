from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import asyncio
from app.services.analyzer import analyze, _call_llm, LANGUAGE_INSTRUCTIONS
from app.services.riot_api import (
    get_match_timeline,
    extract_timeline_summary,
    get_puuid_by_riot_id,
    get_match_ids_by_puuid,
    get_match_summary,
    get_match_summaries_parallel,
    extract_players_from_match,
    is_summoners_rift_match,
)
from app.services.comp_classifier import classify_comp, get_team_champions_for_player
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api", tags=["match"])


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=5000)


class ChatRequest(BaseModel):
    analysis: str = Field(max_length=50000)
    history: list[ChatMessage] = Field(max_length=20)
    question: str = Field(max_length=2000)
    language: str = "English"


class AnalyzeMatchRequest(BaseModel):
    match_id: str = Field(max_length=50, pattern="^[A-Z0-9_]+$")
    champion: str | None = Field(default=None, max_length=30)
    language: str = "English"


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@router.post("/chat")
@limiter.limit("10/minute")
async def chat(req: ChatRequest, request: Request):
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(req.language, LANGUAGE_INSTRUCTIONS["English"])
    system_msg = (
        f"You are a Challenger-tier League of Legends coach. "
        f"The player is asking follow-up questions about their match analysis below. "
        f"Answer directly and specifically, referencing the analysis data when relevant. "
        f"{lang_instruction} "
        f"Be conversational but brutally honest. Keep answers concise."
        f"\n\n## Match Analysis Context\n{req.analysis}"
    )
    messages = [{"role": "system", "content": system_msg}]
    for msg in req.history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.question})

    reply = _call_llm(messages)
    return {"reply": reply}


# ---------------------------------------------------------------------------
# Summoner lookup -> match list
# ---------------------------------------------------------------------------

@router.get("/lookup")
async def lookup_summoner(summoner: str):
    """
    Resolve a Riot ID (gameName#tagLine) to a list of recent matches.
    Fetches match data in parallel for speed.
    """
    if "#" not in summoner:
        raise HTTPException(
            status_code=400,
            detail="Enter your Riot ID as  Name#TAG  (e.g. Faker#KR1)"
        )

    game_name, tag_line = summoner.split("#", 1)
    game_name = game_name.strip()
    tag_line  = tag_line.strip()

    puuid = get_puuid_by_riot_id(game_name, tag_line)
    if not puuid:
        raise HTTPException(
            status_code=404,
            detail=f"Summoner '{game_name}#{tag_line}' not found. Check the name and tag."
        )

    target = 20
    batch = 40
    max_history_offset = 200
    matches: list[dict] = []
    start = 0

    while len(matches) < target and start < max_history_offset:
        match_ids = get_match_ids_by_puuid(puuid, count=batch, start=start)
        if not match_ids:
            break

        # Fetch all matches in this batch in parallel
        match_data_map = await get_match_summaries_parallel(match_ids, max_concurrent=5)

        for mid in match_ids:
            data = match_data_map.get(mid)
            if not data or not is_summoners_rift_match(data):
                continue

            info = data.get("info", {})
            participants = info.get("participants", [])

            player_entry = next(
                (p for p in participants if p.get("puuid") == puuid),
                None,
            )

            blue = [p["championName"] for p in participants if p.get("teamId") == 100]
            red = [p["championName"] for p in participants if p.get("teamId") != 100]

            matches.append({
                "match_id": mid,
                "game_duration": info.get("gameDuration", 0),
                "queue_id": info.get("queueId", 0),
                "game_creation": info.get("gameCreation", 0),
                "blue_team": blue,
                "red_team": red,
                "my_champion": player_entry.get("championName", "") if player_entry else "",
                "my_team": "Blue" if (player_entry or {}).get("teamId") == 100 else "Red",
                "my_win": (player_entry or {}).get("win", False),
                "my_kda": {
                    "kills": (player_entry or {}).get("kills", 0),
                    "deaths": (player_entry or {}).get("deaths", 0),
                    "assists": (player_entry or {}).get("assists", 0),
                },
            })
            if len(matches) >= target:
                break

        start += len(match_ids)

    if not matches:
        raise HTTPException(
            status_code=404,
            detail="No recent Summoner's Rift matches found for this account.",
        )

    return {"puuid": puuid, "matches": matches}


# ---------------------------------------------------------------------------
# Analyze a match by ID (Riot API)
# ---------------------------------------------------------------------------

@router.post("/analyze-match")
@limiter.limit("5/minute")
async def analyze_match(req: AnalyzeMatchRequest, request: Request):
    """
    Full analysis using only the Riot API:
      1. GET /lol/match/v5/matches/{matchId}          -> player stats
      2. GET /lol/match/v5/matches/{matchId}/timeline -> per-minute frames + events
      3. Run LLM coaching report
    """
    match_data = await asyncio.to_thread(get_match_summary, req.match_id)
    if not match_data:
        raise HTTPException(
            status_code=404,
            detail=f"Match {req.match_id} not found or Riot API unavailable."
        )

    players = extract_players_from_match(match_data)
    if not players:
        raise HTTPException(status_code=422, detail="No player data in match.")

    # Timeline is the core of the coaching - every second of the game
    timeline = await asyncio.to_thread(get_match_timeline, req.match_id)
    timeline_summary = (
        extract_timeline_summary(timeline, req.champion, players)
        if timeline else ""
    )

    try:
        result = analyze(
            players,
            champion_filter=req.champion or None,
            timeline_summary=timeline_summary,
            language=req.language,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again.")

    result["players"]      = players
    result["has_timeline"] = bool(timeline)
    return result



# ---------------------------------------------------------------------------
# Top champions for a player
# ---------------------------------------------------------------------------

@router.get("/top-champions")
async def top_champions(summoner: str):
    """
    Fetch last 50 Summoner's Rift matches in parallel, aggregate per-champion stats,
    return top 3 champions by performance score.
    """
    if "#" not in summoner:
        raise HTTPException(status_code=400, detail="Enter Riot ID as Name#TAG")

    game_name, tag_line = summoner.split("#", 1)
    puuid = get_puuid_by_riot_id(game_name.strip(), tag_line.strip())
    if not puuid:
        raise HTTPException(status_code=404, detail="Summoner not found.")

    # Fetch up to 50 match IDs
    all_ids: list[str] = []
    start = 0
    while len(all_ids) < 50 and start < 200:
        batch = get_match_ids_by_puuid(puuid, count=100, start=start)
        if not batch:
            break
        all_ids.extend(batch)
        start += len(batch)
    all_ids = all_ids[:50]

    # Fetch all match data in parallel (5 concurrent to respect rate limits)
    match_data_map = await get_match_summaries_parallel(all_ids, max_concurrent=5)

    # Aggregate stats per champion
    champ_stats: dict[str, dict] = {}

    for mid in all_ids:
        data = match_data_map.get(mid)
        if not data or not is_summoners_rift_match(data):
            continue
        info = data.get("info", {})
        participants = info.get("participants", [])
        player = next((p for p in participants if p.get("puuid") == puuid), None)
        if not player:
            continue

        champ = player.get("championName", "Unknown")
        if champ not in champ_stats:
            champ_stats[champ] = {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0, "cs": 0, "dmg": 0, "duration": 0}

        s = champ_stats[champ]
        s["games"] += 1
        s["wins"] += 1 if player.get("win") else 0
        s["kills"] += player.get("kills", 0)
        s["deaths"] += player.get("deaths", 0)
        s["assists"] += player.get("assists", 0)
        s["cs"] += player.get("totalMinionsKilled", 0) + player.get("neutralMinionsKilled", 0)
        s["dmg"] += player.get("totalDamageDealtToChampions", 0)
        s["duration"] += info.get("gameDuration", 0)

    # Score each champion
    results = []
    for champ, s in champ_stats.items():
        if s["games"] < 2:
            continue  # need at least 2 games
        g = s["games"]
        mins = (s["duration"] / 60) or 1
        avg_kda = (s["kills"] + s["assists"]) / max(s["deaths"], 1)
        winrate = s["wins"] / g
        cs_per_min = s["cs"] / mins
        dmg_per_min = s["dmg"] / mins

        # Score: winrate (40%) + KDA (30%) + CS (15%) + damage (15%)
        score = (
            winrate * 4.0 +
            min(avg_kda / 5, 1) * 3.0 +
            min(cs_per_min / 8, 1) * 1.5 +
            min(dmg_per_min / 700, 1) * 1.5
        )
        results.append({
            "champion": champ,
            "games": g,
            "winrate": round(winrate * 100),
            "avg_kda": round(avg_kda, 2),
            "cs_per_min": round(cs_per_min, 1),
            "score": round(score, 1),
        })

    results.sort(key=lambda x: -x["score"])
    return {"top_champions": results[:3], "total_matches_analyzed": len(all_ids)}


# ---------------------------------------------------------------------------
# Comp analysis — which team comp style does the player win most with?
# ---------------------------------------------------------------------------

@router.get("/comp-analysis")
async def comp_analysis(summoner: str):
    """
    Analyze last 50 Summoner's Rift matches to determine:
    1. Which team comp style the player wins most with
    2. Which ADC performs best in each comp style
    Fetches matches in parallel for speed.
    """
    if "#" not in summoner:
        raise HTTPException(status_code=400, detail="Enter Riot ID as Name#TAG")

    game_name, tag_line = summoner.split("#", 1)
    puuid = get_puuid_by_riot_id(game_name.strip(), tag_line.strip())
    if not puuid:
        raise HTTPException(status_code=404, detail="Summoner not found.")

    # Fetch up to 50 match IDs
    all_ids: list[str] = []
    start = 0
    while len(all_ids) < 50 and start < 200:
        batch = get_match_ids_by_puuid(puuid, count=100, start=start)
        if not batch:
            break
        all_ids.extend(batch)
        start += len(batch)
    all_ids = all_ids[:50]

    # Fetch all match data in parallel
    match_data_map = await get_match_summaries_parallel(all_ids, max_concurrent=5)

    # Aggregate by comp type
    # comp_type -> {games, wins, adcs: {champ -> {games, wins, kills, deaths, assists, cs, dmg, duration}}}
    comp_stats: dict[str, dict] = {}

    for mid in all_ids:
        data = match_data_map.get(mid)
        if not data or not is_summoners_rift_match(data):
            continue

        info = data.get("info", {})
        participants = info.get("participants", [])
        player = next((p for p in participants if p.get("puuid") == puuid), None)
        if not player:
            continue

        # Get team champions and classify comp
        team_champs = get_team_champions_for_player(participants, puuid)
        if not team_champs:
            continue

        comp_type = classify_comp(team_champs)
        player_champ = player.get("championName", "Unknown")
        player_position = (player.get("individualPosition") or player.get("teamPosition") or "").upper()
        is_adc = player_position == "BOTTOM"
        won = player.get("win", False)
        duration = info.get("gameDuration", 0)

        # Init comp stats
        if comp_type not in comp_stats:
            comp_stats[comp_type] = {"games": 0, "wins": 0, "adcs": {}}

        cs = comp_stats[comp_type]
        cs["games"] += 1
        cs["wins"] += 1 if won else 0

        # Track ADC performance within this comp type
        if is_adc:
            if player_champ not in cs["adcs"]:
                cs["adcs"][player_champ] = {
                    "games": 0, "wins": 0,
                    "kills": 0, "deaths": 0, "assists": 0,
                    "cs": 0, "dmg": 0, "duration": 0,
                }
            adc = cs["adcs"][player_champ]
            adc["games"] += 1
            adc["wins"] += 1 if won else 0
            adc["kills"] += player.get("kills", 0)
            adc["deaths"] += player.get("deaths", 0)
            adc["assists"] += player.get("assists", 0)
            adc["cs"] += player.get("totalMinionsKilled", 0) + player.get("neutralMinionsKilled", 0)
            adc["dmg"] += player.get("totalDamageDealtToChampions", 0)
            adc["duration"] += duration

    # Build response
    comp_results = []
    for comp_type, cs in comp_stats.items():
        if cs["games"] < 1:
            continue

        # Best ADC in this comp
        best_adcs = []
        for champ, adc in cs["adcs"].items():
            g = adc["games"]
            mins = (adc["duration"] / 60) or 1
            avg_kda = (adc["kills"] + adc["assists"]) / max(adc["deaths"], 1)
            best_adcs.append({
                "champion": champ,
                "games": g,
                "winrate": round((adc["wins"] / g) * 100),
                "avg_kda": round(avg_kda, 2),
                "cs_per_min": round(adc["cs"] / mins, 1),
                "dmg_per_min": round(adc["dmg"] / mins),
            })

        # Sort ADCs by winrate then KDA
        best_adcs.sort(key=lambda x: (-x["winrate"], -x["avg_kda"]))

        comp_results.append({
            "comp_type": comp_type,
            "games": cs["games"],
            "wins": cs["wins"],
            "winrate": round((cs["wins"] / cs["games"]) * 100),
            "best_adcs": best_adcs[:3],
        })

    # Sort by winrate (min 2 games for reliability), then by games played
    comp_results.sort(key=lambda x: (-x["winrate"] if x["games"] >= 2 else -50, -x["games"]))

    return {
        "comp_analysis": comp_results,
        "total_matches_analyzed": len(all_ids),
    }


# ---------------------------------------------------------------------------
# Combined player stats — top champions + comp analysis in one request
# ---------------------------------------------------------------------------

@router.get("/player-stats")
async def player_stats(summoner: str):
    """
    Single endpoint that returns both top champions and comp analysis.
    Fetches 30 matches in parallel (one pass), avoiding duplicate API calls.
    """
    if "#" not in summoner:
        raise HTTPException(status_code=400, detail="Enter Riot ID as Name#TAG")

    game_name, tag_line = summoner.split("#", 1)
    puuid = get_puuid_by_riot_id(game_name.strip(), tag_line.strip())
    if not puuid:
        raise HTTPException(status_code=404, detail="Summoner not found.")

    # Fetch up to 30 match IDs (enough for stats, faster than 50)
    all_ids: list[str] = []
    start = 0
    while len(all_ids) < 30 and start < 100:
        batch = get_match_ids_by_puuid(puuid, count=100, start=start)
        if not batch:
            break
        all_ids.extend(batch)
        start += len(batch)
    all_ids = all_ids[:30]

    # Fetch all match data in parallel (single pass)
    match_data_map = await get_match_summaries_parallel(all_ids, max_concurrent=5)

    # --- Aggregate both stats in one loop ---
    champ_stats: dict[str, dict] = {}
    comp_stats: dict[str, dict] = {}
    role_counts: dict[str, int] = {}  # Track which role the player plays most

    for mid in all_ids:
        data = match_data_map.get(mid)
        if not data or not is_summoners_rift_match(data):
            continue

        info = data.get("info", {})
        participants = info.get("participants", [])
        player = next((p for p in participants if p.get("puuid") == puuid), None)
        if not player:
            continue

        champ = player.get("championName", "Unknown")
        won = player.get("win", False)
        duration = info.get("gameDuration", 0)
        player_position = (player.get("individualPosition") or player.get("teamPosition") or "").upper()

        # Track role frequency
        if player_position and player_position != "UNKNOWN":
            role_counts[player_position] = role_counts.get(player_position, 0) + 1

        # --- Top champions aggregation ---
        if champ not in champ_stats:
            champ_stats[champ] = {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0, "cs": 0, "dmg": 0, "duration": 0}

        cs = champ_stats[champ]
        cs["games"] += 1
        cs["wins"] += 1 if won else 0
        cs["kills"] += player.get("kills", 0)
        cs["deaths"] += player.get("deaths", 0)
        cs["assists"] += player.get("assists", 0)
        cs["cs"] += player.get("totalMinionsKilled", 0) + player.get("neutralMinionsKilled", 0)
        cs["dmg"] += player.get("totalDamageDealtToChampions", 0)
        cs["duration"] += duration

        # --- Comp analysis aggregation (track player's champion in their role) ---
        team_champs = get_team_champions_for_player(participants, puuid)
        if team_champs:
            comp_type = classify_comp(team_champs)

            if comp_type not in comp_stats:
                comp_stats[comp_type] = {"games": 0, "wins": 0, "picks": {}, "role_picks": {}}

            cst = comp_stats[comp_type]
            cst["games"] += 1
            cst["wins"] += 1 if won else 0

            # Track all teammates' champions by role in this comp
            team_id = player.get("teamId", 0)
            for p in participants:
                if p.get("teamId") != team_id:
                    continue
                p_role = (p.get("individualPosition") or p.get("teamPosition") or "").upper()
                p_champ = p.get("championName", "Unknown")
                p_won = p.get("win", False)
                if p_role and p_role != "UNKNOWN":
                    if p_role not in cst["role_picks"]:
                        cst["role_picks"][p_role] = {}
                    if p_champ not in cst["role_picks"][p_role]:
                        cst["role_picks"][p_role][p_champ] = {"games": 0, "wins": 0}
                    cst["role_picks"][p_role][p_champ]["games"] += 1
                    cst["role_picks"][p_role][p_champ]["wins"] += 1 if p_won else 0

            # Track this player's champion performance in this comp
            if champ not in cst["picks"]:
                cst["picks"][champ] = {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0, "cs": 0, "dmg": 0, "duration": 0}
            pick = cst["picks"][champ]
            pick["games"] += 1
            pick["wins"] += 1 if won else 0
            pick["kills"] += player.get("kills", 0)
            pick["deaths"] += player.get("deaths", 0)
            pick["assists"] += player.get("assists", 0)
            pick["cs"] += player.get("totalMinionsKilled", 0) + player.get("neutralMinionsKilled", 0)
            pick["dmg"] += player.get("totalDamageDealtToChampions", 0)
            pick["duration"] += duration

    # Determine primary role
    primary_role = max(role_counts, key=role_counts.get) if role_counts else "BOTTOM"
    role_label_map = {"BOTTOM": "ADC", "UTILITY": "Support", "MIDDLE": "Mid", "JUNGLE": "Jungle", "TOP": "Top"}
    role_label = role_label_map.get(primary_role, "Champion")

    # --- Build top champions response ---
    top_champ_results = []
    for champ, s in champ_stats.items():
        if s["games"] < 2:
            continue
        g = s["games"]
        mins = (s["duration"] / 60) or 1
        avg_kda = (s["kills"] + s["assists"]) / max(s["deaths"], 1)
        winrate = s["wins"] / g
        cs_per_min = s["cs"] / mins
        dmg_per_min = s["dmg"] / mins

        score = (
            winrate * 4.0 +
            min(avg_kda / 5, 1) * 3.0 +
            min(cs_per_min / 8, 1) * 1.5 +
            min(dmg_per_min / 700, 1) * 1.5
        )
        top_champ_results.append({
            "champion": champ,
            "games": g,
            "winrate": round(winrate * 100),
            "avg_kda": round(avg_kda, 2),
            "cs_per_min": round(cs_per_min, 1),
            "score": round(score, 1),
        })
    top_champ_results.sort(key=lambda x: -x["score"])

    # --- Build comp analysis response ---
    comp_results = []
    role_order = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    role_display = {"TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid", "BOTTOM": "ADC", "UTILITY": "Support"}

    for comp_type, cst in comp_stats.items():
        if cst["games"] < 1:
            continue
        best_picks = []
        for champ, pick in cst["picks"].items():
            g = pick["games"]
            mins = (pick["duration"] / 60) or 1
            avg_kda = (pick["kills"] + pick["assists"]) / max(pick["deaths"], 1)
            best_picks.append({
                "champion": champ,
                "games": g,
                "winrate": round((pick["wins"] / g) * 100),
                "avg_kda": round(avg_kda, 2),
                "cs_per_min": round(pick["cs"] / mins, 1),
                "dmg_per_min": round(pick["dmg"] / mins),
            })
        best_picks.sort(key=lambda x: (-x["winrate"], -x["avg_kda"]))

        # Build role breakdown: most-played champion per role in this comp
        role_breakdown = {}
        for role in role_order:
            champs = cst["role_picks"].get(role, {})
            if not champs:
                continue
            # Sort by games played, then winrate
            sorted_champs = sorted(champs.items(), key=lambda x: (-x[1]["games"], -x[1]["wins"]))
            top_champs = []
            for c_name, c_data in sorted_champs[:2]:  # top 2 per role
                wr = round((c_data["wins"] / c_data["games"]) * 100) if c_data["games"] > 0 else 0
                top_champs.append({"champion": c_name, "games": c_data["games"], "winrate": wr})
            role_breakdown[role_display[role]] = top_champs

        comp_results.append({
            "comp_type": comp_type,
            "games": cst["games"],
            "wins": cst["wins"],
            "winrate": round((cst["wins"] / cst["games"]) * 100),
            "best_adcs": best_picks[:3],
            "role_label": role_label,
            "role_breakdown": role_breakdown,
        })
    comp_results.sort(key=lambda x: (-x["winrate"] if x["games"] >= 2 else -50, -x["games"]))

    return {
        "top_champions": top_champ_results[:3],
        "comp_analysis": comp_results[:5],
        "primary_role": role_label,
        "total_matches_analyzed": len(all_ids),
    }


# ---------------------------------------------------------------------------
# Live Champ Select — LCU integration
# ---------------------------------------------------------------------------

from app.services.lcu import lcu, parse_champ_select
from app.services.banpick import (
    build_banpick_profile,
    get_recommendations,
    champ_name,
    CHAMP_ID_TO_NAME,
)
from app.services.profile_store import get_profile, save_profile

# In-memory profile cache (built on search, reused during champ select)
_banpick_profiles: dict[str, dict] = {}  # puuid -> profile


@router.get("/lcu/status")
async def lcu_status():
    """Check if the League client is running and accessible."""
    connected = lcu.connect()
    if not connected:
        return {"connected": False, "phase": None}
    phase = await lcu.get_gameflow_phase()
    return {"connected": True, "phase": phase}


@router.get("/lcu/champ-select")
async def lcu_champ_select(summoner: str = ""):
    """
    Get current champ select state + ban/pick recommendations.
    Requires the League client to be open and in champ select.
    """
    # Check LCU connection
    if not lcu.connect():
        return {"in_champ_select": False, "error": "League client not detected. Is it running?"}

    # Check gameflow phase
    phase = await lcu.get_gameflow_phase()
    if phase != "ChampSelect":
        return {"in_champ_select": False, "phase": phase}

    # Get champ select session
    session = await lcu.get_champ_select_session()
    if not session:
        return {"in_champ_select": False, "error": "Could not read champ select session."}

    # Parse the session
    parsed = parse_champ_select(session)

    # Convert champion IDs to names
    ally_picks = [
        champ_name(p["champion_id"]) for p in parsed["my_team"]
        if p["champion_id"] > 0 and not p["is_local"]
    ]
    enemy_picks = [
        champ_name(p["champion_id"]) for p in parsed["their_team"]
        if p["champion_id"] > 0
    ]
    all_bans = [
        champ_name(cid) for cid in parsed["bans"]["my_team"] + parsed["bans"]["their_team"]
    ]
    my_role = parsed["my_role"]
    my_pick = champ_name(parsed["my_champion_id"]) if parsed["my_champion_id"] > 0 else ""

    # Get recommendations if we have a profile
    recommendations = {}
    if summoner and "#" in summoner:
        game_name, tag_line = summoner.split("#", 1)
        puuid = get_puuid_by_riot_id(game_name.strip(), tag_line.strip())
        if puuid:
            # Build or use cached profile (check memory, then disk)
            if puuid not in _banpick_profiles:
                stored = get_profile(puuid)
                if stored:
                    _banpick_profiles[puuid] = stored
                else:
                    _banpick_profiles[puuid] = await build_banpick_profile(puuid)
                    save_profile(puuid, _banpick_profiles[puuid])
            profile = _banpick_profiles[puuid]
            recommendations = get_recommendations(
                profile, my_role, ally_picks, enemy_picks, all_bans
            )

    return {
        "in_champ_select": True,
        "phase": parsed["phase"],
        "my_role": my_role,
        "my_pick": my_pick,
        "ally_picks": ally_picks,
        "enemy_picks": enemy_picks,
        "bans": all_bans,
        "recommendations": recommendations,
    }


@router.post("/banpick-profile")
async def build_profile(summoner: str):
    """
    Pre-build the ban/pick profile for a summoner.
    Called after search so the profile is ready when champ select starts.
    Persists to disk for use across server restarts.
    """
    if "#" not in summoner:
        raise HTTPException(status_code=400, detail="Enter Riot ID as Name#TAG")

    game_name, tag_line = summoner.split("#", 1)
    puuid = get_puuid_by_riot_id(game_name.strip(), tag_line.strip())
    if not puuid:
        raise HTTPException(status_code=404, detail="Summoner not found.")

    profile = await build_banpick_profile(puuid)
    _banpick_profiles[puuid] = profile
    save_profile(puuid, profile)

    return {
        "status": "ready",
        "enemy_threats": profile["enemy_threats"][:5],
        "best_picks": profile["best_picks"][:5],
        "synergies": profile["synergies"][:5],
    }
