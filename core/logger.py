"""
Logging System

Handles playback history, error logs, and usage statistics.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging


class YTBMusicLogger:
    """Comprehensive logging system for YTBMusic."""
    
    def __init__(self, logs_dir: str = 'logs'):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Log files
        self.playback_log = self.logs_dir / 'playback.log'
        self.error_log = self.logs_dir / 'errors.log'
        self.stats_file = self.logs_dir / 'statistics.json'
        
        # Statistics data
        self.stats = self._load_statistics()
        
        # Setup Python logging for errors
        self._setup_error_logging()
    
    def _setup_error_logging(self):
        """Setup Python logging for error tracking."""
        self.error_logger = logging.getLogger('ytbmusic')
        self.error_logger.setLevel(logging.ERROR)
        
        # File handler
        handler = logging.FileHandler(self.error_log)
        handler.setLevel(logging.ERROR)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        self.error_logger.addHandler(handler)
    
    def _load_statistics(self) -> Dict[str, Any]:
        """Load statistics from file."""
        if self.stats_file.exists():
            with open(self.stats_file, 'r') as f:
                return json.load(f)
        else:
            return {
                'total_tracks_played': 0,
                'total_playtime_seconds': 0,
                'tracks_by_artist': {},
                'tracks_by_playlist': {},
                'most_played_tracks': {},
                'session_history': [],
                'cache_hits': 0,
                'cache_misses': 0,
                'downloads_completed': 0,
                'errors_count': 0,
                'last_updated': time.time()
            }
    
    def _save_statistics(self):
        """Save statistics to file."""
        self.stats['last_updated'] = time.time()
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
    
    # Playback logging
    def log_track_start(self, title: str, artist: str, playlist: str, 
                       url: str, from_cache: bool = False):
        """Log when a track starts playing."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Write to playback log
        with open(self.playback_log, 'a', encoding='utf-8') as f:
            cache_status = "CACHED" if from_cache else "STREAM"
            f.write(f"{timestamp} - PLAY - {title} - {artist} - [{cache_status}] - Playlist: {playlist}\n")
        
        # Update statistics
        self.stats['total_tracks_played'] += 1
        
        # Track by artist
        if artist not in self.stats['tracks_by_artist']:
            self.stats['tracks_by_artist'][artist] = 0
        self.stats['tracks_by_artist'][artist] += 1
        
        # Track by playlist
        if playlist not in self.stats['tracks_by_playlist']:
            self.stats['tracks_by_playlist'][playlist] = 0
        self.stats['tracks_by_playlist'][playlist] += 1
        
        # Most played tracks
        track_key = f"{title} - {artist}"
        if track_key not in self.stats['most_played_tracks']:
            self.stats['most_played_tracks'][track_key] = {
                'count': 0,
                'title': title,
                'artist': artist,
                'url': url
            }
        self.stats['most_played_tracks'][track_key]['count'] += 1
        
        # Cache statistics
        if from_cache:
            self.stats['cache_hits'] += 1
        else:
            self.stats['cache_misses'] += 1
        
        self._save_statistics()
    
    def log_track_complete(self, title: str, artist: str, duration: float):
        """Log when a track completes."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(self.playback_log, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - COMPLETE - {title} - {artist} - Duration: {duration:.1f}s\n")
        
        # Update total playtime
        self.stats['total_playtime_seconds'] += duration
        self._save_statistics()
    
    def log_track_skip(self, title: str, artist: str, position: float):
        """Log when a track is skipped."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(self.playback_log, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - SKIP - {title} - {artist} - At: {position:.1f}s\n")
        
        # Update playtime with partial duration
        self.stats['total_playtime_seconds'] += position
        self._save_statistics()
    
    def log_download_complete(self, title: str, artist: str, file_size: int):
        """Log when a download completes."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(self.playback_log, 'a', encoding='utf-8') as f:
            size_mb = file_size / (1024 * 1024)
            f.write(f"{timestamp} - DOWNLOAD - {title} - {artist} - Size: {size_mb:.2f}MB\n")
        
        self.stats['downloads_completed'] += 1
        self._save_statistics()
    
    # Error logging
    def log_error(self, error_type: str, message: str, details: Optional[str] = None):
        """Log an error."""
        self.error_logger.error(f"{error_type}: {message}")
        
        if details:
            self.error_logger.error(f"Details: {details}")
        
        self.stats['errors_count'] += 1
        self._save_statistics()
    
    def log_warning(self, message: str):
        """Log a warning."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(self.error_log, 'a') as f:
            f.write(f"{timestamp} - WARNING - {message}\n")
    
    # Session logging
    def log_session_start(self):
        """Log session start."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(self.playback_log, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"{timestamp} - SESSION START\n")
            f.write(f"{'='*60}\n")
        
        # Add to session history
        self.stats['session_history'].append({
            'start_time': time.time(),
            'end_time': None,
            'tracks_played': 0
        })
        
        # Keep only last 100 sessions
        if len(self.stats['session_history']) > 100:
            self.stats['session_history'] = self.stats['session_history'][-100:]
        
        self._save_statistics()
    
    def log_session_end(self, tracks_played: int):
        """Log session end."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(self.playback_log, 'a') as f:
            f.write(f"{timestamp} - SESSION END - Tracks played: {tracks_played}\n")
            f.write(f"{'='*60}\n\n")
        
        # Update last session
        if self.stats['session_history']:
            self.stats['session_history'][-1]['end_time'] = time.time()
            self.stats['session_history'][-1]['tracks_played'] = tracks_played
        
        self._save_statistics()
    
    # Statistics retrieval
    def get_statistics(self) -> Dict[str, Any]:
        """Get all statistics."""
        return self.stats.copy()
    
    def get_top_artists(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top artists by play count."""
        artists = [
            {'artist': artist, 'plays': count}
            for artist, count in self.stats['tracks_by_artist'].items()
        ]
        artists.sort(key=lambda x: x['plays'], reverse=True)
        return artists[:limit]
    
    def get_top_tracks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top tracks by play count."""
        tracks = list(self.stats['most_played_tracks'].values())
        tracks.sort(key=lambda x: x['count'], reverse=True)
        return tracks[:limit]
    
    def get_top_playlists(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top playlists by play count."""
        playlists = [
            {'playlist': playlist, 'plays': count}
            for playlist, count in self.stats['tracks_by_playlist'].items()
        ]
        playlists.sort(key=lambda x: x['plays'], reverse=True)
        return playlists[:limit]
    
    def get_cache_efficiency(self) -> Dict[str, Any]:
        """Get cache hit/miss statistics."""
        total = self.stats['cache_hits'] + self.stats['cache_misses']
        
        if total == 0:
            hit_rate = 0
        else:
            hit_rate = (self.stats['cache_hits'] / total) * 100
        
        return {
            'hits': self.stats['cache_hits'],
            'misses': self.stats['cache_misses'],
            'total': total,
            'hit_rate_percent': hit_rate
        }
    
    def get_formatted_playtime(self) -> str:
        """Get total playtime formatted as human-readable string."""
        total_seconds = self.stats['total_playtime_seconds']
        
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    # Reporting
    def generate_report(self) -> str:
        """Generate a human-readable statistics report."""
        report = []
        report.append("=" * 60)
        report.append("YTBMusic - Usage Statistics Report")
        report.append("=" * 60)
        report.append("")
        
        # Overall stats
        report.append("📊 Overall Statistics:")
        report.append(f"  Total Tracks Played: {self.stats['total_tracks_played']}")
        report.append(f"  Total Playtime: {self.get_formatted_playtime()}")
        report.append(f"  Sessions: {len(self.stats['session_history'])}")
        report.append(f"  Downloads: {self.stats['downloads_completed']}")
        report.append(f"  Errors: {self.stats['errors_count']}")
        report.append("")
        
        # Cache efficiency
        cache_stats = self.get_cache_efficiency()
        report.append("💾 Cache Efficiency:")
        report.append(f"  Hit Rate: {cache_stats['hit_rate_percent']:.1f}%")
        report.append(f"  Hits: {cache_stats['hits']}")
        report.append(f"  Misses: {cache_stats['misses']}")
        report.append("")
        
        # Top artists
        report.append("🎤 Top Artists:")
        for i, artist in enumerate(self.get_top_artists(5), 1):
            report.append(f"  {i}. {artist['artist']} - {artist['plays']} plays")
        report.append("")
        
        # Top tracks
        report.append("🎵 Top Tracks:")
        for i, track in enumerate(self.get_top_tracks(5), 1):
            report.append(f"  {i}. {track['title']} - {track['artist']} - {track['count']} plays")
        report.append("")
        
        # Top playlists
        report.append("📝 Top Playlists:")
        for i, playlist in enumerate(self.get_top_playlists(5), 1):
            report.append(f"  {i}. {playlist['playlist']} - {playlist['plays']} plays")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)


if __name__ == '__main__':
    # Test the logger
    logger = YTBMusicLogger()
    
    # Simulate some activity
    logger.log_session_start()
    logger.log_track_start("Bohemian Rhapsody", "Queen", "rock", "url", from_cache=False)
    logger.log_track_complete("Bohemian Rhapsody", "Queen", 354.0)
    logger.log_session_end(1)
    
    # Print report
    print(logger.generate_report())
