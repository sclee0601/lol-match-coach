"""
LoL Match Coach — Live Champ Select Helper (GUI version)
A standalone desktop app that connects to your League client during champ select
and shows ban/pick recommendations based on your match history.
"""

import base64
import os
import json
import threading
import tkinter as tk
import httpx
import urllib3
from matchup_data import get_matchup_context, evaluate_pick_vs_enemies

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_lockfile_cache: str | None = None
_lockfile_cache_time: float = 0


def find_lockfile() -> str | None:
    """Auto-find the League lockfile. Caches result for 10 seconds to avoid subprocess spam."""
    global _lockfile_cache, _lockfile_cache_time
    import time

    # Return cached result if checked within last 10 seconds
    now = time.time()
    if _lockfile_cache and (now - _lockfile_cache_time) < 10:
        if os.path.exists(_lockfile_cache):
            return _lockfile_cache
        else:
            _lockfile_cache = None

    # Check common installation paths
    common_paths = [
        r"C:\Riot Games\League of Legends\lockfile",
        r"D:\Riot Games\League of Legends\lockfile",
        r"E:\Riot Games\League of Legends\lockfile",
        r"C:\Program Files\Riot Games\League of Legends\lockfile",
        r"C:\Program Files (x86)\Riot Games\League of Legends\lockfile",
        os.path.expanduser(r"~\Riot Games\League of Legends\lockfile"),
    ]

    for path in common_paths:
        if os.path.exists(path):
            _lockfile_cache = path
            _lockfile_cache_time = now
            return path

    # Only try subprocess every 10 seconds (expensive)
    if (now - _lockfile_cache_time) < 10:
        return None
    _lockfile_cache_time = now

    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "process", "where", "name='LeagueClientUx.exe'", "get", "ExecutablePath"],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000  # CREATE_NO_WINDOW — prevents console flash
        )
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and "LeagueClientUx" in line:
                league_dir = os.path.dirname(line)
                lockfile = os.path.join(league_dir, "lockfile")
                if os.path.exists(lockfile):
                    _lockfile_cache = lockfile
                    return lockfile
    except Exception:
        pass

    return None
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "https://lol-match-coach.onrender.com/api")
POLL_INTERVAL = 2000  # ms

# ---------------------------------------------------------------------------
# LCU Connection
# ---------------------------------------------------------------------------

def read_lockfile() -> dict | None:
    """Read the League client lockfile (auto-finds the path)."""
    lockfile_path = find_lockfile()
    if not lockfile_path:
        return None
    try:
        with open(lockfile_path, "r") as f:
            content = f.read().strip()
        parts = content.split(":")
        if len(parts) < 5:
            return None
        return {"port": int(parts[2]), "password": parts[3]}
    except Exception:
        return None


def get_auth_header(password: str) -> str:
    token = base64.b64encode(f"riot:{password}".encode()).decode()
    return f"Basic {token}"


def get_gameflow_phase(port: int, auth: str) -> str | None:
    try:
        with httpx.Client(verify=False, timeout=3) as client:
            resp = client.get(f"https://127.0.0.1:{port}/lol-gameflow/v1/gameflow-phase",
                              headers={"Authorization": auth})
            return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def get_champ_select_session(port: int, auth: str) -> dict | None:
    try:
        with httpx.Client(verify=False, timeout=3) as client:
            resp = client.get(f"https://127.0.0.1:{port}/lol-champ-select/v1/session",
                              headers={"Authorization": auth})
            return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def get_current_queue_id(port: int, auth: str) -> int | None:
    """Get the current queue ID to determine game mode."""
    try:
        with httpx.Client(verify=False, timeout=3) as client:
            resp = client.get(f"https://127.0.0.1:{port}/lol-gameflow/v1/session",
                              headers={"Authorization": auth})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("gameData", {}).get("queue", {}).get("id", None)
            return None
    except Exception:
        return None


# Summoner's Rift queue IDs (ranked, draft, clash)
SUPPORTED_QUEUES = {
    420,   # Ranked Solo/Duo
    440,   # Ranked Flex
    400,   # Normal Draft
    700,   # Clash
    410,   # Ranked Solo (old)
}


# ---------------------------------------------------------------------------
# Champion data
# ---------------------------------------------------------------------------

CHAMP_ID_TO_NAME: dict[int, str] = {}


