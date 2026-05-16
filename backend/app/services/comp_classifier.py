"""
Team composition classifier for League of Legends.
Categorizes team comps into archetypes based on champion roles/kits.
"""

# Champion -> primary archetype tags
# Tags: engage, peel, poke, burst, sustain_dps, split, pick, tank, enchanter
CHAMPION_TAGS: dict[str, list[str]] = {
    # --- ADCs ---
    "Jinx": ["sustain_dps", "hypercarry"],
    "KogMaw": ["sustain_dps", "hypercarry"],
    "Twitch": ["sustain_dps", "hypercarry"],
    "Vayne": ["sustain_dps", "hypercarry", "split"],
    "Aphelios": ["sustain_dps", "hypercarry"],
    "Zeri": ["sustain_dps", "hypercarry"],
    "Smolder": ["sustain_dps", "hypercarry", "poke"],
    "Caitlyn": ["poke", "siege"],
    "Ezreal": ["poke", "safe"],
    "Varus": ["poke", "engage"],
    "Jhin": ["poke", "pick", "utility"],
    "Ashe": ["utility", "engage", "poke"],
    "MissFortune": ["burst", "wombo"],
    "Xayah": ["sustain_dps", "safe"],
    "Kaisa": ["burst", "dive", "sustain_dps"],
    "Lucian": ["burst", "lane_bully"],
    "Draven": ["burst", "lane_bully"],
    "Samira": ["dive", "burst"],
    "Nilah": ["dive", "burst"],
    "Kalista": ["sustain_dps", "engage", "utility"],
    "Tristana": ["burst", "siege", "safe"],
    "Sivir": ["sustain_dps", "siege", "utility"],
    "Ziggs": ["poke", "siege"],
    "Corki": ["poke", "burst"],

    # --- Supports ---
    "Thresh": ["engage", "peel", "pick"],
    "Nautilus": ["engage", "tank", "pick"],
    "Leona": ["engage", "tank"],
    "Alistar": ["engage", "tank", "peel"],
    "Blitzcrank": ["pick", "engage"],
    "Pyke": ["pick", "engage"],
    "Rakan": ["engage", "enchanter"],
    "Rell": ["engage", "tank"],
    "Milio": ["enchanter", "peel"],
    "Lulu": ["enchanter", "peel", "hypercarry_enabler"],
    "Janna": ["enchanter", "peel"],
    "Soraka": ["enchanter", "sustain"],
    "Nami": ["enchanter", "poke", "peel"],
    "Yuumi": ["enchanter", "hypercarry_enabler"],
    "Sona": ["enchanter", "sustain", "wombo"],
    "Karma": ["enchanter", "poke"],
    "Morgana": ["peel", "pick"],
    "Lux": ["poke", "burst", "pick"],
    "Zyra": ["poke", "wombo"],
    "Brand": ["poke", "burst", "wombo"],
    "Xerath": ["poke", "siege"],
    "Vel'Koz": ["poke", "siege"],
    "Senna": ["sustain", "poke", "utility"],
    "TahmKench": ["peel", "tank"],
    "Braum": ["peel", "tank"],
    "Renata": ["enchanter", "peel"],
    "Bard": ["pick", "utility", "roam"],

    # --- Junglers ---
    "LeeSin": ["pick", "engage", "dive"],
    "JarvanIV": ["engage", "wombo", "dive"],
    "Amumu": ["engage", "wombo", "tank"],
    "Sejuani": ["engage", "tank", "wombo"],
    "Zac": ["engage", "tank"],
    "Vi": ["pick", "dive"],
    "Hecarim": ["engage", "dive"],
    "Rammus": ["engage", "tank"],
    "Maokai": ["engage", "tank", "peel"],
    "Elise": ["pick", "dive", "burst"],
    "Nidalee": ["poke", "pick"],
    "KhaZix": ["pick", "burst", "split"],
    "Rengar": ["pick", "burst"],
    "Evelynn": ["pick", "burst"],
    "Kayn": ["dive", "burst"],
    "Viego": ["dive", "sustain_dps"],
    "Graves": ["burst", "split"],
    "Kindred": ["sustain_dps", "safe"],
    "Lillia": ["poke", "wombo"],
    "Diana": ["dive", "wombo", "burst"],
    "Wukong": ["engage", "wombo", "dive"],
    "Nocturne": ["pick", "dive"],
    "Shaco": ["pick", "split"],
    "MasterYi": ["sustain_dps", "hypercarry", "split"],
    "Belveth": ["sustain_dps", "hypercarry", "split"],
    "Briar": ["dive", "burst"],
    "Ivern": ["enchanter", "peel"],
    "Nunu": ["engage", "tank", "wombo"],

    # --- Mid laners ---
    "Ahri": ["pick", "burst", "safe"],
    "Syndra": ["burst", "poke"],
    "Orianna": ["wombo", "peel", "poke"],
    "Viktor": ["poke", "wombo", "siege"],
    "Azir": ["sustain_dps", "siege", "peel"],
    "Cassiopeia": ["sustain_dps", "peel"],
    "Zed": ["burst", "pick", "split"],
    "Talon": ["burst", "pick", "roam"],
    "Fizz": ["burst", "pick", "dive"],
    "LeBlanc": ["burst", "pick"],
    "Katarina": ["burst", "dive"],
    "Akali": ["burst", "dive", "split"],
    "Yasuo": ["sustain_dps", "dive", "wombo"],
    "Yone": ["dive", "engage", "wombo"],
    "Sylas": ["dive", "burst"],
    "Galio": ["engage", "tank", "roam"],
    "TwistedFate": ["pick", "roam", "utility"],
    "Ryze": ["sustain_dps", "utility"],
    "Anivia": ["poke", "peel", "siege"],
    "Xerath": ["poke", "siege"],
    "Vel'Koz": ["poke", "siege"],
    "Lux": ["poke", "burst", "pick"],
    "Malzahar": ["pick", "siege"],
    "Veigar": ["burst", "peel", "pick"],
    "AurelionSol": ["poke", "sustain_dps", "siege"],
    "Hwei": ["poke", "wombo", "utility"],
    "Naafiri": ["burst", "pick", "dive"],
    "Zoe": ["poke", "pick", "burst"],
    "Neeko": ["wombo", "engage", "burst"],
    "Seraphine": ["wombo", "poke", "enchanter"],
    "Annie": ["engage", "burst", "wombo"],

    # --- Top laners ---
    "Ornn": ["engage", "tank", "wombo"],
    "Malphite": ["engage", "tank", "wombo"],
    "Sion": ["engage", "tank", "split"],
    "Maokai": ["engage", "tank", "peel"],
    "KSante": ["engage", "tank", "dive"],
    "Gnar": ["engage", "tank", "poke"],
    "Darius": ["lane_bully", "split"],
    "Garen": ["split", "tank"],
    "Mordekaiser": ["split", "dive"],
    "Fiora": ["split", "sustain_dps"],
    "Camille": ["split", "pick", "dive"],
    "Jax": ["split", "sustain_dps", "dive"],
    "Irelia": ["dive", "sustain_dps", "split"],
    "Riven": ["dive", "burst", "split"],
    "Aatrox": ["dive", "sustain_dps"],
    "Renekton": ["dive", "lane_bully"],
    "Jayce": ["poke", "siege", "split"],
    "Kennen": ["engage", "wombo"],
    "Rumble": ["wombo", "poke"],
    "Gangplank": ["poke", "split", "wombo"],
    "Shen": ["peel", "engage", "split"],
    "Quinn": ["split", "pick", "roam"],
    "Teemo": ["split", "poke"],
    "Nasus": ["split", "sustain_dps"],
    "Tryndamere": ["split", "sustain_dps"],
    "Yorick": ["split", "siege"],
    "Illaoi": ["split", "sustain_dps"],
    "Volibear": ["dive", "tank", "split"],
    "Urgot": ["sustain_dps", "tank"],
    "Cho'Gath": ["tank", "peel"],
    "Dr.Mundo": ["tank", "split"],
    "Singed": ["split", "engage"],
    "Poppy": ["peel", "tank"],
    "Gragas": ["engage", "peel", "burst"],
    "Ambessa": ["dive", "burst", "split"],
}

