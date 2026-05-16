"""
League Client Update (LCU) API integration.
Connects to the local League client to detect champ select and provide live data.
"""

import asyncio
import base64
import os
import re
import httpx
import ssl

LEAGUE_PATH = r"C:\Riot Games\League of Legends"
LOCKFILE_PATH = os.path.join(LEAGUE_PATH, "lockfile")


def read_lockfile() -> dict | None:
    """
    Read the League client lockfile to get connection details.
    Lockfile format: processName:pid:port:password:protocol
    Returns dict with port, password, protocol or None if not found.
    """
    if not os.path.exists(LOCKFILE_PATH):
        return None
    try:
        with open(LOCKFILE_PATH, "r") as f:
            content = f.read().strip()
        parts = content.split(":")
        if len(parts) < 5:
            return None
        return {
            "process": parts[0],
            "pid": int(parts[1]),
            "port": int(parts[2]),
            "password": parts[3],
            "protocol": parts[4],
        }
    except Exception:
        return None


def get_auth_header(password: str) -> str:
    """Build the Basic auth header for LCU API."""
    token = base64.b64encode(f"riot:{password}".encode()).decode()
    return f"Basic {token}"


class LCUConnection:
    """Manages connection to the local League client API."""

    def __init__(self):
        self.port: int | None = None
        self.auth: str | None = None
        self.base_url: str | None = None
        self.connected = False

    def connect(self) -> bool:
        """Attempt to connect to the League client."""
        lockfile = read_lockfile()
        if not lockfile:
            self.connected = False
            return False
        self.port = lockfile["port"]
        self.auth = get_auth_header(lockfile["password"])
        self.base_url = f"https://127.0.0.1:{self.port}"
        self.connected = True
        return True

    def _get_client(self) -> httpx.AsyncClient:
        """Create an async client that ignores SSL cert (LCU uses self-signed)."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": self.auth},
            verify=False,
            timeout=5,
        )

    async def get_champ_select_session(self) -> dict | None:
        """
        Get current champ select session data.
        Returns None if not in champ select.
        """
        if not self.connected:
            if not self.connect():
                return None
        try:
            async with self._get_client() as client:
                resp = await client.get("/lol-champ-select/v1/session")
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            self.connected = False
            return None

    async def get_current_summoner(self) -> dict | None:
        """Get the currently logged-in summoner info."""
        if not self.connected:
            if not self.connect():
                return None
        try:
            async with self._get_client() as client:
                resp = await client.get("/lol-summoner/v1/current-summoner")
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def get_gameflow_phase(self) -> str | None:
        """Get current gameflow phase (None, Lobby, ChampSelect, InProgress, etc.)."""
        if not self.connected:
            if not self.connect():
                return None
        try:
            async with self._get_client() as client:
                resp = await client.get("/lol-gameflow/v1/gameflow-phase")
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None


def parse_champ_select(session: dict) -> dict:
    """
    Parse a champ select session into a structured format.
    Returns picks, bans, assigned role, team members, etc.
    """
    result = {
        "phase": session.get("timer", {}).get("phase", "UNKNOWN"),
        "my_team": [],
        "their_team": [],
        "bans": {"my_team": [], "their_team": []},
        "my_role": "",
        "my_champion_id": 0,
        "local_player_cell_id": session.get("localPlayerCellId", -1),
    }

    local_cell = result["local_player_cell_id"]

    # Parse actions for bans
    for action_group in session.get("actions", []):
        for action in action_group:
            if action.get("type") == "ban" and action.get("completed"):
                champ_id = action.get("championId", 0)
                if champ_id > 0:
                    # Determine which team
                    actor_cell = action.get("actorCellId", -1)
                    is_ally = any(
                        p.get("cellId") == actor_cell
                        for p in session.get("myTeam", [])
                    )
                    if is_ally:
                        result["bans"]["my_team"].append(champ_id)
                    else:
                        result["bans"]["their_team"].append(champ_id)

    # Parse my team
    for player in session.get("myTeam", []):
        entry = {
            "cell_id": player.get("cellId", -1),
            "champion_id": player.get("championId", 0),
            "champion_pick_intent": player.get("championPickIntent", 0),
            "assigned_position": player.get("assignedPosition", ""),
            "is_local": player.get("cellId") == local_cell,
        }
        if entry["is_local"]:
            result["my_role"] = entry["assigned_position"]
            result["my_champion_id"] = entry["champion_id"] or entry["champion_pick_intent"]
        result["my_team"].append(entry)

    # Parse their team (limited info during draft)
    for player in session.get("theirTeam", []):
        entry = {
            "cell_id": player.get("cellId", -1),
            "champion_id": player.get("championId", 0),
            "champion_pick_intent": player.get("championPickIntent", 0),
            "assigned_position": player.get("assignedPosition", ""),
        }
        result["their_team"].append(entry)

    return result


# Singleton connection
lcu = LCUConnection()
