import json
import os
from pathlib import Path
from typing import List, Dict, Optional

from core.downloader import YouTubeDownloader

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


def add_track(
    playlist_name: str,
    url: str,
    title: str = None,
    artist: str = None,
    tags: list = None,
    duration: Optional[int] = None,
) -> Dict:
    """
    Add a track to playlist with optional auto-extraction.
    
    If title/artist not provided, attempts to extract from YouTube.
    
    Args:
        playlist_name: Playlist name
        url: YouTube URL
        title: Track title (optional, will auto-extract if None)
        artist: Artist name (optional, will auto-extract if None)
        tags: List of tags (optional)
        duration: Duration in seconds (optional, auto-extracted if None)
        
    Returns:
        Dictionary with extracted/provided metadata, or None if failed
    """
    from core.downloader import YouTubeDownloader
    
    # Auto-extract if title/artist not provided
    if not title or not artist or duration is None:
        try:
            downloader = YouTubeDownloader()
            metadata = downloader.extract_metadata(url)
            if metadata:
                title = title or metadata.get('title', 'Unknown')
                artist = artist or metadata.get('artist', 'Unknown Artist')
                duration = duration if duration is not None else metadata.get('duration')
        except Exception:
            # Fallback to defaults if extraction fails
            title = title or 'Unknown'
            artist = artist or 'Unknown Artist'
            duration = duration if duration is not None else 0
    
    # Add track
    data = load_playlist(playlist_name)
    if "tracks" not in data:
        data["tracks"] = []
    
    track = {
        "title": title,
        "artist": artist,
        "url": url,
        "tags": tags or [],
        "duration": duration if duration is not None else 0
    }
    
    data["tracks"].append(track)
    save_playlist(playlist_name, data)
    
    return track


def import_playlist_from_youtube(
    url: str,
    playlist_name: Optional[str] = None,
    overwrite: bool = False
) -> Dict:
    """
    Import all items from a YouTube playlist (metadata only).
    
    Args:
        url: YouTube playlist URL
        playlist_name: Optional name for the new playlist (defaults to yt title)
        overwrite: If True, replace existing playlist content
    
    Returns:
        Dict with summary: {name, count, added, skipped, added_items}
    """
    downloader = YouTubeDownloader()
    info = downloader.extract_playlist_items(url)

    name = playlist_name or info.get("title") or "Imported Playlist"
    # if overwrite, create empty; else load existing or new
    if overwrite or name not in list_playlists():
        create_playlist(name, description=f"Imported from {url}")
    data = load_playlist(name)
    if "tracks" not in data:
        data["tracks"] = []

    existing_urls = {t.get("url") for t in data["tracks"]}
    added = 0
    skipped = 0
    added_items = []

    for item in info.get("items", []):
        if item["url"] in existing_urls:
            skipped += 1
            continue
        track_entry = {
            "title": item.get("title", "Unknown"),
            "artist": item.get("artist", "Unknown Artist"),
            "url": item.get("url"),
            "tags": [],
            "duration": item.get("duration", 0),
        }
        data["tracks"].append(track_entry)
        added_items.append(track_entry)
        added += 1

    save_playlist(name, data)
    return {
        "name": name,
        "count": len(info.get("items", [])),
        "added": added,
        "skipped": skipped,
        "source": info.get("source_url", url),
        "added_items": added_items,
    }


def playlist_summary(name: str) -> str:
    """Return summary string for a playlist."""
    try:
        data = load_playlist(name)
        title = data.get("metadata", {}).get("name", name)
        count = len(data.get("tracks", []))
        return f"{title} ({count} tracks)"
    except Exception:
        return f"{name} (error reading)"


def delete_track(name: str, index: int) -> bool:
    """
    Delete a track from playlist by index.
    
    Args:
        name: Playlist name
        index: Track index (0-based)
        
    Returns:
        True if deleted successfully
    """
    try:
        data = load_playlist(name)
        tracks = data.get("tracks", [])
        if 0 <= index < len(tracks):
            tracks.pop(index)
            save_playlist(name, data)
            return True
        return False
    except Exception:
        return False


def list_tracks(name: str) -> List[Dict]:
    """
    Get list of tracks in a playlist.
    
    Args:
        name: Playlist name
        
    Returns:
        List of track dictionaries
    """
    try:
        data = load_playlist(name)
        return data.get("tracks", [])
    except Exception:
        return []
