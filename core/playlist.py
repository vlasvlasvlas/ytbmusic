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

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class Playlist:
    """Manages a playlist of tracks."""

    def __init__(self):
        self.metadata = {}
        self.settings = {}
        self.tracks: List[Track] = []
        self.current_index = 0
        self.shuffle_enabled = False
        self.repeat_mode = RepeatMode.PLAYLIST
        self._original_order = []
        self._shuffle_order = []

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
            )
            self.tracks.append(track)

        # Setup shuffle
        self._original_order = list(range(len(self.tracks)))
        if self.shuffle_enabled:
            self._create_shuffle_order()

    def _create_shuffle_order(self):
        """Create a shuffled order of track indices."""
        self._shuffle_order = self._original_order.copy()
        random.shuffle(self._shuffle_order)

    def get_current_track(self) -> Optional[Track]:
        """Get the current track."""
        if not self.tracks:
            return None

        if self.shuffle_enabled and self._shuffle_order:
            actual_index = self._shuffle_order[self.current_index]
        else:
            actual_index = self.current_index

        return self.tracks[actual_index]

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
        Jump to specific track index.

        Args:
            index: Track index (0-based)

        Returns:
            Track at index or None if invalid
        """
        if 0 <= index < len(self.tracks):
            self.current_index = index
            return self.get_current_track()
        return None

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
        self.current_playlist = Playlist.from_file(str(filepath))
        return self.current_playlist

    def get_current(self) -> Optional[Playlist]:
        """Get current playlist."""
        return self.current_playlist


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
