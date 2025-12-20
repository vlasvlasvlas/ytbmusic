"""
YouTube Downloader Integration

Handles yt-dlp for extracting stream URLs and downloading audio.
"""

import hashlib
import logging
import os
import time
import random
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Callable

import yt_dlp
from core.logger import setup_logging

logger = logging.getLogger("YouTubeDownloader")


class YouTubeDownloader:
    """Manages YouTube audio downloads and streaming URL extraction."""

    # Estimated size per track in bytes (5MB average for audio)
    ESTIMATED_TRACK_SIZE = 5 * 1024 * 1024
    MAX_RETRIES = 3

    @staticmethod
    def validate_url(url: str):
        """Ensure URL is valid, safe (http/https), and from YouTube."""
        if not url:
            raise ValueError("Empty URL")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("Invalid URL scheme: must be http or https")
        # Basic check to prevent local file access
        if "file://" in url:
            raise ValueError("Local file URLs are not allowed")
            
        # Domain allowlist
        allowed_domains = ["youtube.com", "www.youtube.com", "youtu.be", "music.youtube.com"]
        # Simple string check (robust enough for typical usage, parsed check better but needs urllib)
        is_allowed = any(domain in url for domain in allowed_domains)
        if not is_allowed:
            raise ValueError("Security: Only YouTube URLs are allowed")

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Suppress yt-dlp console output completely
        self._null_logger = logging.getLogger("yt-dlp")
        self._null_logger.setLevel(logging.CRITICAL)

        # yt-dlp options for extracting info without downloading
        self.ydl_opts_info = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "logger": self._null_logger,
        }

        # yt-dlp options for downloading
        self.ydl_opts_download = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": self._null_logger,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
        }

        self._apply_cookie_strategy()

        logger.info("YouTubeDownloader initialized")

    def _apply_cookie_strategy(self):
        """
        Configure yt-dlp authentication automatically.

        Priority:
        1. Explicit file via YTBMUSIC_COOKIES_FILE or cookies.txt.
        2. Explicit browser via YTBMUSIC_COOKIES_BROWSER.
        3. Best-effort autodetect of popular Chromium/Firefox/Safari profiles.
        """

        if os.environ.get("YTBMUSIC_DISABLE_COOKIES"):
            logger.warning("Cookie strategy disabled via YTBMUSIC_DISABLE_COOKIES")
            return

        cookie_file_env = os.environ.get("YTBMUSIC_COOKIES_FILE")
        cookie_path = Path(cookie_file_env) if cookie_file_env else Path("cookies.txt")
        if cookie_path.exists():
            self._set_cookie_file(cookie_path)
            return

        browser_pref = os.environ.get("YTBMUSIC_COOKIES_BROWSER")
        browser_candidates = [
            "chrome",
            "brave",
            "edge",
            "vivaldi",
            "opera",
            "chromium",
            "firefox",
            "safari",
        ]
        if browser_pref:
            browser_candidates = [browser_pref] + [
                b for b in browser_candidates if b != browser_pref
            ]

        for browser in browser_candidates:
            if self._set_browser_cookies(browser):
                return

        logger.warning(
            "No cookies configured (set cookies.txt or YTBMUSIC_COOKIES_* env vars). "
            "YouTube may require manual verification."
        )

    def _set_cookie_file(self, path: Path):
        logger.info(f"Using cookies file: {path}")
        self.ydl_opts_info["cookiefile"] = str(path)
        self.ydl_opts_download["cookiefile"] = str(path)

    def _set_browser_cookies(self, browser: str) -> bool:
        """
        Register a browser profile for yt-dlp cookie extraction.
        Returns True once configured (yt-dlp will raise later if browser unsupported).
        """
        browser = browser.lower()
        supported = {
            "chrome",
            "chromium",
            "brave",
            "vivaldi",
            "edge",
            "opera",
            "safari",
            "firefox",
        }
        if browser not in supported:
            return False

        logger.info(f"Attempting cookies_from_browser='{browser}'")
        spec = (browser,)
        self.ydl_opts_info["cookiesfrombrowser"] = spec
        self.ydl_opts_download["cookiesfrombrowser"] = spec
        return True

    def refresh_cookies_from_browser(
        self,
        browser: Optional[str] = None,
        output: Optional[str] = None,
        test_url: Optional[str] = None,
    ) -> str:
        """
        Invoke yt-dlp to export cookies from a browser profile into a cookies.txt file.
        Returns the path to the cookies file if successful.
        """

        browser = (
            browser
            or os.environ.get("YTBMUSIC_COOKIES_BROWSER")
            or "firefox"
        )
        cookie_file_env = output or os.environ.get("YTBMUSIC_COOKIES_FILE")
        cookie_path = Path(cookie_file_env) if cookie_file_env else Path("cookies.txt")
        cookie_path.parent.mkdir(parents=True, exist_ok=True)

        test_url = (
            test_url
            or os.environ.get("YTBMUSIC_COOKIES_TEST_URL")
            or "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )

        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--simulate",
            "--cookies-from-browser",
            browser,
            "--cookies",
            str(cookie_path),
            test_url,
        ]

        logger.info(f"Refreshing cookies via browser='{browser}' → {cookie_path}")
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )
        if proc.returncode != 0:
            err_output = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(
                f"yt-dlp cookies export failed ({browser}): {err_output}"
            )

        if not cookie_path.exists():
            raise RuntimeError(
                f"Cookies export did not create {cookie_path}. "
                "Please ensure the browser has an active YouTube session."
            )

        self._set_cookie_file(cookie_path)
        return str(cookie_path)

    def check_disk_space(self, track_count: int) -> tuple:
        """
        Check if there's enough disk space for downloading tracks.

        Args:
            track_count: Number of tracks to download

        Returns:
            Tuple of (has_enough_space: bool, available_mb: float, required_mb: float)
        """
        import shutil

        try:
            disk_usage = shutil.disk_usage(self.cache_dir)
            available_bytes = disk_usage.free
            required_bytes = track_count * self.ESTIMATED_TRACK_SIZE

            available_mb = available_bytes / (1024 * 1024)
            required_mb = required_bytes / (1024 * 1024)

            return available_bytes >= required_bytes, available_mb, required_mb
        except Exception:
            # If we can't check, assume it's fine
            return True, 0, 0

    def extract_info(self, url: str) -> Dict:
        """
        Extract metadata from YouTube video without downloading.

        Args:
            url: YouTube video URL

        Returns:
            Dictionary with title, artist (uploader), duration, thumbnail, etc.
        """
        self.validate_url(url)
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    "id": info.get("id"),
                    "title": info.get("title", "Unknown"),
                    "artist": info.get("uploader", "Unknown Artist"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail"),
                    "url": url,
                    "formats": info.get("formats", []),
                }
        except Exception as e:
            return None

    def extract_metadata(self, url: str) -> Optional[Dict[str, str]]:
        """
        Extract metadata from YouTube URL and parse title.

        Attempts to parse title in format "Artist - Song Title" or similar.

        Args:
            url: YouTube video URL

        Returns:
            Dictionary with 'title', 'artist', 'duration' or None if failed
        """
        self.validate_url(url)
        try:
            info = self.extract_info(url)
            if not info:
                return None

            raw_title = info.get("title", "")
            uploader = info.get("uploader", "Unknown Artist")
            duration = info.get("duration", 0)

            # SOTA Check: Skip unusable tracks (Private/Deleted)
            if raw_title in ["[Private video]", "[Deleted video]"]:
                logger.info(f"Skipping unusable track metadata extraction: {raw_title}")
                return None

            # Try to parse "Artist - Title" format
            title = raw_title
            artist = uploader

            # Common separators
            separators = [" - ", " – ", " — ", " | ", " // "]

            for sep in separators:
                if sep in raw_title:
                    parts = raw_title.split(sep, 1)
                    if len(parts) == 2:
                        artist = parts[0].strip()
                        title = parts[1].strip()
                        break

            # Clean up common suffixes
            suffixes = [
                "(Official Video)",
                "(Official Music Video)",
                "(Official Audio)",
                "(Lyric Video)",
                "(Lyrics)",
                "[Official Video]",
                "[Official Music Video]",
                "[Official Audio]",
                "[Lyric Video]",
                "[Lyrics]",
            ]

            for suffix in suffixes:
                if suffix in title:
                    title = title.replace(suffix, "").strip()

            return {
                "title": title,
                "artist": artist,
                "duration": duration,
                "raw_title": raw_title,
            }
        except Exception as e:
            return None

    def get_stream_url(self, url: str) -> str:
        """
        Get direct streaming URL for immediate playback.

        Args:
            url: YouTube video URL

        Returns:
            Direct audio stream URL
        """
        self.validate_url(url)
        info = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts_info) as ydl:
                    info = ydl.extract_info(url, download=False)
                break
            except Exception as e:
                if attempt < self.MAX_RETRIES and (
                    "429" in str(e) or "too many requests" in str(e).lower()
                ):
                    wait = (attempt + 1) * 30 + random.uniform(1, 10)
                    logger.warning(
                        f"HTTP 429. Retrying get_stream_url in {wait:.1f}s..."
                    )
                    time.sleep(wait)
                    continue
                raise Exception(f"Failed to get stream URL from {url}: {e}")

        if not info:
            raise Exception(f"Failed to get stream URL from {url}: empty info")

        formats = info.get("formats", [])
        audio_formats = [f for f in formats if f.get("acodec") != "none"]

        if audio_formats:
            audio_formats.sort(key=lambda x: x.get("abr") or 0, reverse=True)
            return audio_formats[0]["url"]

        return info.get("url")

    def extract_playlist_items(self, url: str):
        """
        Extract basic metadata for a YouTube playlist (no download).

        Returns list of dicts with: title, artist (uploader), duration, url.
        """
        self.validate_url(url)
        try:
            # 1. Clean URL: If it has v=...&list=..., strip v= to process as pure playlist
            # This fixes "Watch with Playlist" URLs often failing in flat extraction
            if "list=" in url and "v=" in url:
                from urllib.parse import urlparse, parse_qs

                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                if "list" in qs:
                    url = f"https://www.youtube.com/playlist?list={qs['list'][0]}"

            opts = self.ydl_opts_info.copy()
            opts["extract_flat"] = (
                "in_playlist"  # More robust than True for flat extraction
            )
            for attempt in range(self.MAX_RETRIES + 1):
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                    break
                except Exception as e:
                    if attempt < self.MAX_RETRIES and ("429" in str(e) or "Too many requests" in str(e).lower()):
                        wait = (attempt + 1) * 30 + random.uniform(1, 10)
                        logger.warning(f"HTTP 429. Retrying extract_playlist in {wait:.1f}s...")
                        time.sleep(wait)
                        continue
                    raise

            entries = info.get("entries")
            items = []
            base_webpage_url = info.get("webpage_url")

            # Handle single video logic
            if not entries:
                if info.get("chapters"):
                    # Split into chapters
                    for idx, ch in enumerate(info["chapters"]):
                        start = ch.get("start_time")
                        end = ch.get("end_time")
                        title = ch.get("title") or f"Chapter {idx+1}"
                        # Append hash fragment to URL to make it unique for caching per-chapter if needed
                        # (though we want to cache the whole file, the track list needs unique logical items)
                        # We'll handle stripping the hash in _extract_video_id
                        full_url = f"{info['webpage_url'] or info['url']}#chapter_{idx}"
                        
                        items.append({
                            "title": title,
                            "artist": info.get("uploader", "Unknown Artist"),
                            "duration": (end - start) if (end and start) else 0,
                            "url": full_url,
                            "start_time": start,
                            "end_time": end
                        })
                    return {
                        "title": info.get("title", "Imported Playlist"),
                        "count": len(items),
                        "items": items,
                        "source_url": base_webpage_url or url,
                    }
                
                # If no entries and no chapters, treat as single video
                elif info.get("id") and info.get("title"):
                    entries = [info]
                else:
                    entries = []

            # If items populated by chapters, we skip the normal entry loop
            # Otherwise we process standard entries
            if not items:
                for entry in entries:
                    # entry may already contain url; if not, build from id
                    eurl = entry.get("url") or entry.get("webpage_url")
                    if not eurl and entry.get("id"):
                        eurl = f"https://www.youtube.com/watch?v={entry['id']}"

                    title = entry.get("title", "Unknown")

                    # SOTA: Filter out unusable videos immediately
                    if title in ["[Private video]", "[Deleted video]"]:
                        continue

                    items.append(
                        {
                            "title": title,
                            "artist": entry.get("uploader", "Unknown Artist"),
                            "duration": entry.get("duration", 0),
                            "url": eurl,
                        }
                    )
            
            return {
                "title": info.get("title", "Imported Playlist"),
                "count": len(items),
                "items": items,
                "source_url": base_webpage_url or url,
            }
        except Exception as e:
            raise Exception(f"Failed to extract playlist: {e}")

    def download(
        self,
        url: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        title: Optional[str] = None,
        artist: Optional[str] = None,
    ) -> str:
        """
        Download audio to cache.

        Args:
            url: YouTube video URL
            output_path: Custom output path (optional, uses cache by default)
            progress_callback: Function called with download progress
            title: Track title for naming (optional)
            artist: Artist name for naming (optional)

        Returns:
            Path to downloaded file
        """
        self.validate_url(url)

        # Anti-Bot: Random delay to mimic human behavior
        # User requested > 3s
        delay = random.uniform(3.5, 8.0)
        logger.debug(f"Sleeping {delay:.2f}s before download...")
        time.sleep(delay)

        try:
            # Generate cache filename
            if output_path is None:
                video_id = self._extract_video_id(url)
                if title:
                    safe_name = self._make_cache_filename(title, artist)
                    output_path = str(self.cache_dir / f"{safe_name}.%(ext)s")
                else:
                    output_path = str(self.cache_dir / f"{video_id}.%(ext)s")

            # Setup progress hook
            opts = self.ydl_opts_download.copy()
            if progress_callback:
                opts["progress_hooks"] = [self._create_progress_hook(progress_callback)]

            opts["outtmpl"] = output_path

            for attempt in range(self.MAX_RETRIES + 1):
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([url])
                    break
                except Exception as e:
                    if attempt < self.MAX_RETRIES and ("429" in str(e) or "Too many requests" in str(e).lower()):
                        wait = (attempt + 1) * 30 + random.uniform(1, 10)
                        logger.warning(f"HTTP 429. Retrying download in {wait:.1f}s...")
                        time.sleep(wait)
                        continue
                    raise

            # Return actual file path (yt-dlp adds extension)
            final_path = output_path.replace(".%(ext)s", ".m4a")
            return final_path

        except yt_dlp.utils.DownloadCancelled:
            # Propagate so callers can treat it as a cancellation (not an error)
            raise
        except Exception as e:
            raise Exception(f"Failed to download {url}: {e}")

    def is_cached(
        self, url: str, title: Optional[str] = None, artist: Optional[str] = None
    ) -> Optional[str]:
        """
        Check if a URL is already cached.

        Args:
            url: YouTube video URL
            title: Track title for naming (optional)
            artist: Artist name for naming (optional)

        Returns:
            Path to cached file if exists, None otherwise
        """
        import re
        
        # Strategy 1: Check exact name using current format
        if title:
            safe_name = self._make_cache_filename(title, artist)
            cache_file = self.cache_dir / f"{safe_name}.m4a"
            if cache_file.exists():
                return str(cache_file)
        
        # Strategy 2: Fallback to video_id
        video_id = self._extract_video_id(url)
        cache_file = self.cache_dir / f"{video_id}.m4a"
        if cache_file.exists():
            return str(cache_file)
        
        # Strategy 3: Fuzzy search - look for files containing key parts of title/artist
        if title:
            # Extract alphanumeric core from title (first significant word)
            title_core = re.sub(r"[^a-zA-Z0-9]", "", title)[:20]
            artist_core = re.sub(r"[^a-zA-Z0-9]", "", artist or "")[:15] if artist else ""
            
            if title_core:
                # Search for any m4a file containing both cores
                for f in self.cache_dir.glob("*.m4a"):
                    fname = f.stem
                    # Check if filename contains key parts (case insensitive)
                    if title_core.lower() in fname.lower():
                        if not artist_core or artist_core.lower() in fname.lower():
                            return str(f)

        return None

    def _make_cache_filename(self, title: str, artist: Optional[str] = None) -> str:
        """Create a safe filename from artist and title (alphanumeric + underscore only)."""
        import re

        # Combine artist and title with a temporary placeholder that won't be stripped
        if artist and artist != "Unknown Artist":
            name = f"{artist}__SEP__{title}"
        else:
            name = title

        # Keep only alphanumeric, spaces, and underscores (strip hyphens for consistency with existing cache files)
        # First remove everything else
        name = re.sub(r"[^a-zA-Z0-9\s_]", "", name)

        # Replace the separator with actual underscore (and surrounding spaces if any)
        name = name.replace("__SEP__", "_")

        # Replace spaces with underscores
        name = re.sub(r"\s+", "_", name)

        # Cleanup multiple underscores
        name = re.sub(r"_+", "_", name)
        name = name.strip("_")

        # Limit length (filesystem limits)
        if len(name) > 80:
            name = name[:80]

        return name

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL or generate hash."""
        # Strip fragment if present
        if "#" in url:
            url = url.split("#")[0]
            
        # Try to extract video ID from URL
        if "v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        else:
            # Fallback: hash the URL
            return hashlib.md5(url.encode()).hexdigest()[:16]

    def _create_progress_hook(self, callback: Callable):
        """Create a progress hook for yt-dlp."""

        def hook(d):
            if d["status"] == "downloading":
                # Extract download progress
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)

                if total > 0:
                    percent = (downloaded / total) * 100
                    callback(percent, downloaded, total)

            elif d["status"] == "finished":
                callback(100, d.get("total_bytes", 0), d.get("total_bytes", 0))

        return hook


if __name__ == "__main__":
    # Test the downloader
    downloader = YouTubeDownloader()

    test_url = "https://www.youtube.com/watch?v=jfKfPfyJRdk"

    print("Extracting info...")
    info = downloader.extract_info(test_url)
    print(f"Title: {info['title']}")
    print(f"Artist: {info['artist']}")
    print(f"Duration: {info['duration']}s")

    print("\nGetting stream URL...")
    stream_url = downloader.get_stream_url(test_url)
    print(f"Stream URL: {stream_url[:100]}...")

    print("\nChecking cache...")
    cached = downloader.is_cached(test_url)
    if cached:
        print(f"Already cached: {cached}")
    else:
        print("Not cached yet")
