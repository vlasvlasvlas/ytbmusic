import json
import os
from pathlib import Path
from typing import List, Dict, Optional


PLAYLISTS_DIR = Path("playlists")

DEFAULT_SETTINGS = {
    "shuffle": False,
    "repeat": "playlist"
}


def list_playlists() -> List[str]:
    """Return playlist names (without .json)."""
    PLAYLISTS_DIR.mkdir(exist_ok=True)
    return sorted([p.stem for p in PLAYLISTS_DIR.glob("*.json")])


def load_playlist(name: str) -> Dict:
    """Load playlist JSON by name (without extension)."""
    path = PLAYLISTS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Playlist not found: {name}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_playlist(name: str, data: Dict):
    """Persist playlist JSON."""
    PLAYLISTS_DIR.mkdir(exist_ok=True)
    path = PLAYLISTS_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_playlist(name: str, description: str = "", author: str = "ytbmusic"):
    """Create a new empty playlist."""
    data = {
        "version": "1.0",
        "metadata": {
            "name": name,
            "description": description,
            "author": author,
            "tags": []
        },
        "settings": DEFAULT_SETTINGS.copy(),
        "tracks": []
    }
    save_playlist(name, data)


def delete_playlist(name: str):
    """Delete a playlist JSON."""
    path = PLAYLISTS_DIR / f"{name}.json"
    if path.exists():
        path.unlink()


def add_track(name: str, title: str, artist: str, url: str):
    """Append a track to a playlist."""
    data = load_playlist(name)
    if "tracks" not in data:
        data["tracks"] = []
    data["tracks"].append(
        {
            "title": title or "Untitled",
            "artist": artist or "Unknown Artist",
            "url": url,
            "tags": []
        }
    )
    save_playlist(name, data)


def playlist_summary(name: str) -> str:
    """Return summary string for a playlist."""
    try:
        data = load_playlist(name)
        title = data.get("metadata", {}).get("name", name)
        count = len(data.get("tracks", []))
        return f"{title} ({count} tracks)"
    except Exception:
        return f"{name} (error reading)"

