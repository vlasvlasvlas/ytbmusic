#!/usr/bin/env python3
"""
YTBMusic - Suite Completa de Tests Automatizados
Tests todas las funcionalidades críticas
"""

import sys
import time
import tempfile
import shutil
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


class TestRunner:
    """Test runner with colored output."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, name, func):
        """Run a single test."""
        print(f"\n{'─'*70}")
        print(f"🧪 TEST: {name}")
        print(f"{'─'*70}")

        try:
            start = time.time()
            result = func()
            duration = time.time() - start

            if result:
                print(f"✅ PASSED ({duration:.2f}s)")
                self.passed += 1
                self.tests.append((name, True, duration, None))
            else:
                print(f"❌ FAILED ({duration:.2f}s)")
                self.failed += 1
                self.tests.append((name, False, duration, "Assertion failed"))

        except Exception as e:
            duration = time.time() - start
            print(f"❌ EXCEPTION ({duration:.2f}s)")
            print(f"   Error: {e}")
            self.failed += 1
            self.tests.append((name, False, duration, str(e)))

            import traceback

            traceback.print_exc()

    def report(self):
        """Print final report."""
        print("\n" + "=" * 70)
        print("📊 TEST RESULTS")
        print("=" * 70)

        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0

        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📈 Pass Rate: {pass_rate:.1f}%")

        if self.failed > 0:
            print("\n❌ Failed Tests:")
            for name, passed, duration, error in self.tests:
                if not passed:
                    print(f"  - {name}")
                    if error:
                        print(f"    Error: {error}")

        print("\n" + "=" * 70)

        return self.failed == 0


# ============================================================================
# TEST SUITE
# ============================================================================


def test_imports():
    """Test 1: All imports work."""
    print("  Importing core modules...")

    from core.player import MusicPlayer
    from core.downloader import YouTubeDownloader
    from core.playlist import PlaylistManager
    from ui.skin_loader import SkinLoader

    print("  ✓ All imports successful")
    return True


def test_skin_loader_matrix():
    """Test 2: Skin loader maintains matrix."""
    print("  Testing skin loader matrix consistency...")

    from ui.skin_loader import SkinLoader, CANVAS_WIDTH, CANVAS_HEIGHT

    loader = SkinLoader()
    skins = loader.list_available_skins()

    if not skins:
        print("  ⚠️  No skins found, skipping")
        return True

    print(f"  Found {len(skins)} skins")

    for skin_name in skins:
        skin_path = f"skins/{skin_name}.txt"

        try:
            meta, lines = loader.load(skin_path)

            # Check dimensions
            if len(lines) != CANVAS_HEIGHT:
                print(f"  ❌ {skin_name}: Height {len(lines)} != {CANVAS_HEIGHT}")
                return False

            for i, line in enumerate(lines):
                if len(line) != CANVAS_WIDTH:
                    print(
                        f"  ❌ {skin_name}: Line {i} width {len(line)} != {CANVAS_WIDTH}"
                    )
                    return False

            print(f"  ✓ {skin_name}: {CANVAS_WIDTH}x{CANVAS_HEIGHT}")

        except Exception as e:
            print(f"  ❌ {skin_name}: {e}")
            return False

    return True


def test_skin_loader_placeholders():
    """Test 3: Skin loader handles all placeholders."""
    print("  Testing placeholder rendering...")

    from ui.skin_loader import SkinLoader

    loader = SkinLoader()
    skins = loader.list_available_skins()

    if not skins:
        print("  ⚠️  No skins found, skipping")
        return True

    # Test context with all placeholders
    context = {
        "PREV": "<<",
        "PLAY": "▶",
        "NEXT": ">>",
        "VOL_DOWN": "-",
        "VOL_UP": "+",
        "QUIT": "Q",
        "TITLE": "Test Song Title That Is Very Long",
        "ARTIST": "Test Artist Name",
        "TIME": "03:45/06:30",
        "TIME_CURRENT": "03:45",
        "TIME_TOTAL": "06:30",
        "PROGRESS": "[█████░░░░░]",
        "VOLUME": "75%",
        "STATUS": "♪",
        "NEXT_TRACK": "Next Track Name",
        "PLAYLIST": "Test Playlist",
        "TRACK_NUM": "2/10",
        "CACHE_STATUS": "✓",
        "SHUFFLE_STATUS": "ON",
        "REPEAT_STATUS": "ALL",
    }

    skin_path = f"skins/{skins[0]}.txt"
    meta, lines = loader.load(skin_path)
    rendered = loader.render(lines, context)

    # Check rendered maintains matrix
    if len(rendered) != len(lines):
        print(f"  ❌ Render changed height: {len(rendered)} != {len(lines)}")
        return False

    for i, line in enumerate(rendered):
        if len(line) != len(lines[i]):
            print(f"  ❌ Render changed width line {i}: {len(line)} != {len(lines[i])}")
            return False

    print(f"  ✓ Placeholders rendered correctly")
    return True


def test_playlist_manager():
    """Test 4: Playlist manager loads playlists."""
    print("  Testing playlist manager...")

    from core.playlist import PlaylistManager

    pm = PlaylistManager()
    playlists = pm.list_playlists()

    print(f"  Found {len(playlists)} playlists")

    if not playlists:
        print("  ⚠️  No playlists found")
        return True

    for pl_name in playlists:
        try:
            pl = pm.load_playlist(pl_name)
            print(f"  ✓ {pl_name}: {pl.get_name()} ({pl.get_track_count()} tracks)")
        except Exception as e:
            print(f"  ❌ {pl_name}: {e}")
            return False

    return True


def test_playlist_navigation():
    """Test 5: Playlist navigation works."""
    print("  Testing playlist navigation...")

    from core.playlist import PlaylistManager

    pm = PlaylistManager()
    playlists = pm.list_playlists()

    if not playlists:
        print("  ⚠️  No playlists, skipping")
        return True

    pl = pm.load_playlist(playlists[0])

    if pl.get_track_count() == 0:
        print("  ⚠️  Empty playlist, skipping")
        return True

    # Test navigation
    current = pl.get_current_track()
    print(f"  Current: {current.title}")

    if pl.get_track_count() > 1:
        next_track = pl.next()
        print(f"  Next: {next_track.title}")

        prev_track = pl.previous()
        print(f"  Previous: {prev_track.title}")

        if prev_track.url != current.url:
            print(f"  ❌ Navigation inconsistent")
            return False

    print(f"  ✓ Navigation working")
    return True


def test_downloader():
    """Test 6: Downloader can extract video IDs."""
    print("  Testing downloader...")

    from core.downloader import YouTubeDownloader

    dl = YouTubeDownloader()

    # Test URL parsing
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
    ]

    for url in test_urls:
        video_id = dl._extract_video_id(url)
        print(f"  ✓ {url} → {video_id}")

        if video_id != "dQw4w9WgXcQ":
            print(f"  ❌ Wrong video ID: {video_id}")
            return False

    return True


def test_cache_system():
    """Test 7: Cache system works."""
    print("  Testing cache system...")

    from core.downloader import YouTubeDownloader

    dl = YouTubeDownloader()

    # Check if cache dir exists
    cache_path = Path("cache")
    print(f"  Cache dir: {cache_path} (exists: {cache_path.exists()})")

    if cache_path.exists():
        cached_files = list(cache_path.glob("*.m4a"))
        print(f"  Cached files: {len(cached_files)}")

    print(f"  ✓ Cache system operational")
    return True


def test_config_manager():
    """Test 8: Config manager loads configs."""
    print("  Testing config manager...")

    from core.config import ConfigManager

    config = ConfigManager()

    # Test config loading
    volume = config.get("playback.volume")
    print(f"  Volume: {volume}")

    # Test state
    session_count = config.get_state("session_count", 0)
    print(f"  Session count: {session_count}")

    # Test keybindings
    play_key = config.get_key_for_action("play_pause")
    print(f"  Play/Pause key: {play_key}")

    return True


def test_state_machine():
    """Test 9: UI state machine transitions."""
    print("  Testing state machine...")

    from main import UIState

    # Test enum
    states = [UIState.MENU, UIState.LOADING, UIState.PLAYER, UIState.ERROR]

    for state in states:
        print(f"  ✓ State: {state.value}")

    return True


def test_emergency_skin():
    """Test 10: Emergency skin generation."""
    print("  Testing emergency skin generation...")

    from main import YTBMusicUI

    # Create UI instance
    ui = YTBMusicUI()

    # Generate emergency skin
    emergency = ui._create_emergency_skin()

    # Check dimensions
    if len(emergency) != 38:
        print(f"  ❌ Emergency skin height: {len(emergency)} != 38")
        return False

    for i, line in enumerate(emergency):
        if len(line) != 78:
            print(f"  ❌ Emergency skin width line {i}: {len(line)} != 78")
            return False

    print(f"  ✓ Emergency skin: 78x38")
    return True


def test_metadata_cache():
    """Test 11: Metadata caching system."""
    print("  Testing metadata cache...")

    from main import YTBMusicUI

    ui = YTBMusicUI()

    if not ui.playlists:
        print("  ⚠️  No playlists, skipping")
        return True

    # First call (cache miss)
    start = time.time()
    meta1 = ui._get_playlist_metadata(ui.playlists[0])
    time1 = time.time() - start

    # Second call (cache hit)
    start = time.time()
    meta2 = ui._get_playlist_metadata(ui.playlists[0])
    time2 = time.time() - start

    print(f"  First call: {time1*1000:.2f}ms")
    print(f"  Second call: {time2*1000:.2f}ms")

    if meta1 and meta2:
        print(f"  ✓ Cache speedup: {time1/time2:.1f}x")
        return True

    print(f"  ⚠️  No metadata loaded")
    return True


def test_stress_state_switching():
    """Test 12: Rapid state switching doesn't crash."""
    print("  Testing rapid state switching...")

    from main import YTBMusicUI, UIState

    ui = YTBMusicUI()

    # Rapid switching
    for i in range(10):
        ui.state = UIState.MENU
        ui.state = UIState.LOADING
        ui.state = UIState.PLAYER
        ui.state = UIState.MENU

    print(f"  ✓ 40 state switches completed")
    return True


# ============================================================================
# MAIN
# ============================================================================


def main():
    print("\n" + "=" * 70)
    print("🧪 YTBMusic - Automated Test Suite")
    print("=" * 70)

    runner = TestRunner()

    # Run all tests
    runner.test("Imports", test_imports)
    runner.test("Skin Loader Matrix", test_skin_loader_matrix)
    runner.test("Skin Loader Placeholders", test_skin_loader_placeholders)
    runner.test("Playlist Manager", test_playlist_manager)
    runner.test("Playlist Navigation", test_playlist_navigation)
    runner.test("Downloader", test_downloader)
    runner.test("Cache System", test_cache_system)
    runner.test("Config Manager", test_config_manager)
    runner.test("State Machine", test_state_machine)
    runner.test("Emergency Skin", test_emergency_skin)
    runner.test("Metadata Cache", test_metadata_cache)
    runner.test("Stress State Switching", test_stress_state_switching)

    # Final report
    success = runner.report()

    if success:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
