import json
import os
import re
from pathlib import Path
from typing import List, Dict, Optional

from core.downloader import YouTubeDownloader
from core.playlist_store import PLAYLIST_LOCK, read_json, write_json_atomic

PLAYLISTS_DIR = Path("playlists")

DEFAULT_SETTINGS = {"shuffle": False, "repeat": "playlist"}


def list_playlists() -> List[str]:
    """Return playlist names (without .json)."""
    PLAYLISTS_DIR.mkdir(exist_ok=True)
    return sorted([p.stem for p in PLAYLISTS_DIR.glob("*.json")])


def sanitize_filename(name: str) -> str:
    """Sanitize playlist name for use as filename (alphanumeric + space + underscore only)."""
    # Strict sanitization: Alphanumeric, space, underscore (NO hyphens for consistency)
    name = re.sub(r"[^a-zA-Z0-9 _]", "", name)
    # Strip whitespace and collapse spaces
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _get_playlist_path(name: str) -> Path:
    """
    Get path for playlist and enforce security (jail check).

    1. Sanitizes the name.
    2. Resolves path and ensures it is within PLAYLISTS_DIR.
    """
    safe_name = sanitize_filename(name)
    path = (PLAYLISTS_DIR / f"{safe_name}.json").resolve()
    root = PLAYLISTS_DIR.resolve()

    # Security check: Prevent path traversal
    if not str(path).startswith(str(root)):
        raise ValueError(
            f"Security detection: Path traversal attempt blocked for '{name}'"
        )

    return path


def load_playlist(name: str) -> Dict:
    """Load playlist JSON by name (without extension)."""
    # Use secure path resolution
    try:
        path = _get_playlist_path(name)
    except ValueError as e:
        raise FileNotFoundError(str(e))

    if not path.exists():
        raise FileNotFoundError(f"Playlist not found: {name}")
    with PLAYLIST_LOCK:
        return read_json(path)


def save_playlist(name: str, data: Dict):
    """Persist playlist JSON."""
    PLAYLISTS_DIR.mkdir(exist_ok=True)

    # Use secure path resolution
    path = _get_playlist_path(name)

    # Update metadata to match the sanitized filename used (source of truth)
    data["metadata"]["name"] = path.stem

    with PLAYLIST_LOCK:
        write_json_atomic(path, data)


def create_playlist(name: str, description: str = "", author: str = "ytbmusic"):
    """Create a new empty playlist."""
    # save_playlist handles sanitization and security
    data = {
        "version": "1.0",
        "metadata": {
            "name": name,
            "description": description,
            "author": author,
            "tags": [],
        },
        "settings": DEFAULT_SETTINGS.copy(),
        "tracks": [],
    }
    save_playlist(name, data)


def delete_playlist(name: str):
    """Delete a playlist JSON."""
    try:
        path = _get_playlist_path(name)
        with PLAYLIST_LOCK:
            if path.exists():
                path.unlink()
    except ValueError:
        pass  # Blocked path, effectively "not found" or ignored


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
                title = title or metadata.get("title", "Unknown")
                artist = artist or metadata.get("artist", "Unknown Artist")
                duration = (
                    duration if duration is not None else metadata.get("duration")
                )
        except Exception:
            # Fallback to defaults if extraction fails
            title = title or "Unknown"
            artist = artist or "Unknown Artist"
            duration = duration if duration is not None else 0

    # Add track (atomic read-modify-write under lock)
    with PLAYLIST_LOCK:
        data = load_playlist(playlist_name)
        if "tracks" not in data:
            data["tracks"] = []

        track = {
            "title": title,
            "artist": artist,
            "url": url,
            "tags": tags or [],
            "duration": duration if duration is not None else 0,
        }

        data["tracks"].append(track)
        save_playlist(playlist_name, data)

    return track


MAX_PLAYLIST_TRACKS = 30  # Limit to prevent huge downloads


def import_playlist_from_youtube(
    url: str,
    playlist_name: Optional[str] = None,
    overwrite: bool = False,
    max_tracks: int = MAX_PLAYLIST_TRACKS,
) -> Dict:
    """
    Import all items from a YouTube playlist (metadata only).

    Args:
        url: YouTube playlist URL
        playlist_name: Optional name for the new playlist (defaults to yt title)
        overwrite: If True, replace existing playlist content
        max_tracks: Maximum number of tracks to import (default: 30)

    Returns:
        Dict with summary: {name, count, added, skipped, added_items, truncated}
    """
    downloader = YouTubeDownloader()
    info = downloader.extract_playlist_items(url)

    name = playlist_name or info.get("title") or "Imported Playlist"
    name = sanitize_filename(name)

    added = 0
    skipped = 0
    added_items = []
    truncated = False

    items = info.get("items", [])
    original_count = len(items)

    # Apply track limit
    if len(items) > max_tracks:
        items = items[:max_tracks]
        truncated = True

    # Atomic file operations under lock (avoid corruption with concurrent rename/delete/import)
    with PLAYLIST_LOCK:
        pl_path = PLAYLISTS_DIR / f"{name}.json"
        # if overwrite, create empty; else load existing or new
        if overwrite or not pl_path.exists():
            create_playlist(name, description=f"Imported from {url}")

        data = load_playlist(name)
        if "tracks" not in data:
            data["tracks"] = []

        existing_urls = {t.get("url") for t in data["tracks"]}

        for item in items:
            if item["url"] in existing_urls:
                skipped += 1
                continue
            # Sanitize title to alphanumeric (no special chars)
            raw_title = item.get("title", "Unknown")
            clean_title = re.sub(r"[^\w\s\-]", "", raw_title)
            clean_title = re.sub(r"\s+", " ", clean_title).strip() or "Unknown"
            track_entry = {
                "title": clean_title,
                "artist": item.get("artist", "Unknown Artist"),
                "url": item.get("url"),
                "tags": [],
                "duration": item.get("duration", 0),
            }
            # Add chapter timing if available (for single video → playlist conversion)
            if "start_time" in item:
                track_entry["start_time"] = item["start_time"]
            if "end_time" in item:
                track_entry["end_time"] = item["end_time"]
            data["tracks"].append(track_entry)
            added_items.append(track_entry)
            added += 1

        save_playlist(name, data)
    return {
        "name": name,
        "count": original_count,
        "added": added,
        "skipped": skipped,
        "source": info.get("source_url", url),
        "added_items": added_items,
        "truncated": truncated,
        "max_tracks": max_tracks,
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
        with PLAYLIST_LOCK:
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


def get_missing_tracks(playlist_name: str) -> List[Dict]:
    """
    Identify tracks in a playlist that are not yet downloaded/cached.

    Args:
        playlist_name: Name of the playlist

    Returns:
        List of track dictionaries that need downloading
    """
    from core.downloader import YouTubeDownloader

    try:
        data = load_playlist(playlist_name)
        tracks = data.get("tracks", [])
        if not tracks:
            return []

        downloader = YouTubeDownloader()
        missing = []

        for track in tracks:
            url = track.get("url")
            title = track.get("title")
            artist = track.get("artist")
            # Skip unplayable tracks (deleted/private/unavailable)
            if track.get("is_playable") is False:
                continue
            if url and not downloader.is_cached(url, title=title, artist=artist):
                missing.append(track)

        return missing
    except Exception:
        return []
