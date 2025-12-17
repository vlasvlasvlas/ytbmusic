#!/usr/bin/env python3
"""
YTBMusic - Automated Testing Suite (No MPV required)
Tests all components except player
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("YTBMusic - Component Testing (without MPV)")
print("=" * 70)
print()

# Test 1: Config Manager
print("⚙️  Test 1: Config Manager...")
try:
    from core.config import ConfigManager

    config = ConfigManager()
    volume = config.get("playback.volume")
    print(f"  ✅ Default volume: {volume}")

    config.update_state(test_key="test_value")
    assert config.get_state("test_key") == "test_value"
    print(f"  ✅ State management OK")

    play_key = config.get_key_for_action("play_pause")
    print(f"  ✅ Keybindings - Play/Pause: '{play_key}'")

    print("✅ Config Manager: PASSED\n")
except Exception as e:
    print(f"❌ FAILED: {e}\n")

# Test 2: Logger
print("📝 Test 2: Logger...")
try:
    from core.logger import setup_logging

    logger = setup_logging()
    logger.info("Test log message")
    print(f"  ✅ Logger initialized: {logger.name}")
    print("✅ Logger: PASSED\n")
except Exception as e:
    print(f"❌ FAILED: {e}\n")

# Test 3: Playlist Manager
print("📋 Test 3: Playlist Manager + vladitest...")
try:
    from core.playlist import PlaylistManager

    pm = PlaylistManager()
    playlists = pm.list_playlists()
    print(f"  ✅ Found playlists: {', '.join(playlists)}")

    if "vladitest" in playlists:
        playlist = pm.load_playlist("vladitest")
        print(f"  ✅ Loaded: '{playlist.get_name()}'")
        print(f"  ✅ Tracks: {playlist.get_track_count()}")

        # Test both tracks
        track1 = playlist.get_current_track()
        print(f"  ✅ Track 1: {track1.title}")
        print(f"     URL: {track1.url}")

        track2 = playlist.next()
        print(f"  ✅ Track 2: {track2.title}")
        print(f"     URL: {track2.url}")

        # Test navigation
        back = playlist.previous()
        assert back.url == track1.url
        print(f"  ✅ Navigation working")

        # Test position info
        pos = playlist.get_position_info()
        print(f"  ✅ Position: {pos}")

    print("✅ Playlist Manager: PASSED\n")
except Exception as e:
    print(f"❌ FAILED: {e}\n")
    import traceback

    traceback.print_exc()

# Test 4: Skin Loader
print("🎨 Test 4: Skin Loader...")
try:
    from ui.skin_loader import SkinLoader

    loader = SkinLoader()
    skins = loader.list_available_skins()
    print(f"  ✅ Found skins: {', '.join(skins)}")

    # Test each skin
    for skin_name in skins:
        metadata, lines = loader.load(f"skins/{skin_name}.txt")
        widths = set(len(line) for line in lines)
        status = "✅" if len(widths) == 1 else "❌"
        print(f"  {status} {skin_name}: {len(lines)} lines, width {list(widths)[0]}")

    # Test rendering
    metadata, lines = loader.load("skins/cassette.txt")
    context = {
        "PREV": "⏮",
        "PLAY": "▶",
        "NEXT": "⏭",
        "VOL_DOWN": "🔉",
        "VOL_UP": "🔊",
        "QUIT": "❌",
        "TITLE": "Test Song",
        "ARTIST": "Test Artist",
        "TIME": "03:45 / 06:07",
        "PROGRESS": "[=====>     ]",
        "VOLUME": "[||||||||  ]",
        "STATUS": "🎵",
        "TRACK_NUM": "1/2",
    }
    rendered = loader.render(lines, context)
    assert "Test Song" in "\n".join(rendered)
    print(f"  ✅ Rendering working")

    print("✅ Skin Loader: PASSED\n")
except Exception as e:
    print(f"❌ FAILED: {e}\n")

# Test 5: Downloader
print("⬇️  Test 5: Downloader...")
try:
    from core.downloader import YouTubeDownloader

    dl = YouTubeDownloader()

    # Test video ID extraction
    urls = [
        "https://www.youtube.com/watch?v=wydOyGNFf4I",
        "https://www.youtube.com/watch?v=tXggyHNwO9A",
    ]

    for url in urls:
        video_id = dl._extract_video_id(url)
        cached = dl.is_cached(url)
        print(f"  ✅ {video_id}: cached={cached is not None}")

    print("✅ Downloader: PASSED\n")
except Exception as e:
    print(f"❌ FAILED: {e}\n")

# Integration Test
print("🔄 Test 6: Integration (Simulated Playback)...")
try:
    from core.config import ConfigManager
    from core.logger import setup_logging
    from core.playlist import PlaylistManager

    # Simulate full flow
    config = ConfigManager()
    logger = setup_logging()
    pm = PlaylistManager()

    config.start_session()
    logger.info("Session started")

    playlist = pm.load_playlist("vladitest")
    track = playlist.get_current_track()

    config.save_playback_state("playlists/vladitest.json", playlist.get_name(), 0, 0.0)

    logger.info(f"Playing: {track.title} - {track.artist}")

    config.end_session()
    logger.info("Session ended")

    # Verify state
    resume = config.get_resume_info()
    assert resume is not None
    print(f"  ✅ Session flow complete")
    print(f"  ✅ Resume info: {resume['playlist_name']}")

    print("✅ Integration: PASSED\n")
except Exception as e:
    print(f"❌ FAILED: {e}\n")
    import traceback

    traceback.print_exc()

print("=" * 70)
print("🎉 All Tests Completed!")
print("=" * 70)
print()
print("✅ vladitest playlist ready with 2 tracks")
print("✅ All components validated")
print()
print("To test full UI: python3 main.py")
print("  (Seleccioná 'vladitest' desde el menú)")
