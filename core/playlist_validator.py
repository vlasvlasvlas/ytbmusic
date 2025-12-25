"""
Playlist Validator

Startup health check system for playlists:
- Validates JSON syntax
- Removes duplicate tracks (by URL)
- Sanitizes titles (alphanumeric)
- Syncs is_playable flags with cache
"""

import json
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger("PlaylistValidator")


@dataclass
class ValidationResult:
    playlist_name: str
    is_valid: bool = True
    duplicates_removed: int = 0
    titles_cleaned: int = 0
    playable_synced: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    playlists_checked: int = 0
    playlists_fixed: int = 0
    total_duplicates_removed: int = 0
    total_titles_cleaned: int = 0
    total_playable_synced: int = 0
    results: List[ValidationResult] = field(default_factory=list)

    def summary(self) -> str:
        if not self.playlists_fixed:
            return f"✓ {self.playlists_checked} playlists validated (no issues)"
        return (
            f"✓ {self.playlists_checked} playlists validated, "
            f"{self.playlists_fixed} fixed: "
            f"{self.total_duplicates_removed} dupes, "
            f"{self.total_titles_cleaned} titles, "
            f"{self.total_playable_synced} synced"
        )


class PlaylistValidator:
    """Validates and repairs playlist JSON files."""

    def __init__(self, playlists_dir: str = "playlists", cache_dir: str = "cache"):
        self.playlists_dir = Path(playlists_dir)
        self.cache_dir = Path(cache_dir)

    def validate_all(self, auto_fix: bool = True) -> ValidationReport:
        """Validate all playlists and optionally auto-fix issues."""
        report = ValidationReport()

        for pl_file in self.playlists_dir.glob("*.json"):
            result = self.validate_playlist(pl_file.stem, auto_fix=auto_fix)
            report.results.append(result)
            report.playlists_checked += 1

            if (
                result.duplicates_removed
                or result.titles_cleaned
                or result.playable_synced
            ):
                report.playlists_fixed += 1
                report.total_duplicates_removed += result.duplicates_removed
                report.total_titles_cleaned += result.titles_cleaned
                report.total_playable_synced += result.playable_synced

        return report

    def validate_playlist(self, name: str, auto_fix: bool = True) -> ValidationResult:
        """Validate a single playlist."""
        result = ValidationResult(playlist_name=name)
        pl_path = self.playlists_dir / f"{name}.json"

        if not pl_path.exists():
            result.is_valid = False
            result.errors.append("File not found")
            return result

        try:
            with open(pl_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result.is_valid = False
            result.errors.append(f"Invalid JSON: {e}")
            return result

        tracks = data.get("tracks", [])
        modified = False

        # 1. Remove duplicates (by URL)
        seen_urls = set()
        unique_tracks = []
        for track in tracks:
            url = track.get("url", "")
            if url and url in seen_urls:
                result.duplicates_removed += 1
                continue
            if url:
                seen_urls.add(url)
            unique_tracks.append(track)

        if result.duplicates_removed:
            data["tracks"] = unique_tracks
            tracks = unique_tracks
            modified = True

        # 2. Sanitize titles
        for track in tracks:
            old_title = track.get("title", "")
            new_title = self._sanitize_title(old_title)
            if old_title != new_title:
                track["title"] = new_title
                result.titles_cleaned += 1
                modified = True

        # 3. Sync is_playable with cache
        for track in tracks:
            url = track.get("url", "")
            title = track.get("title", "")
            artist = track.get("artist", "")

            cached = self._is_cached(url, title, artist)
            current_playable = track.get("is_playable", True)

            # If cached, should be playable (unless marked otherwise for other reasons)
            if cached and current_playable is False and "error_msg" in track:
                # Has cache but marked unplayable - check if it's a stale flag
                if "unavailable" in track.get("error_msg", "").lower():
                    # Was unavailable but now cached - update
                    del track["is_playable"]
                    if "error_msg" in track:
                        del track["error_msg"]
                    result.playable_synced += 1
                    modified = True

        # Save if modified
        if modified and auto_fix:
            try:
                with open(pl_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info(f"Fixed playlist: {name}")
            except Exception as e:
                result.errors.append(f"Failed to save: {e}")

        return result

    def _sanitize_title(self, title: str) -> str:
        """Sanitize title to alphanumeric + spaces + hyphens."""
        clean = re.sub(r"[^\w\s\-]", "", title)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _is_cached(self, url: str, title: str, artist: str) -> bool:
        """Check if track is cached (simplified check)."""
        if not url or not self.cache_dir.exists():
            return False

        # Extract video ID
        video_id = None
        if "v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]

        # Check by video ID
        if video_id:
            if (self.cache_dir / f"{video_id}.m4a").exists():
                return True

        # Check by title pattern
        if title:
            title_core = re.sub(r"[^a-zA-Z0-9]", "", title)[:20].lower()
            for f in self.cache_dir.glob("*.m4a"):
                if title_core in f.stem.lower():
                    return True

        return False


def run_validation(auto_fix: bool = True) -> ValidationReport:
    """Run full playlist validation."""
    validator = PlaylistValidator()
    return validator.validate_all(auto_fix=auto_fix)


if __name__ == "__main__":
    # CLI usage
    report = run_validation()
    print(report.summary())
    for r in report.results:
        if r.duplicates_removed or r.titles_cleaned or r.playable_synced or r.errors:
            print(
                f"  {r.playlist_name}: dupes={r.duplicates_removed}, titles={r.titles_cleaned}, synced={r.playable_synced}"
            )
