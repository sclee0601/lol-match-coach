"""
Persistent storage for player ban/pick profiles.
Saves to a JSON file so data persists across server restarts.
"""

import json
import os
from pathlib import Path

STORE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STORE_FILE = STORE_DIR / "player_profiles.json"


def _ensure_dir():
    STORE_DIR.mkdir(parents=True, exist_ok=True)


def load_profiles() -> dict:
    """Load all saved profiles from disk."""
    if not STORE_FILE.exists():
        return {}
    try:
        with open(STORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_profiles(profiles: dict):
    """Save all profiles to disk."""
    _ensure_dir()
    try:
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[profile_store] Failed to save: {e}")


def get_profile(puuid: str) -> dict | None:
    """Get a single player's profile."""
    profiles = load_profiles()
    return profiles.get(puuid)


def save_profile(puuid: str, profile: dict):
    """Save/update a single player's profile."""
    profiles = load_profiles()
    profiles[puuid] = profile
    save_profiles(profiles)
