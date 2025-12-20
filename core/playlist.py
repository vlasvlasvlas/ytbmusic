"""
Playlist Management

Handles loading, parsing, and navigating JSON playlists.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import random

from core.playlist_store import PLAYLIST_LOCK, read_json, write_json_atomic


class RepeatMode(Enum):
    """Repeat mode options."""

    NONE = "none"
    TRACK = "track"
    PLAYLIST = "playlist"


@dataclass
class Track:
    """Represents a single track."""

    title: str
    artist: str
    url: str
    duration: int = 0
    tags: List[str] = None
    is_playable: bool = True
    error_msg: Optional[str] = None
    start_time: float = 0.0
    end_time: Optional[float] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class Playlist:
    """Manages a playlist of tracks."""

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tracks: Optional[List[Track]] = None,
        settings: Optional[Dict] = None,
    ):
        # Metadata and settings
        self.metadata = {}
        if name is not None:
            self.metadata["name"] = name
        if description is not None:
            self.metadata["description"] = description

        self.settings = settings.copy() if settings else {}

        # Core state
        self.tracks: List[Track] = list(tracks) if tracks else []
        self.current_index = 0
        self.shuffle_enabled = bool(self.settings.get("shuffle", False))

        repeat_setting = self.settings.get("repeat", RepeatMode.PLAYLIST.value)
        try:
            self.repeat_mode = RepeatMode(repeat_setting)
        except Exception:
            self.repeat_mode = RepeatMode.PLAYLIST

        # Track ordering
        self._original_order = list(range(len(self.tracks)))
        self._shuffle_order = []
        if self.shuffle_enabled and self.tracks:
            self._create_shuffle_order()

    @classmethod
    def from_file(cls, filepath: str) -> "Playlist":
        """
        Load playlist from JSON file.

        Args:
            filepath: Path to JSON playlist file

        Returns:
            Playlist instance
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Playlist not found: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        playlist = cls()
        playlist._parse_json(data)
        return playlist

    def _parse_json(self, data: Dict):
        """Parse JSON data into playlist structure."""
        # Metadata
        self.metadata = data.get("metadata", {})

        # Settings
        self.settings = data.get("settings", {})
        self.shuffle_enabled = self.settings.get("shuffle", False)

        repeat_str = self.settings.get("repeat", "playlist")
        try:
            self.repeat_mode = RepeatMode(repeat_str)
        except Exception:
            self.repeat_mode = RepeatMode.PLAYLIST

        # Tracks
        tracks_data = data.get("tracks", [])
        for track_data in tracks_data:
            track = Track(
                title=track_data.get("title", "Unknown"),
                artist=track_data.get("artist", "Unknown Artist"),
                url=track_data["url"],
                duration=track_data.get("duration", 0),
                tags=track_data.get("tags", []),
                is_playable=track_data.get("is_playable", True),
                error_msg=track_data.get("error_msg"),
                start_time=track_data.get("start_time", 0.0),
                end_time=track_data.get("end_time"),
            )
            self.tracks.append(track)

        # Setup shuffle
        self._original_order = list(range(len(self.tracks)))
        if self.shuffle_enabled:
            self._create_shuffle_order()

    def to_dict(self) -> Dict:
        """Convert playlist to a dictionary suitable for JSON serialization."""
        tracks_data = []
        for track in self.tracks:
            track_dict = {
                "title": track.title,
                "artist": track.artist,
                "url": track.url,
                "duration": track.duration,
                "tags": track.tags,
                "is_playable": track.is_playable,
                "start_time": track.start_time,
                "end_time": track.end_time,
            }
            if track.error_msg:
                track_dict["error_msg"] = track.error_msg
            tracks_data.append(track_dict)

        settings_data = self.settings.copy()
        settings_data["shuffle"] = self.shuffle_enabled
        settings_data["repeat"] = self.repeat_mode.value

        return {
            "metadata": self.metadata,
            "settings": settings_data,
            "tracks": tracks_data,
        }

    def save_to_file(self, filepath: str):
        """Save playlist to a JSON file."""
        path = Path(filepath)
        with PLAYLIST_LOCK:
            write_json_atomic(path, self.to_dict())

    def _create_shuffle_order(self):
        """Create a shuffled order of track indices."""
        self._shuffle_order = self._original_order.copy()
        random.shuffle(self._shuffle_order)

    def get_track(self, index: int) -> Optional[Track]:
        """Get track by index, or None if out of bounds."""
        if 0 <= index < len(self.tracks):
            return self.tracks[index]
        return None

    def get_current_track(self) -> Optional[Track]:
        """Get the current track."""
        if not self.tracks:
            return None

        original_idx = self.current_index  # Store original index to detect full loop

        if self.shuffle_enabled and self._shuffle_order:
            # Skip unplayable tracks in shuffle
            while True:
                if (
                    not self._shuffle_order
                ):  # Handle empty shuffle order if tracks were removed
                    return None
                real_idx = self._shuffle_order[self.current_index]
                if self.tracks[real_idx].is_playable:
                    return self.tracks[real_idx]

                # If unplayable, move to next and prevent infinite loop if all are bad
                self.current_index = (self.current_index + 1) % len(self.tracks)
                if self.current_index == original_idx:
                    return None  # All unplayable
        else:
            # Skip unplayable tracks in linear order
            attempts = 0
            while attempts < len(self.tracks):
                track = self.tracks[self.current_index]
                if track.is_playable:
                    return track
                self.current_index = (self.current_index + 1) % len(self.tracks)
                attempts += 1
            return None

    def next(self) -> Optional[Track]:
        """
        Move to next track.

        Returns:
            Next track or None if at end (and repeat is off)
        """
        if not self.tracks:
            return None

        # If repeat track, stay on same track
        if self.repeat_mode == RepeatMode.TRACK:
            return self.get_current_track()

        # Move to next
        self.current_index += 1

        # Check if we've reached the end
        if self.current_index >= len(self.tracks):
            if self.repeat_mode == RepeatMode.PLAYLIST:
                self.current_index = 0
                # If shuffle, create new shuffle order
                if self.shuffle_enabled:
                    self._create_shuffle_order()
            else:
                # No repeat, return None
                return None

        return self.get_current_track()

    def previous(self) -> Optional[Track]:
        """
        Move to previous track.

        Returns:
            Previous track
        """
        if not self.tracks:
            return None

        self.current_index -= 1

        if self.current_index < 0:
            if self.repeat_mode == RepeatMode.PLAYLIST:
                self.current_index = len(self.tracks) - 1
            else:
                self.current_index = 0

        return self.get_current_track()

    def jump_to(self, index: int) -> Optional[Track]:
        """
        Jump to specific track index (logical index/position in queue).

        Args:
            index: Queue position (0-based)
        """
        if 0 <= index < len(self.tracks):
            self.current_index = index
            return self.get_current_track()
        return None

    def set_position_by_original_index(self, original_index: int) -> Optional[Track]:
        """
        Jump to a specific track by its original index in the tracks list.
        Useful when clicking a track in the UI list.

        Args:
           original_index: Index in the .tracks list
        """
        if not (0 <= original_index < len(self.tracks)):
            return None

        if self.shuffle_enabled and self._shuffle_order:
            # Find which position in the shuffled queue points to this track
            try:
                queue_pos = self._shuffle_order.index(original_index)
                self.current_index = queue_pos
            except ValueError:
                # Should not happen
                self.current_index = original_index
        else:
            self.current_index = original_index

        return self.get_current_track()

    def peek_next(self) -> Optional[Track]:
        """
        Return the next track without changing position.
        """
        if not self.tracks:
            return None

        if self.repeat_mode == RepeatMode.TRACK:
            return self.get_current_track()

        next_idx = self.current_index + 1
        if next_idx >= len(self.tracks):
            if self.repeat_mode == RepeatMode.PLAYLIST:
                next_idx = 0
            else:
                return None

        # Resolve actual index (shuffle vs normal)
        if self.shuffle_enabled and self._shuffle_order:
            actual_index = self._shuffle_order[next_idx]
        else:
            actual_index = next_idx

        return self.tracks[actual_index]

    def toggle_shuffle(self):
        """Toggle shuffle mode."""
        self.shuffle_enabled = not self.shuffle_enabled
        if self.shuffle_enabled:
            self._create_shuffle_order()

    def set_repeat_mode(self, mode: RepeatMode):
        """Set repeat mode."""
        self.repeat_mode = mode

    def cycle_repeat_mode(self):
        """Cycle through repeat modes."""
        modes = [RepeatMode.NONE, RepeatMode.TRACK, RepeatMode.PLAYLIST]
        current_idx = modes.index(self.repeat_mode)
        next_idx = (current_idx + 1) % len(modes)
        self.repeat_mode = modes[next_idx]

    def get_name(self) -> str:
        """Get playlist name."""
        return self.metadata.get("name", "Untitled Playlist")

    def get_description(self) -> str:
        """Get playlist description."""
        return self.metadata.get("description", "")

    def get_track_count(self) -> int:
        """Get number of tracks."""
        return len(self.tracks)

    def get_position_info(self) -> str:
        """Get current position as string (e.g., '5/12')."""
        if not self.tracks:
            return "0/0"
        return f"{self.current_index + 1}/{len(self.tracks)}"