# Comp archetype definitions
COMP_TYPES = {
    "protect_the_carry": {
        "description": "Protect the Carry",
        "requires": ["hypercarry"],
        "boosted_by": ["peel", "enchanter", "hypercarry_enabler"],
        "min_score": 3,
    },
    "engage_teamfight": {
        "description": "Hard Engage / Teamfight",
        "requires": ["engage"],
        "boosted_by": ["wombo", "tank", "engage"],
        "min_score": 3,
    },
    "poke_siege": {
        "description": "Poke / Siege",
        "requires": ["poke"],
        "boosted_by": ["siege", "poke"],
        "min_score": 3,
    },
    "pick_comp": {
        "description": "Pick / Catch",
        "requires": ["pick"],
        "boosted_by": ["pick", "burst", "roam"],
        "min_score": 3,
    },
    "dive_comp": {
        "description": "Dive / Assassin",
        "requires": ["dive"],
        "boosted_by": ["burst", "dive"],
        "min_score": 3,
    },
    "split_push": {
        "description": "Split Push",
        "requires": ["split"],
        "boosted_by": ["split", "siege"],
        "min_score": 2,
    },
    "wombo_combo": {
        "description": "Wombo Combo",
        "requires": ["wombo"],
        "boosted_by": ["wombo", "engage"],
        "min_score": 3,
    },
}


def classify_comp(champions: list[str]) -> str:
    """Classify a team of 5 champions into a comp archetype."""
    # Gather all tags for the team
    all_tags: list[str] = []
    for champ in champions:
        tags = CHAMPION_TAGS.get(champ, [])
        all_tags.extend(tags)

    # Score each comp type
    scores: dict[str, int] = {}
    for comp_type, definition in COMP_TYPES.items():
        # Must have at least one champion with the required tag
        has_required = any(tag in all_tags for tag in definition["requires"])
        if not has_required:
            scores[comp_type] = 0
            continue

        score = 0
        for tag in definition["boosted_by"]:
            score += all_tags.count(tag)
        scores[comp_type] = score

    # Find the best match
    best_type = max(scores, key=lambda k: scores[k])
    if scores[best_type] >= COMP_TYPES[best_type]["min_score"]:
        return COMP_TYPES[best_type]["description"]

    # Fallback: generic teamfight
    return "Standard / Mixed"


def get_team_champions_for_player(participants: list[dict], puuid: str) -> list[str]:
    """Get the 5 champions on the player's team."""
    player = next((p for p in participants if p.get("puuid") == puuid), None)
    if not player:
        return []
    team_id = player.get("teamId", 0)
    return [p.get("championName", "") for p in participants if p.get("teamId") == team_id]
