#!/usr/bin/env python3
"""
Rename existing cache files from video_id.m4a to artist_title.m4a
"""
import json
import re
from pathlib import Path


def make_safe_filename(title, artist=None):
    """Create a safe filename from artist and title (alphanumeric + underscore only)."""
    # Combine artist and title
    if artist and artist != "Unknown Artist":
        name = f"{artist}__SEP__{title}"
    else:
        name = title

    # Keep only alphanumeric, spaces, and underscore
    name = re.sub(r"[^a-zA-Z0-9\s_]", "", name)

    # Replace separator
    name = name.replace("__SEP__", "_")

    # Replace spaces with underscores
    name = re.sub(r"\s+", "_", name)

    # Cleanup multiple underscores
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")

    # Limit length
    if len(name) > 80:
        name = name[:80]

    return name


def extract_video_id(url):
    """Extract video ID from YouTube URL."""
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None


def make_legacy_filename(title, artist=None):
    """Create the previous intermediate filename (with spaces)."""
    if artist and artist != "Unknown Artist":
        name = f"{artist} - {title}"
    else:
        name = title

    # Remove/replace unsafe characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = name.replace("\n", " ").replace("\r", "")
    name = name.strip()
    if len(name) > 100:
        name = name[:100]
    return name


def main():
    cache_dir = Path("cache")
    playlists_dir = Path("playlists")

    if not cache_dir.exists():
        print("No cache directory found")
        return

    # Build mapping: video_id -> (title, artist)
    id_to_metadata = {}

    for pl_file in playlists_dir.glob("*.json"):
        try:
            with open(pl_file, "r") as f:
                data = json.load(f)

            for track in data.get("tracks", []):
                url = track.get("url", "")
                video_id = extract_video_id(url)
                if video_id:
                    id_to_metadata[video_id] = {
                        "title": track.get("title", "Unknown"),
                        "artist": track.get("artist", ""),
                    }
        except Exception as e:
            print(f"Error reading {pl_file}: {e}")

    print(f"Found {len(id_to_metadata)} tracks in playlists")

    # processed_files = set()
    renamed = 0

    for video_id, meta in id_to_metadata.items():
        title = meta["title"]
        artist = meta["artist"]

        target_name = make_safe_filename(title, artist)
        target_path = cache_dir / f"{target_name}.m4a"

        if target_path.exists():
            continue

        # Check for legacy format (Artist - Title)
        legacy_name = make_legacy_filename(title, artist)
        legacy_path = cache_dir / f"{legacy_name}.m4a"

        # Check for original format (video_id)
        original_path = cache_dir / f"{video_id}.m4a"

        source_path = None
        if legacy_path.exists():
            source_path = legacy_path
            print(f"FOUND LEGACY: {legacy_path.name}")
        elif original_path.exists():
            source_path = original_path
            print(f"FOUND ORIGINAL: {original_path.name}")

        if source_path:
            print(f"RENAME: {source_path.name} -> {target_path.name}")
            try:
                source_path.rename(target_path)
                renamed += 1
            except Exception as e:
                print(f"Error renaming: {e}")

    print(f"\nRenamed {renamed} files")


if __name__ == "__main__":
    main()
