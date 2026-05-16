"""
LoL Match Coach — Live Champ Select Helper (GUI version)
A standalone desktop app that connects to your League client during champ select
and shows ban/pick recommendations based on your match history.
"""

import asyncio
import base64
import os
import json
import threading
import tkinter as tk
from tkinter import ttk
import httpx
import urllib3
from matchup_data import get_matchup_context, evaluate_pick_vs_enemies

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LEAGUE_PATH = r"C:\Riot Games\League of Legends"
LOCKFILE_PATH = os.path.join(LEAGUE_PATH, "lockfile")
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "http://localhost:8000/api")
POLL_INTERVAL = 2000  # ms

# ---------------------------------------------------------------------------
# LCU Connection
# ---------------------------------------------------------------------------

def read_lockfile() -> dict | None:
    if not os.path.exists(LOCKFILE_PATH):
        return None
    try:
        with open(LOCKFILE_PATH, "r") as f:
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

    # Gather candidate picks
    candidates = []
    for pick in profile.get("best_picks", []):
        if pick["champion"].lower() in banned_lower | ally_lower | enemy_lower:
            continue
        if pick.get("role") == norm_role or not norm_role:
            # Evaluate matchup against enemy picks
            matchup = evaluate_pick_vs_enemies(pick["champion"], enemy_picks)
            candidates.append({
                **pick,
                "matchup_score": matchup["matchup_score"],
                "matchup_details": matchup["details"],
            })

    # If not enough role-specific picks, add others
    if len(candidates) < 5:
        for pick in profile.get("best_picks", []):
            if pick["champion"].lower() in banned_lower | ally_lower | enemy_lower:
                continue
            if not any(c["champion"] == pick["champion"] for c in candidates):
                matchup = evaluate_pick_vs_enemies(pick["champion"], enemy_picks)
                candidates.append({
                    **pick,
                    "matchup_score": matchup["matchup_score"],
                    "matchup_details": matchup["details"],
                })

    # Sort by: matchup score first (don't pick into counters), then winrate
    # Penalize picks with negative matchup, boost picks with positive matchup
    candidates.sort(key=lambda x: (
        -(x["winrate"] + x["matchup_score"] * 10),  # matchup heavily weighted
    ))

    pick_suggestions = candidates[:3]

    # Synergy
    synergy = [s for s in profile.get("synergies", []) if s["champion"].lower() in ally_lower]

    return {"ban_suggestions": ban_suggestions, "pick_suggestions": pick_suggestions, "synergy_matches": synergy}