def load_champion_ids():
    global CHAMP_ID_TO_NAME
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            latest = resp.json()[0]
            resp = client.get(f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json")
            for name, data in resp.json().get("data", {}).items():
                CHAMP_ID_TO_NAME[int(data["key"])] = name
    except Exception:
        pass


def champ_name(cid: int) -> str:
    return CHAMP_ID_TO_NAME.get(cid, f"#{cid}")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

PROFILE_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile_cache.json")


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


def fetch_profile_sync(summoner: str) -> dict | None:
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{CLOUD_API_URL}/banpick-profile", params={"summoner": summoner})
            if resp.status_code == 200:
                profile = resp.json()
                save_profile_cache(profile)
                return profile
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def get_recommendations(profile: dict, my_role: str, ally_picks: list, enemy_picks: list, banned: list) -> dict:
    banned_lower = {b.lower() for b in banned}
    enemy_lower = {e.lower() for e in enemy_picks}
    ally_lower = {a.lower() for a in ally_picks}

    ban_suggestions = []
    for threat in profile.get("enemy_threats", []):
        if threat["champion"].lower() not in banned_lower and threat["champion"].lower() not in enemy_lower:
            ban_suggestions.append(threat)
        if len(ban_suggestions) >= 3:
            break

    # Pick suggestions — factor in matchups against enemy draft
    role_map = {"top": "TOP", "jungle": "JUNGLE", "middle": "MIDDLE", "bottom": "BOTTOM", "utility": "UTILITY"}
    norm_role = role_map.get(my_role.lower(), my_role.upper())

    # Gather candidate picks — use comp classifier + counter enemy comp
    candidates = []

    # Classify ally comp using CHAMPION_TAGS
    from matchup_data import CHAMPION_DATA, CHAMPION_TAGS

    ally_tags = []
    for ally in ally_picks:
        ally_tags.extend(CHAMPION_TAGS.get(ally, []))

    enemy_tags = []
    for enemy in enemy_picks:
        enemy_tags.extend(CHAMPION_TAGS.get(enemy, []))

    # What comp is our team building?
    team_has_engage = "engage" in ally_tags or "tank" in ally_tags
    team_has_peel = "peel" in ally_tags or "enchanter" in ally_tags
    team_has_hypercarry = "hypercarry" in ally_tags
    team_has_poke = ally_tags.count("poke") >= 2
    team_has_dive = ally_tags.count("dive") >= 2

    # What is enemy comp threatening?
    enemy_has_dive = enemy_tags.count("dive") >= 2 or enemy_tags.count("burst") >= 2
    enemy_has_poke = enemy_tags.count("poke") >= 2
    enemy_has_engage = enemy_tags.count("engage") >= 2
    enemy_has_split = "split" in enemy_tags
    enemy_has_hypercarry = "hypercarry" in enemy_tags
    enemy_has_scaling = enemy_has_hypercarry or enemy_tags.count("sustain_dps") >= 2

    # Get role-appropriate champions from profile
    # Use mastery pool (actual mains) as primary, fall back to recent picks
    champion_pool = profile.get("mastery_pool", [])
    recent_picks = profile.get("best_picks", [])

    # Build candidate list from mastery pool first
    for mastery_champ in champion_pool:
        champ = mastery_champ["champion"]
        if champ.lower() in banned_lower | ally_lower | enemy_lower:
            continue
        # Check if this champion fits the assigned role (from CHAMPION_TAGS)
        champ_tags = CHAMPION_TAGS.get(champ, [])
        role_fits = False
        if norm_role == "UTILITY" and ("enchanter" in champ_tags or "peel" in champ_tags or "engage" in champ_tags or "tank" in champ_tags or "pick" in champ_tags):
            role_fits = True
        elif norm_role == "BOTTOM" and ("sustain_dps" in champ_tags or "hypercarry" in champ_tags or "burst" in champ_tags or "poke" in champ_tags or "safe" in champ_tags):
            role_fits = True
        elif norm_role == "MIDDLE" and ("burst" in champ_tags or "poke" in champ_tags or "assassin" in champ_tags or "sustain_dps" in champ_tags or "roam" in champ_tags):
            role_fits = True
        elif norm_role == "JUNGLE" and ("engage" in champ_tags or "dive" in champ_tags or "tank" in champ_tags or "burst" in champ_tags or "pick" in champ_tags):
            role_fits = True
        elif norm_role == "TOP" and ("split" in champ_tags or "tank" in champ_tags or "dive" in champ_tags or "lane_bully" in champ_tags or "engage" in champ_tags):
            role_fits = True
        elif not norm_role:
            role_fits = True

        if not role_fits:
            continue

        matchup = evaluate_pick_vs_enemies(champ, enemy_picks)

        # Get winrate from recent picks if available
        recent = next((p for p in recent_picks if p["champion"] == champ), None)
        winrate = recent["winrate"] if recent else 50  # Default 50% if no recent data

        comp_bonus = 0
        pick_tags = CHAMPION_TAGS.get(pick["champion"], [])

        # Complete our team comp
        if not team_has_engage and ("engage" in pick_tags or "tank" in pick_tags):
            comp_bonus += 3
        if not team_has_peel and ("peel" in pick_tags or "enchanter" in pick_tags):
            comp_bonus += 2
        if team_has_hypercarry and ("peel" in pick_tags or "hypercarry_enabler" in pick_tags):
            comp_bonus += 3  # Protect the carry
        if team_has_poke and "poke" in pick_tags:
            comp_bonus += 1
        if team_has_dive and "dive" in pick_tags:
            comp_bonus += 1

        # Counter enemy comp
        if enemy_has_dive and ("peel" in pick_tags or "enchanter" in pick_tags):
            comp_bonus += 3  # Peel counters dive
        if enemy_has_poke and ("engage" in pick_tags or "dive" in pick_tags):
            comp_bonus += 2  # Engage counters poke
        if enemy_has_engage and ("peel" in pick_tags or "safe" in pick_tags):
            comp_bonus += 2  # Disengage counters engage
        if enemy_has_split and ("engage" in pick_tags or "wombo" in pick_tags):
            comp_bonus += 1  # Force 5v5 vs split
        if enemy_has_scaling and ("engage" in pick_tags or "all_in" in pick_tags or "lane_bully" in pick_tags):
            comp_bonus += 3  # Punish scaling comps with early aggression

        candidates.append({
            "champion": champ,
            "winrate": winrate,
            "games": mastery_champ.get("mastery_level", 0),
            "matchup_score": matchup["matchup_score"],
            "matchup_details": matchup["details"],
            "comp_bonus": comp_bonus,
        })

    # Fallback if no role-specific picks from mastery
    if len(candidates) == 0:
        for pick in recent_picks:
            if pick["champion"].lower() in banned_lower | ally_lower | enemy_lower:
                continue
            matchup = evaluate_pick_vs_enemies(pick["champion"], enemy_picks)
            candidates.append({
                "champion": pick["champion"],
                "winrate": pick["winrate"],
                "games": pick.get("games", 0),
                "matchup_score": matchup["matchup_score"],
                "matchup_details": matchup["details"],
                "comp_bonus": 0,
            })

    # Sort: 1) Comp needs + counter enemy  2) Matchup 상성  3) Personal winrate
    candidates.sort(key=lambda x: (
        -(x.get("comp_bonus", 0) * 20),
        -(x["matchup_score"] * 15),
        -(x["winrate"]),
    ))

    pick_suggestions = candidates[:3]

    # Also generate "ideal picks" regardless of user's pool
    # Check ALL champions for the role, not just user's mastery
    ideal_candidates = []
    all_role_champs = []
    for champ, tags in CHAMPION_TAGS.items():
        if champ.lower() in banned_lower | ally_lower | enemy_lower:
            continue
        # Role filter
        role_fits = False
        if norm_role == "UTILITY" and ("enchanter" in tags or "peel" in tags or "engage" in tags or "tank" in tags or "pick" in tags):
            role_fits = True
        elif norm_role == "BOTTOM" and ("sustain_dps" in tags or "hypercarry" in tags or "burst" in tags or "safe" in tags):
            role_fits = True
        elif norm_role == "MIDDLE" and ("burst" in tags or "poke" in tags or "sustain_dps" in tags or "roam" in tags):
            role_fits = True
        elif norm_role == "JUNGLE" and ("engage" in tags or "dive" in tags or "tank" in tags or "burst" in tags or "pick" in tags):
            role_fits = True
        elif norm_role == "TOP" and ("split" in tags or "tank" in tags or "dive" in tags or "lane_bully" in tags or "engage" in tags):
            role_fits = True
        elif not norm_role:
            role_fits = True
        if not role_fits:
            continue

        matchup = evaluate_pick_vs_enemies(champ, enemy_picks)
        comp_bonus = 0

        if not team_has_engage and ("engage" in tags or "tank" in tags):
            comp_bonus += 3
        if not team_has_peel and ("peel" in tags or "enchanter" in tags):
            comp_bonus += 2
        if team_has_hypercarry and ("peel" in tags or "hypercarry_enabler" in tags):
            comp_bonus += 3
        if enemy_has_dive and ("peel" in tags or "enchanter" in tags):
            comp_bonus += 3
        if enemy_has_poke and ("engage" in tags or "dive" in tags):
            comp_bonus += 2
        if enemy_has_engage and ("peel" in tags or "safe" in tags):
            comp_bonus += 2
        if enemy_has_scaling and ("engage" in tags or "all_in" in tags or "lane_bully" in tags):
            comp_bonus += 3

        ideal_candidates.append({
            "champion": champ,
            "comp_bonus": comp_bonus,
            "matchup_score": matchup["matchup_score"],
            "matchup_details": matchup["details"],
        })

    ideal_candidates.sort(key=lambda x: (-(x["comp_bonus"] * 20), -(x["matchup_score"] * 15)))
    # Filter out champions already in pick_suggestions
    pick_champs = {p["champion"] for p in pick_suggestions}
    ideal_picks = [c for c in ideal_candidates if c["champion"] not in pick_champs][:3]

    # Synergy
    synergy = [s for s in profile.get("synergies", []) if s["champion"].lower() in ally_lower]

    return {"ban_suggestions": ban_suggestions, "pick_suggestions": pick_suggestions, "ideal_picks": ideal_picks, "synergy_matches": synergy}


def parse_session(session: dict) -> dict:
    local_cell = session.get("localPlayerCellId", -1)
    my_role = ""
    my_champ = 0
    ally_picks = []
    enemy_picks = []
    bans = []

    for action_group in session.get("actions", []):
        for action in action_group:
            # Include both completed and in-progress bans/picks
            cid = action.get("championId", 0)
            if cid <= 0:
                continue
            if action.get("type") == "ban" and (action.get("completed") or action.get("isInProgress")):
                bans.append(champ_name(cid))
            elif action.get("type") == "pick" and action.get("completed"):
                # Completed picks go to ally/enemy based on actor
                actor_cell = action.get("actorCellId", -1)
                is_ally = any(p.get("cellId") == actor_cell for p in session.get("myTeam", []))
                if actor_cell == local_cell:
                    pass  # handled below
                elif is_ally:
                    if champ_name(cid) not in ally_picks:
                        ally_picks.append(champ_name(cid))
                else:
                    if champ_name(cid) not in enemy_picks:
                        enemy_picks.append(champ_name(cid))

    for p in session.get("myTeam", []):
        cid = p.get("championId", 0) or p.get("championPickIntent", 0)
        if p.get("cellId") == local_cell:
            my_role = p.get("assignedPosition", "")
            my_champ = cid
        elif cid > 0:
            name = champ_name(cid)
            if name not in ally_picks:
                ally_picks.append(name)

    for p in session.get("theirTeam", []):
        cid = p.get("championId", 0)
        if cid > 0:
            name = champ_name(cid)
            if name not in enemy_picks:
                enemy_picks.append(name)

    return {"my_role": my_role, "my_champ": champ_name(my_champ) if my_champ > 0 else "", "ally_picks": ally_picks, "enemy_picks": enemy_picks, "bans": bans}


# ---------------------------------------------------------------------------
# GUI App
# ---------------------------------------------------------------------------

class MatchCoachApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LoL Match Coach — Draft Helper")
        self.root.geometry("520x600")
        self.root.configure(bg="#0d1117")
        self.root.resizable(False, False)

        self.profile = None
        self.summoner = ""

        self._build_login_screen()

    def _build_login_screen(self):
        """Initial screen: auto-detect from League client."""
        self._clear()

        frame = tk.Frame(self.root, bg="#0d1117")
        frame.pack(expand=True)

        tk.Label(frame, text="⚔️ LoL Match Coach", font=("Segoe UI", 18, "bold"),
                 fg="#c89b3c", bg="#0d1117").pack(pady=(0, 5))
        tk.Label(frame, text="Live Draft Helper", font=("Segoe UI", 11),
                 fg="#6b7280", bg="#0d1117").pack(pady=(0, 30))

        self.status_label = tk.Label(frame, text="Detecting League client...",
                                     font=("Segoe UI", 10), fg="#9ca3af", bg="#0d1117")
        self.status_label.pack(pady=10)

        # Auto-detect on startup
        self.root.after(500, self._try_auto_connect)

    def _try_auto_connect(self):
        """Try to auto-detect summoner from League client."""
        lockfile = read_lockfile()
        if lockfile:
            try:
                port = lockfile["port"]
                auth = get_auth_header(lockfile["password"])
                with httpx.Client(verify=False, timeout=5) as client:
                    resp = client.get(f"https://127.0.0.1:{port}/lol-summoner/v1/current-summoner",
                                      headers={"Authorization": auth})
                    if resp.status_code == 200:
                        data = resp.json()
                        game_name = data.get("gameName", "")
                        tag_line = data.get("tagLine", "")
                        if game_name and tag_line:
                            self.summoner = f"{game_name}#{tag_line}"
                            self.status_label.config(text=f"Connected: {self.summoner}", fg="#22c55e")
                            self.root.update()
                            threading.Thread(target=self._load_profile, daemon=True).start()
                            return
            except Exception:
                pass

        # Client not found — retry every 3 seconds
        self.status_label.config(text="⏳ Waiting for League client...", fg="#9ca3af")
        self.root.after(3000, self._try_auto_connect)

    def _load_profile(self):
        # Load champion IDs and cached profile in parallel
        load_champion_ids()

        # Use cached profile FIRST for instant startup
        self.profile = load_cached_profile()
        if self.profile:
            # Show main screen immediately with cached data
            self.root.after(0, self._build_main_screen)
            # Refresh in background (updates for next champ select)
            threading.Thread(target=self._refresh_profile, daemon=True).start()
        else:
            # No cache — must fetch (first time only)
            self.profile = fetch_profile_sync(self.summoner)
            if self.profile:
                self.root.after(0, self._build_main_screen)
            else:
                self.root.after(0, lambda: self.status_label.config(
                    text="⚠ Could not load profile. Check internet connection.", fg="#ef4444"))
                self.root.after(0, lambda: self.connect_btn.config(state="normal"))

    def _refresh_profile(self):
        """Silently refresh profile in background."""
        fresh = fetch_profile_sync(self.summoner)
        if fresh:
            self.profile = fresh

    def _build_main_screen(self):
        """Main screen: waiting / champ select display."""
        self._clear()

        # Header
        header = tk.Frame(self.root, bg="#0d1117")
        header.pack(fill="x", padx=20, pady=(15, 10))
        tk.Label(header, text="⚡ Live Draft", font=("Segoe UI", 14, "bold"),
                 fg="#c89b3c", bg="#0d1117").pack(side="left")
        tk.Label(header, text=self.summoner, font=("Segoe UI", 10),
                 fg="#6b7280", bg="#0d1117").pack(side="right")

        # Status
        self.phase_label = tk.Label(self.root, text="Waiting for champ select...",
                                    font=("Segoe UI", 10), fg="#9ca3af", bg="#0d1117")
        self.phase_label.pack(pady=(0, 10))

        # Content area
        self.content_frame = tk.Frame(self.root, bg="#0d1117")
        self.content_frame.pack(fill="both", expand=True, padx=20)

        # Start polling
        self._poll()

    def _poll(self):
        """Poll LCU every 2 seconds."""
        lockfile = read_lockfile()
        if not lockfile:
            if not hasattr(self, '_last_state') or self._last_state != 'waiting':
                self.phase_label.config(text="⏳ Waiting for League client...")
                self._clear_content()
                self._last_state = 'waiting'
        else:
            port = lockfile["port"]
            auth = get_auth_header(lockfile["password"])
            phase = get_gameflow_phase(port, auth)

            if phase is None:
                # Client was closed or connection lost
                if not hasattr(self, '_last_state') or self._last_state != 'disconnected':
                    self.phase_label.config(text="⏳ Waiting for League client...")
                    self._clear_content()
                    self._last_state = 'disconnected'
            elif phase == "ChampSelect":
                # Check if it's a supported game mode (Summoner's Rift only)
                queue_id = get_current_queue_id(port, auth)
                if queue_id is not None and queue_id not in SUPPORTED_QUEUES:
                    if not hasattr(self, '_last_state') or self._last_state != f'skip_{queue_id}':
                        self.phase_label.config(text=f"⏭️ Non-Rift mode — skipping", fg="#6b7280")
                        self._clear_content()
                        self._last_state = f'skip_{queue_id}'
                else:
                    self.phase_label.config(text="🎯 IN CHAMP SELECT", fg="#22c55e")
                    session = get_champ_select_session(port, auth)
                    if session:
                        # Only redraw if draft state changed
                        draft = parse_session(session)
                        draft_key = f"{draft['bans']}_{draft['ally_picks']}_{draft['enemy_picks']}_{draft['my_champ']}"
                        if not hasattr(self, '_last_draft_key') or self._last_draft_key != draft_key:
                            self._display_draft(session)
                            self._last_draft_key = draft_key
                    self._last_state = 'champ_select'
            else:
                if not hasattr(self, '_last_state') or self._last_state != f'phase_{phase}':
                    self.phase_label.config(text=f"Status: {phase or 'Waiting'}...", fg="#9ca3af")
                    self._clear_content()
                    self._last_state = f'phase_{phase}'

        self.root.after(POLL_INTERVAL, self._poll)

    def _display_draft(self, session: dict):
        self._clear_content()
        draft = parse_session(session)

        f = self.content_frame

        # Role
        if draft["my_role"]:
            tk.Label(f, text=f"Role: {draft['my_role'].upper()}", font=("Segoe UI", 11, "bold"),
                     fg="#e8d5a3", bg="#0d1117").pack(anchor="w")

        # Draft state
        if draft["bans"]:
            tk.Label(f, text=f"Bans: {', '.join(draft['bans'])}", font=("Segoe UI", 9),
                     fg="#6b7280", bg="#0d1117").pack(anchor="w", pady=(5, 0))
        if draft["ally_picks"]:
            tk.Label(f, text=f"Allies: {', '.join(draft['ally_picks'])}", font=("Segoe UI", 9),
                     fg="#60a5fa", bg="#0d1117").pack(anchor="w")
        if draft["enemy_picks"]:
            tk.Label(f, text=f"Enemies: {', '.join(draft['enemy_picks'])}", font=("Segoe UI", 9),
                     fg="#f87171", bg="#0d1117").pack(anchor="w")

        # Only show recommendations AFTER there are actual picks/bans to react to
        has_draft_info = len(draft["bans"]) > 0 or len(draft["ally_picks"]) > 0 or len(draft["enemy_picks"]) > 0

        if not has_draft_info:
            tk.Frame(f, height=1, bg="#1f2937").pack(fill="x", pady=12)
            tk.Label(f, text="Waiting for picks & bans...", font=("Segoe UI", 10),
                     fg="#6b7280", bg="#0d1117").pack()
            return

        recs = get_recommendations(self.profile, draft["my_role"], draft["ally_picks"], draft["enemy_picks"], draft["bans"])

        # Separator
        tk.Frame(f, height=1, bg="#1f2937").pack(fill="x", pady=12)

        # Ban suggestions with context
        if recs["ban_suggestions"]:
            tk.Label(f, text="🚫 BAN THESE", font=("Segoe UI", 10, "bold"),
                     fg="#ef4444", bg="#0d1117").pack(anchor="w")
            for b in recs["ban_suggestions"]:
                tk.Label(f, text=f"  {b['champion']} — you lose {b['loss_rate']}%",
                         font=("Segoe UI", 10), fg="#fca5a5", bg="#0d1117").pack(anchor="w")
                ctx = get_matchup_context(b["champion"])
                if ctx.get("tip"):
                    tk.Label(f, text=f"      {ctx['tip']}", font=("Segoe UI", 9),
                             fg="#6b7280", bg="#0d1117").pack(anchor="w")
            tk.Label(f, text="", bg="#0d1117").pack()

        # Pick suggestions with matchup context
        if recs["pick_suggestions"]:
            tk.Label(f, text="✅ FROM YOUR POOL", font=("Segoe UI", 10, "bold"),
                     fg="#22c55e", bg="#0d1117").pack(anchor="w")
            for p in recs["pick_suggestions"]:
                # Champion row with image
                pick_frame = tk.Frame(f, bg="#0d1117")
                pick_frame.pack(anchor="w", fill="x", pady=2)

                # Load champion image
                self._load_champ_image(pick_frame, p["champion"])

                # Info column
                info_frame = tk.Frame(pick_frame, bg="#0d1117")
                info_frame.pack(side="left", padx=(8, 0))

                # Main line: champion + winrate
                tk.Label(info_frame, text=f"{p['champion']} — {p['winrate']}% WR ({p['games']}G)",
                         font=("Segoe UI", 10, "bold"), fg="#86efac", bg="#0d1117").pack(anchor="w")

                # Laning/Late context from matchup data
                ctx = get_matchup_context(p["champion"])
                if ctx.get("tip"):
                    # Show lane/late power
                    power_text = f"라인: {ctx['lane']} | 후반: {ctx['late']} | {ctx['style']}"
                    tk.Label(info_frame, text=power_text, font=("Segoe UI", 8),
                             fg="#9ca3af", bg="#0d1117").pack(anchor="w")

                # Matchup details (상성 vs enemies)
                if p.get("matchup_details"):
                    for detail in p["matchup_details"]:
                        color = "#86efac" if "유리" in detail else "#fca5a5"
                        tk.Label(info_frame, text=detail, font=("Segoe UI", 8),
                                 fg=color, bg="#0d1117").pack(anchor="w")

            tk.Label(f, text="", bg="#0d1117").pack()

        # Ideal picks (best for situation, regardless of user's pool)
        if recs.get("ideal_picks"):
            tk.Label(f, text="💡 IDEAL FOR THIS SITUATION", font=("Segoe UI", 10, "bold"),
                     fg="#f0c040", bg="#0d1117").pack(anchor="w")
            for p in recs["ideal_picks"]:
                pick_frame = tk.Frame(f, bg="#0d1117")
                pick_frame.pack(anchor="w", fill="x", pady=2)
                self._load_champ_image(pick_frame, p["champion"])
                info_frame = tk.Frame(pick_frame, bg="#0d1117")
                info_frame.pack(side="left", padx=(8, 0))
                tk.Label(info_frame, text=f"{p['champion']}",
                         font=("Segoe UI", 10, "bold"), fg="#fde68a", bg="#0d1117").pack(anchor="w")
                ctx = get_matchup_context(p["champion"])
                if ctx.get("tip"):
                    tk.Label(info_frame, text=ctx["tip"], font=("Segoe UI", 8),
                             fg="#9ca3af", bg="#0d1117").pack(anchor="w")
                if p.get("matchup_details"):
                    for detail in p["matchup_details"]:
                        color = "#86efac" if "유리" in detail else "#fca5a5"
                        tk.Label(info_frame, text=detail, font=("Segoe UI", 8),
                                 fg=color, bg="#0d1117").pack(anchor="w")
            tk.Label(f, text="", bg="#0d1117").pack()

        # Synergy
        if recs["synergy_matches"]:
            tk.Label(f, text="🤝 SYNERGY", font=("Segoe UI", 10, "bold"),
                     fg="#60a5fa", bg="#0d1117").pack(anchor="w")
            for s in recs["synergy_matches"]:
                tk.Label(f, text=f"  {s['champion']} — {s['winrate']}% WR together",
                         font=("Segoe UI", 10), fg="#93c5fd", bg="#0d1117").pack(anchor="w")

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _load_champ_image(self, parent: tk.Frame, champion: str):
        """Load a champion icon from Data Dragon and display it."""
        try:
            from io import BytesIO
            from tkinter import PhotoImage
            import urllib.request

            # Data Dragon champion icon URL
            url = f"https://ddragon.leagueoflegends.com/cdn/15.10.1/img/champion/{champion}.png"

            # Cache images to avoid re-downloading
            if not hasattr(self, '_image_cache'):
                self._image_cache = {}

            if champion in self._image_cache:
                img = self._image_cache[champion]
            else:
                # Download and resize (tkinter PhotoImage supports PNG via subsample)
                data = urllib.request.urlopen(url, timeout=3).read()
                img = tk.PhotoImage(data=data)
                # Subsample to ~32x32 (original is 120x120)
                img = img.subsample(3, 3)
                self._image_cache[champion] = img

            label = tk.Label(parent, image=img, bg="#0d1117")
            label.image = img  # Keep reference
            label.pack(side="left")
        except Exception:
            # If image fails, just show text placeholder
            tk.Label(parent, text="🎮", font=("Segoe UI", 14), bg="#0d1117").pack(side="left")

    def _clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = MatchCoachApp()
    app.run()
