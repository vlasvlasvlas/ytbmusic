#!/usr/bin/env python3
"""
Import a YouTube playlist into ytbmusic playlists/ as JSON (metadata only).

Usage:
    python3 import_youtube_playlist.py <playlist_url> [playlist_name] [--overwrite] [--download]

Prompts a confirmation showing first items and stats.
"""

import sys
from core.playlist_editor import import_playlist_from_youtube
from core.playlist_editor import list_playlists
from core.downloader import YouTubeDownloader


def preview(url: str, info: dict, max_items: int = 5):
    print("\n--- Playlist Preview ---")
    print(f"Source: {info.get('source', url)}")
    print(f"Title:  {info.get('title', 'Imported Playlist')}")
    print(f"Items:  {info.get('count', len(info.get('items', [])))} total")
    items = info.get("items", [])[:max_items]
    if items:
        print("\nFirst items:")
        for i, item in enumerate(items, 1):
            dur = item.get("duration") or 0
            mm = dur // 60
            ss = dur % 60
            print(
                f"  {i:2d}. {item.get('title','Unknown')} - {item.get('artist','Unknown Artist')} ({mm:02d}:{ss:02d})"
            )
    print("------------------------\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    url = sys.argv[1]
    playlist_name = None
    overwrite = False
    download_after = False
    if len(sys.argv) >= 3:
        playlist_name = sys.argv[2]
    if "--overwrite" in sys.argv:
        overwrite = True
    if "--download" in sys.argv:
        download_after = True

    from core.downloader import YouTubeDownloader

    yd = YouTubeDownloader()
    info = yd.extract_playlist_items(url)

    preview(url, info)

    target_name = playlist_name or info.get("title") or "Imported Playlist"
    if not overwrite and target_name in list_playlists():
        print(
            f"Playlist '{target_name}' exists. Pass --overwrite to replace or choose another name."
        )
        return

    confirm = input(f"Import into '{target_name}'? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    result = import_playlist_from_youtube(
        url, playlist_name=target_name, overwrite=overwrite
    )
    print(
        f"Imported '{result['name']}': added {result['added']} tracks, skipped {result['skipped']} (existing)."
    )

    if download_after and result.get("added_items"):
        print("\nDownloading added tracks...")
        yd = YouTubeDownloader()
        added = result["added_items"]
        total = len(added)
        failures = 0

        for idx, item in enumerate(added, 1):
            title = item.get("title", "Unknown")
            track_url = item.get("url")

            def hook(percent, downloaded, total_bytes):
                print(f"\r[{idx}/{total}] {title[:40]:40}  {percent:5.1f}%", end="")

            try:
                yd.download(track_url, progress_callback=hook)
                print("")  # newline after each track
            except Exception as e:
                failures += 1
                print(f"\nFailed: {title} ({e})")

        print(f"\nDownload summary: {total - failures} ok, {failures} failed.")


if __name__ == "__main__":
    main()