def parse_session(session: dict) -> dict:
    local_cell = session.get("localPlayerCellId", -1)
    my_role = ""
    my_champ = 0
    ally_picks = []
    enemy_picks = []
    bans = []

    for action_group in session.get("actions", []):
        for action in action_group:
            if action.get("type") == "ban" and action.get("completed") and action.get("championId", 0) > 0:
                bans.append(champ_name(action["championId"]))

    for p in session.get("myTeam", []):
        cid = p.get("championId", 0) or p.get("championPickIntent", 0)
        if p.get("cellId") == local_cell:
            my_role = p.get("assignedPosition", "")
            my_champ = cid
        elif cid > 0:
            ally_picks.append(champ_name(cid))

    for p in session.get("theirTeam", []):
        cid = p.get("championId", 0)
        if cid > 0:
            enemy_picks.append(champ_name(cid))

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
        """Initial screen: enter Riot ID."""
        self._clear()

        frame = tk.Frame(self.root, bg="#0d1117")
        frame.pack(expand=True)

        tk.Label(frame, text="⚔️ LoL Match Coach", font=("Segoe UI", 18, "bold"),
                 fg="#c89b3c", bg="#0d1117").pack(pady=(0, 5))
        tk.Label(frame, text="Live Draft Helper", font=("Segoe UI", 11),
                 fg="#6b7280", bg="#0d1117").pack(pady=(0, 30))

        tk.Label(frame, text="Enter your Riot ID:", font=("Segoe UI", 10),
                 fg="#9ca3af", bg="#0d1117").pack()

        self.entry = tk.Entry(frame, font=("Segoe UI", 12), width=25,
                              bg="#111827", fg="#e8d5a3", insertbackground="#c89b3c",
                              relief="flat", highlightthickness=1, highlightcolor="#c89b3c")
        self.entry.pack(pady=10, ipady=6)
        self.entry.insert(0, os.getenv("SUMMONER", ""))
        self.entry.bind("<Return>", lambda e: self._on_connect())

        self.connect_btn = tk.Button(frame, text="Connect", font=("Segoe UI", 11, "bold"),
                                     bg="#c89b3c", fg="#0d1117", relief="flat", cursor="hand2",
                                     command=self._on_connect, width=15)
        self.connect_btn.pack(pady=10)

        self.status_label = tk.Label(frame, text="", font=("Segoe UI", 9),
                                     fg="#6b7280", bg="#0d1117")
        self.status_label.pack(pady=5)

    def _on_connect(self):
        self.summoner = self.entry.get().strip()
        if not self.summoner or "#" not in self.summoner:
            self.status_label.config(text="⚠ Use format: Name#TAG", fg="#ef4444")
            return

        self.status_label.config(text="Loading profile...", fg="#6b7280")
        self.connect_btn.config(state="disabled")
        self.root.update()

        # Load in background thread
        threading.Thread(target=self._load_profile, daemon=True).start()

    def _load_profile(self):
        load_champion_ids()
        self.profile = load_cached_profile()
        if not self.profile:
            self.profile = fetch_profile_sync(self.summoner)

        if self.profile:
            self.root.after(0, self._build_main_screen)
        else:
            self.root.after(0, lambda: self.status_label.config(
                text="⚠ Could not load profile. Is the web app running?", fg="#ef4444"))
            self.root.after(0, lambda: self.connect_btn.config(state="normal"))

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
            self.phase_label.config(text="⏳ Waiting for League client...")
            self._clear_content()
        else:
            port = lockfile["port"]
            auth = get_auth_header(lockfile["password"])
            phase = get_gameflow_phase(port, auth)

            if phase == "ChampSelect":
                self.phase_label.config(text="🎯 IN CHAMP SELECT", fg="#22c55e")
                session = get_champ_select_session(port, auth)
                if session:
                    self._display_draft(session)
            else:
                self.phase_label.config(text=f"Status: {phase or 'Waiting'}...", fg="#9ca3af")
                self._clear_content()

        self.root.after(POLL_INTERVAL, self._poll)

    def _display_draft(self, session: dict):
        self._clear_content()
        draft = parse_session(session)
        recs = get_recommendations(self.profile, draft["my_role"], draft["ally_picks"], draft["enemy_picks"], draft["bans"])

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
            tk.Label(f, text="✅ PICK THESE", font=("Segoe UI", 10, "bold"),
                     fg="#22c55e", bg="#0d1117").pack(anchor="w")
            for p in recs["pick_suggestions"]:
                # Main line: champion + winrate
                pick_text = f"  {p['champion']} — {p['winrate']}% WR ({p['games']}G)"
                tk.Label(f, text=pick_text, font=("Segoe UI", 10), fg="#86efac", bg="#0d1117").pack(anchor="w")

                # Matchup details (상성)
                if p.get("matchup_details"):
                    for detail in p["matchup_details"]:
                        color = "#86efac" if "유리" in detail else "#fca5a5"
                        tk.Label(f, text=f"      {detail}", font=("Segoe UI", 9),
                                 fg=color, bg="#0d1117").pack(anchor="w")
                elif enemy_picks:
                    # Get general champion context
                    ctx = get_matchup_context(p["champion"])
                    if ctx.get("tip"):
                        tk.Label(f, text=f"      라인: {ctx['lane']} | 후반: {ctx['late']}",
                                 font=("Segoe UI", 9), fg="#6b7280", bg="#0d1117").pack(anchor="w")
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
