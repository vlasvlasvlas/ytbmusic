"""
Icecast/Shoutcast Streaming Module

Streams audio to external streaming servers using FFmpeg.
Supports live re-encoding and broadcasting.
"""

import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("StreamBroadcaster")


class StreamBroadcaster:
    """
    Broadcasts audio to Icecast/Shoutcast servers.

    Uses FFmpeg to re-encode and stream audio to a configured server.
    The stream runs in a background thread and can be started/stopped.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize broadcaster with streaming config.

        Config keys:
            url: Full Icecast/Shoutcast URL (e.g., icecast://source:pass@host:port/mount)
            user: Stream source username (default: source)
            password: Stream source password
            bitrate: Audio bitrate in kbps (default: 128)
            format: Audio format - mp3 or ogg (default: mp3)
        """
        self.config = config
        self.url = config.get("url", "")
        self.user = config.get("user", "source")
        self.password = config.get("password", "")
        self.bitrate = int(config.get("bitrate", 128))
        self.format = config.get("format", "mp3").lower()

        # State
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._current_source = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_status: Optional[Callable[[str], None]] = None

    def is_configured(self) -> bool:
        """Check if streaming is properly configured."""
        return bool(self.url and self.password)

    def get_shareable_link(self) -> str:
        """
        Get the public URL that listeners can use.

        Converts icecast://user:pass@host:port/mount to http://host:port/mount
        """
        if not self.url:
            return ""

        url = self.url

        # Handle icecast:// protocol
        if url.startswith("icecast://"):
            url = url.replace("icecast://", "http://")

        # Remove credentials from URL for sharing
        if "@" in url:
            # Extract host:port/mount from user:pass@host:port/mount
            url = "http://" + url.split("@", 1)[1]

        return url

    def start_stream(self, source_path: str) -> bool:
        """
        Start streaming audio file to the configured server.

        Args:
            source_path: Path to audio file or stream URL

        Returns:
            True if stream started successfully
        """
        if not self.is_configured():
            logger.warning("Stream not configured - missing URL or password")
            return False

        if self._running:
            self.stop_stream()

        self._current_source = source_path
        self._running = True

        # Run FFmpeg in background thread
        self._thread = threading.Thread(target=self._run_ffmpeg, daemon=True)
        self._thread.start()

        return True

    def stop_stream(self):
        """Stop the current stream."""
        self._running = False

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

        if self._thread:
            try:
                self._thread.join(timeout=2)
            except Exception:
                pass
            self._thread = None

        self._current_source = None
        logger.info("Stream stopped")

    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        return self._running and self._process is not None

    def _build_ffmpeg_command(self, source: str) -> list:
        """Build FFmpeg command for streaming."""
        # Build Icecast URL with credentials
        icecast_url = self._build_icecast_url()

        if self.format == "ogg":
            codec = "libvorbis"
            content_type = "audio/ogg"
        else:
            codec = "libmp3lame"
            content_type = "audio/mpeg"

        cmd = [
            "ffmpeg",
            "-re",  # Read at native framerate
            "-i",
            source,  # Input file
            "-vn",  # No video
            "-acodec",
            codec,
            "-b:a",
            f"{self.bitrate}k",
            "-ar",
            "44100",  # Standard sample rate
            "-ac",
            "2",  # Stereo
            "-f",
            self.format if self.format == "ogg" else "mp3",
            "-content_type",
            content_type,
            icecast_url,
        ]

        return cmd

    def _build_icecast_url(self) -> str:
        """Build full Icecast URL with credentials."""
        url = self.url

        # If URL already has icecast:// prefix, use it
        if url.startswith("icecast://"):
            return url

        # If URL is http://, convert to icecast://
        if url.startswith("http://"):
            url = url.replace("http://", "icecast://")
        elif not url.startswith("icecast://"):
            url = "icecast://" + url

        # Insert credentials if not already in URL
        if "@" not in url:
            # Parse host from url
            protocol = "icecast://"
            rest = url[len(protocol) :]
            url = f"{protocol}{self.user}:{self.password}@{rest}"

        return url

    def _run_ffmpeg(self):
        """Run FFmpeg in background thread."""
        if not self._current_source:
            return

        cmd = self._build_ffmpeg_command(self._current_source)
        logger.info(f"Starting stream: {' '.join(cmd[:5])}...")

        if self._on_status:
            self._on_status("Connecting to Icecast...")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )

            if self._on_status:
                self._on_status(f"Streaming to {self.get_shareable_link()}")

            # Wait for process and monitor output
            stdout, stderr = self._process.communicate()

            if self._process.returncode != 0:
                error_msg = stderr.decode()[-500:] if stderr else "Unknown error"
                logger.error(f"FFmpeg stream failed: {error_msg}")
                if self._on_error:
                    self._on_error(f"Stream error: {error_msg[:100]}")

        except Exception as e:
            logger.error(f"Stream error: {e}")
            if self._on_error:
                self._on_error(str(e))
        finally:
            self._running = False
            self._process = None


def check_ffmpeg_available() -> bool:
    """Check if FFmpeg is installed and available."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def get_ffmpeg_version() -> str:
    """Get FFmpeg version string."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            # First line contains version
            return result.stdout.split("\n")[0]
        return ""
    except Exception:
        return ""


if __name__ == "__main__":
    # Quick test
    print(f"FFmpeg available: {check_ffmpeg_available()}")
    print(f"FFmpeg version: {get_ffmpeg_version()}")

    # Test config
    config = {
        "url": "http://localhost:8000/stream",
        "user": "source",
        "password": "hackme",
        "bitrate": 128,
        "format": "mp3",
    }

    broadcaster = StreamBroadcaster(config)
    print(f"Configured: {broadcaster.is_configured()}")
    print(f"Shareable: {broadcaster.get_shareable_link()}")