class PlaylistManager:
    """Manages multiple playlists."""

    def __init__(self, playlists_dir: str = "playlists"):
        self.playlists_dir = Path(playlists_dir)
        self.playlists_dir.mkdir(exist_ok=True)
        self.current_playlist: Optional[Playlist] = None

    def list_playlists(self) -> List[str]:
        """List all available playlist files."""
        return [f.stem for f in self.playlists_dir.glob("*.json")]

    def load_playlist(self, name: str) -> Playlist:
        """
        Load a playlist by name.

        Args:
            name: Playlist name (without .json extension)

        Returns:
            Loaded playlist
        """
        filepath = self.playlists_dir / f"{name}.json"
        with PLAYLIST_LOCK:
            self.current_playlist = Playlist.from_file(str(filepath))
        return self.current_playlist

    def get_current(self) -> Optional[Playlist]:
        """Get current playlist."""
        return self.current_playlist

    def rename_playlist(self, old_name: str, new_name: str) -> None:
        """
        Rename a playlist file and update its internal metadata.

        Args:
            old_name: Current playlist name (stem)
            new_name: New playlist name (stem)

        Raises:
            FileNotFoundError: If old name not found
            FileExistsError: If new name already exists
            ValueError: If new name is invalid
        """
        if not new_name or not new_name.strip():
            raise ValueError("New name cannot be empty")

        old_path = self.playlists_dir / f"{old_name}.json"
        new_path = self.playlists_dir / f"{new_name}.json"

        if not old_path.exists():
            raise FileNotFoundError(f"Playlist '{old_name}' not found")

        if new_path.exists():
            raise FileExistsError(f"Playlist '{new_name}' already exists")

        try:
            with PLAYLIST_LOCK:
                data = read_json(old_path)
                if "metadata" not in data:
                    data["metadata"] = {}
                data["metadata"]["name"] = new_name

                # Write new file atomically, then remove old (atomic write avoids partial JSON)
                write_json_atomic(new_path, data)
                try:
                    old_path.unlink()
                except FileNotFoundError:
                    pass

                # Update current if needed
                if (
                    self.current_playlist
                    and self.current_playlist.get_name() == old_name
                ):
                    self.current_playlist.metadata["name"] = new_name
        except Exception as e:
            raise Exception(f"Failed to rename playlist: {e}")

    def mark_track_unplayable(
        self, playlist_name: str, url: str, reason: Optional[str] = None
    ) -> bool:
        """
        Persist a track as unplayable so playback and downloads can skip it.

        Returns True if a track was updated.
        """
        if not playlist_name or not url:
            return False

        path = self.playlists_dir / f"{playlist_name}.json"
        if not path.exists():
            return False

        updated = False
        with PLAYLIST_LOCK:
            data = read_json(path)
            tracks = data.get("tracks", [])
            for t in tracks:
                if t.get("url") == url:
                    t["is_playable"] = False
                    if reason:
                        t["error_msg"] = reason
                    updated = True
                    break
            if updated:
                write_json_atomic(path, data)

        # Keep in-memory current playlist consistent
        if (
            updated
            and self.current_playlist
            and self.current_playlist.metadata.get("name") == playlist_name
        ):
            for tr in self.current_playlist.tracks:
                if tr.url == url:
                    tr.is_playable = False
                    tr.error_msg = reason
                    break

        return updated


if __name__ == "__main__":
    # Test the playlist manager
    manager = PlaylistManager()

    print("Available playlists:")
    for name in manager.list_playlists():
        print(f"  - {name}")

    if manager.list_playlists():
        # Load first playlist
        first = manager.list_playlists()[0]
        print(f"\nLoading: {first}")

        playlist = manager.load_playlist(first)
        print(f"Name: {playlist.get_name()}")
        print(f"Tracks: {playlist.get_track_count()}")

        # Show current track
        track = playlist.get_current_track()
        if track:
            print(f"\nCurrent: {track.title} - {track.artist}")
            print(f"URL: {track.url}")
