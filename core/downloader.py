"""
YouTube Downloader Integration

Handles yt-dlp for extracting stream URLs and downloading audio.
"""

import yt_dlp
from pathlib import Path
from typing import Dict, Optional, Callable
import hashlib
import logging
import os
from core.logger import setup_logging

logger = logging.getLogger("YouTubeDownloader")


class YouTubeDownloader:
    """Manages YouTube audio downloads and streaming URL extraction."""
    
    # Estimated size per track in bytes (5MB average for audio)
    ESTIMATED_TRACK_SIZE = 5 * 1024 * 1024
    
    def __init__(self, cache_dir: str = 'cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Suppress yt-dlp console output completely
        self._null_logger = logging.getLogger('yt-dlp')
        self._null_logger.setLevel(logging.CRITICAL)
        
        # yt-dlp options for extracting info without downloading
        self.ydl_opts_info = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'logger': self._null_logger,
        }
        
        # yt-dlp options for downloading
        self.ydl_opts_download = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'logger': self._null_logger,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }
        
        logger.info("YouTubeDownloader initialized")
    
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
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'id': info.get('id'),
                    'title': info.get('title', 'Unknown'),
                    'artist': info.get('uploader', 'Unknown Artist'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail'),
                    'url': url,
                    'formats': info.get('formats', [])
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
        try:
            info = self.extract_info(url)
            if not info:
                return None
            
            raw_title = info.get('title', '')
            uploader = info.get('uploader', 'Unknown Artist')
            duration = info.get('duration', 0)
            
            # Try to parse "Artist - Title" format
            title = raw_title
            artist = uploader
            
            # Common separators
            separators = [' - ', ' – ', ' — ', ' | ', ' // ']
            
            for sep in separators:
                if sep in raw_title:
                    parts = raw_title.split(sep, 1)
                    if len(parts) == 2:
                        artist = parts[0].strip()
                        title = parts[1].strip()
                        break
            
            # Clean up common suffixes
            suffixes = [
                '(Official Video)', '(Official Music Video)', 
                '(Official Audio)', '(Lyric Video)', '(Lyrics)',
                '[Official Video]', '[Official Music Video]',
                '[Official Audio]', '[Lyric Video]', '[Lyrics]'
            ]
            
            for suffix in suffixes:
                if suffix in title:
                    title = title.replace(suffix, '').strip()
            
            return {
                'title': title,
                'artist': artist,
                'duration': duration,
                'raw_title': raw_title
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
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Get best audio format
                formats = info.get('formats', [])
                audio_formats = [f for f in formats if f.get('acodec') != 'none']
                
                if audio_formats:
                    # Sort by quality (abr = audio bitrate)
                    # Use 'or 0' to handle None values that get() might return
                    audio_formats.sort(key=lambda x: x.get('abr') or 0, reverse=True)
                    return audio_formats[0]['url']
                
                # Fallback to any format with audio
                return info.get('url')
                
        except Exception as e:
            raise Exception(f"Failed to get stream URL from {url}: {e}")

    def extract_playlist_items(self, url: str):
        """
        Extract basic metadata for a YouTube playlist (no download).
        
        Returns list of dicts with: title, artist (uploader), duration, url.
        """
        try:
            opts = self.ydl_opts_info.copy()
            opts["extract_flat"] = True  # faster, no individual downloads
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            entries = info.get("entries", []) or []
            items = []
            base_webpage_url = info.get("webpage_url")

            for entry in entries:
                # entry may already contain url; if not, build from id
                eurl = entry.get("url") or entry.get("webpage_url")
                if not eurl and entry.get("id"):
                    eurl = f"https://www.youtube.com/watch?v={entry['id']}"
                items.append(
                    {
                        "title": entry.get("title", "Unknown"),
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
    
    def download(self, url: str, output_path: Optional[str] = None, 
                 progress_callback: Optional[Callable] = None) -> str:
        """
        Download audio to cache.
        
        Args:
            url: YouTube video URL
            output_path: Custom output path (optional, uses cache by default)
            progress_callback: Function called with download progress
            
        Returns:
            Path to downloaded file
        """
        try:
            # Generate cache filename from URL
            if output_path is None:
                video_id = self._extract_video_id(url)
                output_path = str(self.cache_dir / f"{video_id}.%(ext)s")
            
            # Setup progress hook
            opts = self.ydl_opts_download.copy()
            if progress_callback:
                opts['progress_hooks'] = [self._create_progress_hook(progress_callback)]
            
            opts['outtmpl'] = output_path
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            
            # Return actual file path (yt-dlp adds extension)
            final_path = output_path.replace('.%(ext)s', '.m4a')
            return final_path
            
        except Exception as e:
            raise Exception(f"Failed to download {url}: {e}")
    
    def is_cached(self, url: str) -> Optional[str]:
        """
        Check if a URL is already cached.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Path to cached file if exists, None otherwise
        """
        video_id = self._extract_video_id(url)
        cache_file = self.cache_dir / f"{video_id}.m4a"
        
        if cache_file.exists():
            return str(cache_file)
        return None
    
    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL or generate hash."""
        # Try to extract video ID from URL
        if 'v=' in url:
            return url.split('v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        else:
            # Fallback: hash the URL
            return hashlib.md5(url.encode()).hexdigest()[:16]
    
    def _create_progress_hook(self, callback: Callable):
        """Create a progress hook for yt-dlp."""
        def hook(d):
            if d['status'] == 'downloading':
                # Extract download progress
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                
                if total > 0:
                    percent = (downloaded / total) * 100
                    callback(percent, downloaded, total)
                    
            elif d['status'] == 'finished':
                callback(100, d.get('total_bytes', 0), d.get('total_bytes', 0))
        
        return hook


if __name__ == '__main__':
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
