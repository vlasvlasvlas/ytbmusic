"""
Music Player Engine using VLC (python-vlc binding).
"""

import logging
import time
from enum import Enum
from pathlib import Path
from typing import Dict

import vlc
from core.logger import setup_logging

logger = logging.getLogger("MusicPlayer")


class PlayerState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class MusicPlayer:
    """Music player using VLC."""

    def __init__(self):
        logger.info("Initializing MusicPlayer with VLC backend")
        self.state = PlayerState.STOPPED
        # Keep volume in sync with VLC from the start to avoid jumps on first keypress
        self.volume = 100
        self.current_url = None
        self.on_end_callback = None

        self._instance = vlc.Instance("--no-video", "--quiet", "--intf", "dummy")
        self._player = self._instance.media_player_new()
        self.set_volume(self.volume)

        # Register end-of-media event
        self._event_mgr = self._player.event_manager()
        self._event_mgr.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end)

    def get_backend_version(self) -> str:
        """Return libVLC version string if available."""
        try:
            return vlc.libvlc_get_version() or ""
        except Exception:
            return ""

    def _on_end(self, event):
        logger.info("End of media reached")
        self.state = PlayerState.STOPPED
        if self.on_end_callback:
            self.on_end_callback()

    def play(self, source: str, start_time: float = 0.0, end_time: float = None):
        """Play audio from URL or file path."""
        self.stop()
        self.current_url = source
        logger.info(f"Playing: {source[:80]}... (Start: {start_time}, End: {end_time})")

        # Configure VLC media options for start/end time
        options = []
        if start_time > 0:
            options.append(f"start-time={start_time}")
        if end_time:
            options.append(f"stop-time={end_time}")

        media = self._instance.media_new(source, *options)
        self._player.set_media(media)
        self._player.play()
        self.state = PlayerState.PLAYING
        self.set_volume(self.volume)

    def pause(self):
        if self.state == PlayerState.PLAYING:
            self._player.set_pause(True)
            self.state = PlayerState.PAUSED

    def resume(self):
        if self.state == PlayerState.PAUSED:
            self._player.set_pause(False)
            self.state = PlayerState.PLAYING

    def toggle_pause(self):
        if self.state == PlayerState.PLAYING:
            self.pause()
        elif self.state == PlayerState.PAUSED:
            self.resume()

    def stop(self):
        try:
            self._player.stop()
        except Exception:
            pass
        self.state = PlayerState.STOPPED

    def seek(self, seconds: float, relative: bool = True):
        try:
            if relative:
                current = self._player.get_time() or 0
                target = max(0, current + int(seconds * 1000))
                self._player.set_time(target)
            else:
                self._player.set_time(int(seconds * 1000))
        except Exception as e:
            logger.debug(f"Seek failed: {e}")

    def set_volume(self, level: int):
        self.volume = max(0, min(100, level))
        try:
            self._player.audio_set_volume(self.volume)
        except Exception:
            pass

    def volume_up(self, step: int = 5):
        self.set_volume(self.volume + step)

    def volume_down(self, step: int = 5):
        self.set_volume(self.volume - step)

    def get_time_info(self) -> Dict[str, any]:
        current_ms = self._player.get_time() or 0
        total_ms = self._player.get_length() or 0
        percentage = 0
        if total_ms > 0:
            percentage = (current_ms / total_ms) * 100
        return {
            "current_time": current_ms / 1000.0,
            "total_duration": total_ms / 1000.0,
            "percentage": percentage,
            "current_formatted": self._format_time(current_ms / 1000.0),
            "total_formatted": self._format_time(total_ms / 1000.0),
        }

    def _format_time(self, seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def is_playing(self) -> bool:
        return self.state == PlayerState.PLAYING

    def is_paused(self) -> bool:
        return self.state == PlayerState.PAUSED

    def cleanup(self):
        try:
            self.stop()
        except Exception:
            pass
        try:
            self._player.release()
        except Exception:
            pass
        try:
            self._instance.release()
        except Exception:
            pass


if __name__ == "__main__":
    player = MusicPlayer()
    url = "https://www.youtube.com/watch?v=jfKfPfyJRdk"
    print("Playing:", url)
    player.play(url)
    try:
        while player.is_playing():
            info = player.get_time_info()
            print(
                f"\r{info['current_formatted']} / {info['total_formatted']} ({info['percentage']:.1f}%)",
                end="",
            )
            time.sleep(1)
    except KeyboardInterrupt:
        player.stop()
        player.cleanup()
