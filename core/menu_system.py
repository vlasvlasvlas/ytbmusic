import sys
from typing import Optional
from core import playlist_editor


def prompt(message: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{message}{suffix}: ").strip() or (default or "")


def main_menu() -> str:
    print("\n" + "=" * 50)
    print(" Y T B M U S I C   -   M A I N   M E N U")
    print("=" * 50)
    print("1) Play music")
    print("2) Manage playlists")
    print("3) Add track (manual URL)")
    print("4) Quit")
    choice = input("\nSelect option (1-4): ").strip()
    if choice == "1":
        return "play"
    if choice == "2":
        return "manage"
    if choice == "3":
        return "add"
    return "quit"


def manage_playlists():
    while True:
        names = playlist_editor.list_playlists()
        print("\nPlaylists:")
        if names:
            for i, name in enumerate(names, 1):
                print(f"  {i}) {playlist_editor.playlist_summary(name)}")
        else:
            print("  (none)")

        print("\nActions: [N]ew  [D]elete  [B]ack")
        choice = input("Choose action: ").strip().lower()

        if choice == "n":
            name = prompt("New playlist name")
            if not name:
                continue
            desc = prompt("Description", "")
            playlist_editor.create_playlist(name, desc)
            print(f"Created playlist '{name}'.")
        elif choice == "d":
            idx = prompt("Enter playlist number to delete")
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(names):
                    playlist_editor.delete_playlist(names[idx])
                    print(f"Deleted '{names[idx]}'.")
        else:
            break


def add_track_manual():
    names = playlist_editor.list_playlists()
    if not names:
        print("No playlists found. Create one first in Manage playlists.")
        return
    print("\nSelect playlist to add track:")
    for i, name in enumerate(names, 1):
        print(f"  {i}) {playlist_editor.playlist_summary(name)}")
    sel = input("Playlist number: ").strip()
    if not sel.isdigit():
        return
    idx = int(sel) - 1
    if idx < 0 or idx >= len(names):
        return
    pl = names[idx]
    url = prompt("Track URL")
    title = prompt("Title", "Untitled")
    artist = prompt("Artist", "Unknown Artist")
    if url:
        playlist_editor.add_track(pl, title, artist, url)
        print(f"Added '{title}' to '{pl}'.")
    else:
        print("No URL provided.")

