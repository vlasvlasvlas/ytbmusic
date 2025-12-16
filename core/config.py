"""
Configuration and State Management

Handles loading/saving config and persistent application state.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import os
import threading
import time


class ConfigManager:
    """Manages application configuration and persistent state."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

        self.config_file = self.config_dir / "default_config.json"
        self.state_file = self.config_dir / "state.json"
        self.keybindings_file = self.config_dir / "keybindings.json"

        self.config = {}
        self.state = {}
        self.keybindings = {}

        self._auto_save_thread = None
        self._auto_save_running = False

        # Load everything
        self.load_config()
        self.load_state()
        self.load_keybindings()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if self.config_file.exists():
            with open(self.config_file, "r") as f:
                self.config = json.load(f)
        else:
            # Create default config
            self.config = self._get_default_config()
            self.save_config()

        return self.config

    def save_config(self):
        """Save configuration to file."""
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    def load_state(self) -> Dict[str, Any]:
        """Load persistent state from file."""
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
        else:
            # Create default state
            self.state = self._get_default_state()
            self.save_state()

        return self.state

    def save_state(self):
        """Save persistent state to file."""
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def load_keybindings(self) -> Dict[str, str]:
        """Load keybindings from file."""
        if self.keybindings_file.exists():
            with open(self.keybindings_file, "r") as f:
                self.keybindings = json.load(f)
        else:
            # Create default keybindings
            self.keybindings = self._get_default_keybindings()
            self.save_keybindings()

        return self.keybindings

    def save_keybindings(self):
        """Save keybindings to file."""
        with open(self.keybindings_file, "w") as f:
            json.dump(self.keybindings, f, indent=2)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "playback": {
                "mode": "hybrid",
                "volume": 75,
                "repeat": "playlist",
                "shuffle": False,
            },
            "cache": {
                "enabled": True,
                "max_size_gb": 5,
                "location": "./cache",
                "prefetch_count": 2,
                "auto_cleanup": True,
            },
            "ui": {
                "default_skin": "cassette",
                "color_support": True,
                "show_next_track": True,
            },
            "logging": {
                "enabled": True,
                "log_playback": True,
                "log_errors": True,
                "log_statistics": True,
            },
            "auto_save": {"enabled": True, "interval_seconds": 10},
        }

    def _get_default_state(self) -> Dict[str, Any]:
        """Get default state."""
        return {
            "last_playlist": None,
            "last_playlist_name": None,
            "last_track_index": 0,
            "last_position": 0.0,
            "last_skin": "cassette",
            "last_volume": 75,
            "session_count": 0,
            "total_playtime_seconds": 0,
            "last_updated": time.time(),
        }

    def _get_default_keybindings(self) -> Dict[str, str]:
        """Get default keybindings."""
        return {
            "play_pause": "space",
            "next": "n",
            "previous": "p",
            "volume_up": "+",
            "volume_down": "-",
            "seek_forward": "right",
            "seek_backward": "left",
            "jump_forward": "]",
            "jump_backward": "[",
            "playlist_browser": "l",
            "skin_selector": "s",
            "queue_view": "q",
            "help": "?",
            "shuffle": "z",
            "repeat": "r",
            "quit": "q",
            "mute": "m",
        }

    # Configuration getters
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key (e.g., 'playback.volume')."""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """Set config value by dot-notation key."""
        keys = key.split(".")
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
        self.save_config()

    # State management
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state value."""
        return self.state.get(key, default)

    def set_state(self, key: str, value: Any):
        """Set state value."""
        self.state[key] = value
        self.state["last_updated"] = time.time()

    def update_state(self, **kwargs):
        """Update multiple state values at once."""
        for key, value in kwargs.items():
            self.state[key] = value
        self.state["last_updated"] = time.time()

    # Auto-save functionality
    def start_auto_save(self, interval: Optional[int] = None):
        """Start auto-save thread."""
        if self._auto_save_running:
            return

        if interval is None:
            interval = self.get("auto_save.interval_seconds", 10)

        self._auto_save_running = True
        self._auto_save_thread = threading.Thread(
            target=self._auto_save_loop, args=(interval,), daemon=True
        )
        self._auto_save_thread.start()

    def stop_auto_save(self):
        """Stop auto-save thread."""
        self._auto_save_running = False
        if self._auto_save_thread:
            self._auto_save_thread.join(timeout=2)

    def _auto_save_loop(self, interval: int):
        """Auto-save loop running in background."""
        while self._auto_save_running:
            time.sleep(interval)
            if self._auto_save_running:
                self.save_state()

    # Keybinding helpers
    def get_key_for_action(self, action: str) -> Optional[str]:
        """Get the key bound to an action."""
        return self.keybindings.get(action)

    def get_action_for_key(self, key: str) -> Optional[str]:
        """Get the action bound to a key."""
        for action, bound_key in self.keybindings.items():
            if bound_key == key:
                return action
        return None

    # Session management
    def start_session(self):
        """Start a new session."""
        self.state["session_count"] = self.state.get("session_count", 0) + 1
        self.state["session_start_time"] = time.time()
        self.save_state()

    def end_session(self):
        """End current session."""
        if "session_start_time" in self.state:
            session_duration = time.time() - self.state["session_start_time"]
            total_playtime = self.state.get("total_playtime_seconds", 0)
            self.state["total_playtime_seconds"] = total_playtime + session_duration
            del self.state["session_start_time"]

        self.save_state()

    # Convenience methods for common operations
    def save_playback_state(
        self, playlist_path: str, playlist_name: str, track_index: int, position: float
    ):
        """Save current playback state for resume."""
        self.update_state(
            last_playlist=playlist_path,
            last_playlist_name=playlist_name,
            last_track_index=track_index,
            last_position=position,
        )

    def get_resume_info(self) -> Optional[Dict[str, Any]]:
        """Get info to resume last session."""
        if self.state.get("last_playlist"):
            return {
                "playlist": self.state["last_playlist"],
                "playlist_name": self.state["last_playlist_name"],
                "track_index": self.state.get("last_track_index", 0),
                "position": self.state.get("last_position", 0.0),
            }
        return None

    def clear_resume_info(self):
        """Clear resume information."""
        self.update_state(
            last_playlist=None,
            last_playlist_name=None,
            last_track_index=0,
            last_position=0.0,
        )


if __name__ == "__main__":
    # Test the config manager
    config = ConfigManager()

    print("📋 Current Config:")
    print(f"  Volume: {config.get('playback.volume')}")
    print(f"  Default Skin: {config.get('ui.default_skin')}")

    print("\n💾 Current State:")
    print(f"  Last Playlist: {config.get_state('last_playlist_name', 'None')}")
    print(f"  Session Count: {config.get_state('session_count', 0)}")
    print(f"  Total Playtime: {config.get_state('total_playtime_seconds', 0)}s")

    print("\n⌨️  Keybindings:")
    print(f"  Play/Pause: {config.get_key_for_action('play_pause')}")
    print(f"  Next: {config.get_key_for_action('next')}")
    print(f"  Quit: {config.get_key_for_action('quit')}")
