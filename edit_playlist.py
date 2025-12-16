#!/usr/bin/env python3
"""
Interactive Playlist Editor CLI

Usage: python3 edit_playlist.py [playlist_name]
"""

import sys
from pathlib import Path
from core import playlist_editor


def print_header():
    print("\n" + "=" * 60)
    print("  YTBMUSIC - Playlist Editor")
    print("=" * 60 + "\n")


def list_playlists():
    """Show all available playlists."""
    playlists = playlist_editor.list_playlists()
    if not playlists:
        print("  No playlists found in playlists/ directory")
        return None

    print("  Available playlists:")
    for i, name in enumerate(playlists, 1):
        summary = playlist_editor.playlist_summary(name)
        print(f"    [{i}] {summary}")

    return playlists


def select_playlist(playlists):
    """Let user select a playlist."""
    while True:
        choice = input(
            "\n  Select playlist number (or 'n' for new, 'q' to quit): "
        ).strip()

        if choice.lower() == "q":
            return None

        if choice.lower() == "n":
            return create_new_playlist()

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(playlists):
                return playlists[idx]
            else:
                print("  Invalid number!")
        except ValueError:
            print("  Invalid input!")


def create_new_playlist():
    """Create a new playlist."""
    print("\n  Creating new playlist...")
    name = input("  Playlist name: ").strip()
    if not name:
        print("  Cancelled.")
        return None

    description = input("  Description (optional): ").strip()

    try:
        playlist_editor.create_playlist(name, description)
        print(f"  ✓ Created playlist: {name}")
        return name
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def show_tracks(playlist_name):
    """Display all tracks in playlist."""
    tracks = playlist_editor.list_tracks(playlist_name)

    if not tracks:
        print("\n  No tracks in this playlist yet.")
        return

    print(f"\n  Tracks in '{playlist_name}':")
    print("  " + "-" * 56)
    for i, track in enumerate(tracks, 1):
        title = track.get("title", "Unknown")
        artist = track.get("artist", "Unknown")
        tags = track.get("tags", [])
        tags_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"    [{i}] {title} - {artist}{tags_str}")
    print("  " + "-" * 56)


def add_track(playlist_name):
    """Add a new track to playlist with auto-extraction."""
    print("\n  Adding new track...")

    url = input("  YouTube URL: ").strip()
    if not url:
        print("  Cancelled.")
        return

    # Try to auto-extract metadata
    print("  Extracting metadata from YouTube...")
    from core.downloader import YouTubeDownloader

    title = None
    artist = None

    duration = None
    try:
        downloader = YouTubeDownloader()
        metadata = downloader.extract_metadata(url)
        if metadata:
            print(f"\n  Auto-detected:")
            print(f"    Title:  {metadata['title']}")
            print(f"    Artist: {metadata['artist']}")
            dur = metadata.get("duration")
            if dur:
                minutes = dur // 60
                seconds = dur % 60
                print(f"    Duration: {minutes:02d}:{seconds:02d}")

            confirm = input("\n  Use this metadata? (Y/n): ").strip().lower()
            if confirm != "n":
                title = metadata["title"]
                artist = metadata["artist"]
                duration = metadata.get("duration")
    except Exception as e:
        print(f"  Could not auto-extract: {e}")

    # Manual input if auto-extraction failed or user declined
    if not title:
        title = input("\n  Title: ").strip()
        if not title:
            print("  Cancelled.")
            return

    if not artist:
        artist = input("  Artist: ").strip()
        if not artist:
            print("  Cancelled.")
            return

    tags_input = input("  Tags (comma-separated, optional): ").strip()
    tags = [t.strip() for t in tags_input.split(",")] if tags_input else []

    try:
        track = playlist_editor.add_track(
            playlist_name, url, title, artist, tags, duration
        )
        print(f"  ✓ Added: {track['title']} - {track['artist']}")
    except Exception as e:
        print(f"  ✗ Error: {e}")


def delete_track(playlist_name):
    """Delete a track from playlist."""
    tracks = playlist_editor.list_tracks(playlist_name)

    if not tracks:
        print("\n  No tracks to delete.")
        return

    show_tracks(playlist_name)

    choice = input("\n  Track number to delete (or Enter to cancel): ").strip()
    if not choice:
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(tracks):
            track = tracks[idx]
            confirm = input(f"  Delete '{track['title']}'? (y/N): ").strip().lower()
            if confirm == "y":
                if playlist_editor.delete_track(playlist_name, idx):
                    print("  ✓ Track deleted")
                else:
                    print("  ✗ Failed to delete")
        else:
            print("  Invalid track number!")
    except ValueError:
        print("  Invalid input!")


def edit_menu(playlist_name):
    """Show edit menu for a playlist."""
    while True:
        print_header()
        print(f"  Editing: {playlist_name}")
        show_tracks(playlist_name)

        print("\n  Options:")
        print("    [a] Add track")
        print("    [d] Delete track")
        print("    [s] Show tracks")
        print("    [q] Back to main menu")

        choice = input("\n  Choice: ").strip().lower()

        if choice == "q":
            break
        elif choice == "a":
            add_track(playlist_name)
        elif choice == "d":
            delete_track(playlist_name)
        elif choice == "s":
            show_tracks(playlist_name)
        else:
            print("  Invalid choice!")


def main():
    """Main entry point."""
    print_header()

    # If playlist name provided as argument
    if len(sys.argv) > 1:
        playlist_name = sys.argv[1]
        if playlist_name in playlist_editor.list_playlists():
            edit_menu(playlist_name)
        else:
            print(f"  Playlist '{playlist_name}' not found!")
            print(f"  Creating new playlist...")
            if create_new_playlist():
                edit_menu(playlist_name)
        return

    # Interactive mode
    while True:
        playlists = list_playlists()
        if playlists is None:
            print("\n  Create a playlist first!")
            if create_new_playlist():
                playlists = list_playlists()
            else:
                break

        if playlists:
            playlist_name = select_playlist(playlists)
            if playlist_name:
                edit_menu(playlist_name)
            else:
                break


if __name__ == "__main__":
    main()
