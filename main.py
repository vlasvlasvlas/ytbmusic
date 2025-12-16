import urwid
import time
import signal
import shutil
import threading
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional

from core.player import MusicPlayer, PlayerState
from core.downloader import YouTubeDownloader
from core.playlist import PlaylistManager
from core.playlist_editor import (
    import_playlist_from_youtube,
    list_playlists,
    get_missing_tracks,
)
from core import playlist_editor
from core.logger import setup_logging
from ui.skin_loader import SkinLoader

logger = setup_logging()


HELP_TEXT = "Space=Play/Pause N/P=Next/Prev ←/→=Seek ↑/↓=Vol S=Skin Z=Shuffle R=Repeat M=Menu Q=Quit"
PAD_WIDTH = 120
PAD_HEIGHT = 88


class UIState(Enum):
    MENU = "menu"
    LOADING = "loading"
    PLAYER = "player"
    ERROR = "error"
    EDIT = "edit"


@dataclass
class PlaylistMetadata:
    name: str
    track_count: int
    loaded_at: float


@dataclass
class SkinMetadata:
    name: str
    author: str
    loaded_at: float


def pad_lines(lines, width=PAD_WIDTH, height=PAD_HEIGHT):
    padded = []
    for line in lines:
        line = line.rstrip("\n")
        if len(line) > width:
            line = line[:width]
        if len(line) < width:
            line = line + " " * (width - len(line))
        padded.append(line)
    while len(padded) < height:
        padded.append(" " * width)
    return padded[:height]


class SkinWidget(urwid.WidgetWrap):
    def __init__(self):
        self.text = urwid.Text("", align="left")
        super().__init__(urwid.Filler(self.text, valign="top"))

    def update(self, text):
        self.text.set_text(text)


class StatusBar(urwid.WidgetWrap):
    """Three-line status bar: notification (optional) + context + shortcuts."""

    SHORTCUTS = "Space=⏯  N/P=⏭⏮  ↑↓=Vol  ←→=Seek  S=Skin  M=Menu  Q=Quit"

    def __init__(self, context_text):
        self.notification = urwid.Text("", align="center")
        self.context = urwid.Text(context_text, align="center")
        self.shortcuts = urwid.Text(self.SHORTCUTS, align="center")
        self.pile = urwid.Pile(
            [
                urwid.AttrWrap(self.notification, "status"),
                urwid.AttrWrap(self.context, "status"),
                urwid.AttrWrap(self.shortcuts, "status"),
            ]
        )
        super().__init__(self.pile)

    def set(self, text):
        """Set the context message (middle line)."""
        self.context.set_text(text)

    def notify(self, text):
        """Set the notification (top line) - for downloads, alerts, etc."""
        self.notification.set_text(text)

    def clear_notify(self):
        """Clear the notification line."""
        self.notification.set_text("")


class MenuListBox(urwid.ListBox):
    """ListBox that passes certain hotkeys through to unhandled_input."""

    # Keys that should NOT be handled by the ListBox
    PASSTHROUGH_KEYS = (
        "i",
        "I",
        "d",
        "D",
        "q",
        "Q",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "a",
        "A",
        "b",
        "B",
        "c",
        "C",
        "e",
        "E",
        "f",
        "F",
        "g",
        "G",
        "h",
        "H",
        "j",
        "J",
    )

    def keypress(self, size, key):
        if key in self.PASSTHROUGH_KEYS:
            return key  # Pass through to unhandled_input
        return super().keypress(size, key)


class InputDialog(urwid.WidgetWrap):
    """ASCII-styled input dialog for retro aesthetic."""

    def __init__(self, title, label, callback):
        self.callback = callback
        self.edit = urwid.Edit(f"  {label}: ")

        # ASCII box art header
        header_art = [
            "╔════════════════════════════════════════════════════════╗",
            f"║  {title:^54}  ║",
            "╠════════════════════════════════════════════════════════╣",
        ]

        footer_art = [
            "╠════════════════════════════════════════════════════════╣",
            "║     [Enter] Confirm            [Esc] Cancel            ║",
            "╚════════════════════════════════════════════════════════╝",
        ]

        body_widgets = []
        for line in header_art:
            body_widgets.append(urwid.Text(line))
        body_widgets.append(
            urwid.Text("║                                                          ║")
        )
        body_widgets.append(
            urwid.Columns(
                [
                    ("fixed", 2, urwid.Text("║ ")),
                    self.edit,
                    ("fixed", 2, urwid.Text(" ║")),
                ]
            )
        )
        body_widgets.append(
            urwid.Text("║                                                          ║")
        )
        for line in footer_art:
            body_widgets.append(urwid.Text(line))

        pile = urwid.Pile(body_widgets)
        fill = urwid.Filler(pile, valign="middle")
        super().__init__(fill)

    def keypress(self, size, key):
        if key == "enter":
            self.callback(self.edit.get_edit_text())
            return None  # Key handled
        elif key == "esc":
            self.callback(None)
            return None  # Key handled
        else:
            # Let the edit widget handle the key
            return super().keypress(size, key)


class YTBMusicUI:
    def __init__(self):
        # Core components
        self.player = MusicPlayer()
        self.player.on_end_callback = self._on_track_end_callback
        self.downloader = YouTubeDownloader(cache_dir="cache")
        self.playlist_manager = PlaylistManager(playlists_dir="playlists")
        self.skin_loader = SkinLoader()

        # State management
        self.state = UIState.MENU
        self.previous_state = None
        self.spinner_alarm = None
        self.refresh_alarm = None

        # Selection state
        self.selected_playlist_idx = None

        # Load resources
        self.playlists = list_playlists()
        self.skins = SkinLoader.list_available_skins()

        # Skins (only those that fit canvas)
        self.current_skin_idx = 0
        self.skin_lines = []
        self._loading_skin = False

        # Playlists
        self.playlists = self.playlist_manager.list_playlists()
        self.current_playlist_idx = 0
        self.current_playlist = None
        self.consecutive_errors = 0

        # Caching
        self.playlist_cache: Dict[str, PlaylistMetadata] = {}
        self.skin_cache: Dict[str, SkinMetadata] = {}
        self.cache_ttl = 300  # 5 minutes

        # UI state
        self.refresh_alarm = None
        self.spinner_alarm = None
        self.spinner_frame = 0
        self.loading_message = ""
        self.is_cached_playback = False

        # Widgets
        self.skin_widget = SkinWidget()
        self.menu_widget = None
        self.loading_widget = None
        self.status = StatusBar("")
        self.main_widget = urwid.WidgetPlaceholder(urwid.Text("Initializing..."))
        frame = urwid.Frame(body=self.main_widget, footer=self.status)

        self.loop = urwid.MainLoop(
            frame,
            unhandled_input=self.unhandled_input,
            palette=[
                ("status", "black", "dark cyan"),
                ("title", "yellow,bold", ""),
                ("highlight", "black", "dark cyan"),
                ("normal", "", ""),
                ("error", "light red,bold", ""),
                ("success", "light green", ""),
                ("info", "light blue", ""),
            ],
        )

        signal.signal(signal.SIGWINCH, self._handle_resize)

    # ---------- utilities ----------
    def _handle_resize(self, signum, frame):
        if self.state == UIState.PLAYER:
            self._render_skin()
        self.loop.draw_screen()

    def _get_playlist_metadata(self, name: str) -> Optional[PlaylistMetadata]:
        if name in self.playlist_cache:
            meta = self.playlist_cache[name]
            if time.time() - meta.loaded_at < self.cache_ttl:
                return meta
        try:
            pl = self.playlist_manager.load_playlist(name)
            meta = PlaylistMetadata(
                name=pl.get_name(),
                track_count=pl.get_track_count(),
                loaded_at=time.time(),
            )
            self.playlist_cache[name] = meta
            return meta
        except Exception:
            return None

    def _get_skin_metadata(self, name: str) -> Optional[SkinMetadata]:
        if name in self.skin_cache:
            meta = self.skin_cache[name]
            if time.time() - meta.loaded_at < self.cache_ttl:
                return meta
        try:
            skin_path = Path("skins") / f"{name}.txt"
            loader = SkinLoader()
            skin_meta, _ = loader.load(str(skin_path))
            meta = SkinMetadata(
                name=skin_meta.get("name", name),
                author=skin_meta.get("author", "Unknown"),
                loaded_at=time.time(),
            )
            self.skin_cache[name] = meta
            return meta
        except Exception:
            return None

    def _count_downloaded_tracks(self, playlist_name: str) -> tuple[int, int]:
        """
        Count downloaded tracks for a playlist.
        Returns (downloaded_count, total_count).
        """
        try:
            # We need to peek into the playlist without fully loading it as the current object
            mgr = PlaylistManager()
            pl = mgr.load_playlist(playlist_name)

            total = len(pl.tracks)
            downloaded = 0

            for track in pl.tracks:
                if self.downloader.is_cached(track.url):
                    downloaded += 1

            return downloaded, total
        except Exception:
            return 0, 0

    # ---------- UI builders ----------
    def _create_menu(self):
        items = []

        # Title Art
        title = [
            "",
            "  ________  ________  ________  _______   ________  ________   ________  ________ ",
            " ╱    ╱   ╲╱        ╲╱       ╱ ╱       ╲╲╱    ╱   ╲╱        ╲ ╱        ╲╱        ╲",
            "╱         ╱        _╱        ╲╱        ╱╱         ╱        _╱_╱       ╱╱         ╱",
            "╲__     ╱╱╱       ╱╱         ╱         ╱         ╱-        ╱╱         ╱       --╱ ",
            "  ╲____╱╱ ╲______╱ ╲________╱╲__╱__╱__╱╲________╱╲________╱ ╲________╱╲________╱  ",
            "",
        ]
        for line in title:
            items.append(urwid.Text(line, align="center"))

        self.menu_walker = urwid.SimpleFocusListWalker(items)
        self.menu_walker.append(urwid.Text(""))
        self.menu_walker.append(urwid.Divider("═"))
        self.menu_walker.append(
            urwid.AttrMap(
                urwid.Text("  ♪  SELECT PLAYLIST (1-9)", align="left"), "title"
            )
        )
        self.menu_walker.append(urwid.Divider("─"))

        if not self.playlists:
            self.menu_walker.append(urwid.Text(""))
            self.menu_walker.append(
                urwid.AttrMap(
                    urwid.Text("     No playlists found!", align="center"), "error"
                )
            )
            self.menu_walker.append(
                urwid.Text("     Add .json files to playlists/ folder", align="center")
            )
        else:
            for i, pl_name in enumerate(self.playlists[:9]):
                meta = self._get_playlist_metadata(pl_name)

                # Get download stats
                down_count, total_count = self._count_downloaded_tracks(pl_name)

                if meta:
                    display = f"    [{i+1}] {meta.name} ({down_count}/{total_count} downloaded)"
                else:
                    display = f"    [{i+1}] {pl_name} ({down_count}/{total_count})"

                # Highlight selected
                style = None
                if i == self.selected_playlist_idx:
                    display += "  ← SELECTED"
                    style = "highlight"

                btn = urwid.Button(display)
                urwid.connect_signal(
                    btn, "click", lambda b, idx=i: self._on_playlist_select(b, idx)
                )
                self.menu_walker.append(
                    urwid.AttrMap(btn, style, focus_map="highlight")
                )

        # Actions for selected playlist
        if self.selected_playlist_idx is not None and self.selected_playlist_idx < len(
            self.playlists
        ):

            self.menu_walker.append(urwid.Divider(" "))
            self.menu_walker.append(
                urwid.Text("      Actions for selected:", align="left")
            )

            # PLAY Button
            play_btn = urwid.Button(f"      [P] PLAY NOW")
            urwid.connect_signal(play_btn, "click", lambda b: self._on_play_selected())
            self.menu_walker.append(
                urwid.AttrMap(play_btn, None, focus_map="highlight")
            )

            # DELETE Button
            del_btn = urwid.Button(f"      [X] DELETE PLAYLIST")
            urwid.connect_signal(del_btn, "click", lambda b: self._on_delete_selected())
            self.menu_walker.append(urwid.AttrMap(del_btn, None, focus_map="highlight"))

        self.menu_walker.append(urwid.Text(""))
        self.menu_walker.append(urwid.Divider("═"))

        # Import button
        import_btn = urwid.Button("    [I] Import from YouTube")
        urwid.connect_signal(
            import_btn, "click", lambda b: self._prompt_import_playlist()
        )
        self.menu_walker.append(urwid.AttrMap(import_btn, None, focus_map="highlight"))

        self.menu_walker.append(urwid.Divider(" "))
        self.menu_walker.append(
            urwid.AttrMap(urwid.Text("  🎨  SELECT SKIN (A-J)", align="left"), "title")
        )
        self.menu_walker.append(urwid.Divider("─"))

        if not self.skins:
            self.menu_walker.append(
                urwid.AttrMap(
                    urwid.Text("     No skins found!", align="center"), "error"
                )
            )
            self.menu_walker.append(
                urwid.Text("     Add .txt files to skins/ folder", align="center")
            )
        else:
            letters = "ABCDEFGHIJ"
            for i, skin_name in enumerate(self.skins[:10]):
                meta = self._get_skin_metadata(skin_name)
                display = f"    [{letters[i]}] {meta.name if meta else skin_name}"
                if i == self.current_skin_idx:
                    display += " ← Current"
                btn = urwid.Button(display)
                urwid.connect_signal(
                    btn, "click", lambda b, idx=i: self._on_skin_select(b, idx)
                )
                self.menu_walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))

        self.menu_walker.append(urwid.Text(""))
        self.menu_walker.append(
            urwid.AttrMap(
                urwid.Text(
                    "  ↑/↓ Navigate  •  Enter Select  •  Q Quit", align="center"
                ),
                "status",
            )
        )

        return MenuListBox(self.menu_walker)

    def _create_loading_widget(self, message: str):
        frames = ["◐", "◓", "◑", "◒"]  # Spinning circle
        spinner = frames[self.spinner_frame % len(frames)]

        # Truncate message to fit
        msg = message[:48]

        loading_art = [
            "",
            "",
            "╔══════════════════════════════════════════════════════════╗",
            "║                                                          ║",
            f"║    {spinner}  {msg:<51}║",
            "║                                                          ║",
            "║         Please wait... YouTube can be slow.              ║",
            "║                                                          ║",
            "║            Press [Q] to quit  •  [M] for menu            ║",
            "╚══════════════════════════════════════════════════════════╝",
            "",
            "",
        ]
        return urwid.Filler(
            urwid.Pile([urwid.Text(line, align="center") for line in loading_art]),
            valign="middle",
        )

    # ---------- state switches ----------
    def _animate_loading(self, loop, data):
        if self.state != UIState.LOADING:
            return
        self.spinner_frame = (self.spinner_frame + 1) % 10
        self.loading_widget = self._create_loading_widget(self.loading_message)
        self.main_widget.original_widget = self.loading_widget
        self.spinner_alarm = loop.set_alarm_in(0.1, self._animate_loading)

    def _switch_to_loading(self, message: str):
        self.previous_state = self.state
        self.state = UIState.LOADING
        self.loading_message = message
        self.spinner_frame = 0
        if self.refresh_alarm:
            self.loop.remove_alarm(self.refresh_alarm)
            self.refresh_alarm = None
        self.loading_widget = self._create_loading_widget(message)

        # If we are in an overlay (input dialog), restore main widget first
        if isinstance(self.main_widget.original_widget, urwid.Overlay):
            if hasattr(self, "menu_widget") and self.menu_widget:
                self.main_widget.original_widget = self.menu_widget

        self.main_widget.original_widget = self.loading_widget
        self.spinner_alarm = self.loop.set_alarm_in(0.1, self._animate_loading)
        self.status.set("Loading... Please wait")

    def _show_input_dialog(self, title, label, callback):
        """Show a modal input dialog."""

        def on_done(text):
            # Restore previous widget
            self.main_widget.original_widget = self.menu_widget
            callback(text)

        dialog = InputDialog(title, label, on_done)
        overlay = urwid.Overlay(
            dialog,
            self.menu_widget,
            align="center",
            width=60,
            valign="middle",
            height=10,
        )
        self.main_widget.original_widget = overlay

    def _start_batch_download(self, tracks: list):
        """Start recursive batch download of missing tracks."""
        if not tracks:
            self.status.set("All tracks downloaded! ✓")
            self._switch_to_menu()
            return

        total = len(tracks)

        def download_next(remaining):
            if not remaining:
                self.status.set("Download complete! ✓")
                self._switch_to_menu()
                return

            track = remaining[0]
            current_idx = total - len(remaining) + 1

            msg = f"Downloading {current_idx}/{total}: {track.get('title', 'Unknown')[:30]}"
            self.loading_message = msg

            def hook(percent, downloaded, total_bytes):
                self._update_loading_message(f"{msg} ({percent:.1f}%)")

            # Perform download in a non-blocking way (loop alarm trick)
            # Since requests are blocking, we still block UI but update text between tracks
            # Ideally we'd use threads, but keep it simple for now as requested
            try:
                self.loop.draw_screen()  # Force repaint
                self.downloader.download(track["url"], progress_callback=hook)
            except Exception as e:
                print(f"Failed to download {track.get('title')}: {e}")

            # Schedule next
            self.loop.set_alarm_in(0.1, lambda l, d: download_next(remaining[1:]))

        self._switch_to_loading(f"Starting download of {total} tracks...")
        self.loop.set_alarm_in(0.5, lambda l, d: download_next(tracks))

    def _update_loading_message(self, message: str):
        """Update loading message (e.g., download percentage)."""
        self.loading_message = message
        if self.state == UIState.LOADING:
            self.loading_widget = self._create_loading_widget(self.loading_message)
            self.main_widget.original_widget = self.loading_widget
            # Force immediate redraw
            try:
                self.loop.draw_screen()
            except Exception:
                pass

    def _switch_to_menu(self):
        self.state = UIState.MENU
        self.player.stop()
        if self.refresh_alarm:
            self.loop.remove_alarm(self.refresh_alarm)
            self.refresh_alarm = None
        if self.spinner_alarm:
            self.loop.remove_alarm(self.spinner_alarm)
            self.spinner_alarm = None
        self.playlists = self.playlist_manager.list_playlists()
        self.menu_widget = self._create_menu()
        self.main_widget.original_widget = self.menu_widget

        # Always set context message
        if self.playlists and self.skins:
            self.status.set("Select playlist (1-9) or skin (A-J) • Q to quit")
        else:
            self.status.set("Add playlists and skins to get started")

        # Show download notification if active
        if getattr(self, "bg_download_active", False):
            curr = getattr(self, "bg_download_current", 0)
            total = getattr(self, "bg_download_total", 0)
            self.status.notify(f"⬇️ Downloading: {curr}/{total}")
        else:
            self.status.clear_notify()

    def _switch_to_player(self):
        self.state = UIState.PLAYER
        if self.spinner_alarm:
            self.loop.remove_alarm(self.spinner_alarm)
            self.spinner_alarm = None
        self.main_widget.original_widget = self.skin_widget
        if self.refresh_alarm:
            self.loop.remove_alarm(self.refresh_alarm)
        self.refresh_alarm = self.loop.set_alarm_in(0.2, self.refresh)

    # ---------- helpers ----------
    def _handle_error(self, error: Exception, context: str = ""):
        error_msg = str(error)[:60]
        self.status.set(f"❌ Error: {error_msg} • Press M for menu")
        print(f"ERROR [{context}]: {error}")
        import traceback

        traceback.print_exc()

    def _safe_call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self._handle_error(e, context=func.__name__)
            return None

    def _prompt_import_playlist(self):
        """Show dialog to import a YouTube playlist."""

        def on_url_entered(url):
            if not url:
                return

            def on_name_entered(name):
                self._switch_to_loading("Contacting YouTube...")
                self.loop.draw_screen()

                # Run import in background thread
                def threaded_import():
                    try:
                        logger.info(f"[THREAD] Starting import for URL: {url}")

                        result = import_playlist_from_youtube(
                            url, playlist_name=name or None, overwrite=False
                        )
                        logger.info(
                            f"[THREAD] Import result: {result['name']}, added={result['added']}"
                        )

                        # Schedule UI update in main thread
                        self.loop.set_alarm_in(
                            0, lambda l, d: self._on_import_complete(result)
                        )

                    except Exception as e:
                        logger.error(f"[THREAD] Import error: {e}")
                        self.loop.set_alarm_in(
                            0, lambda l, d: self._on_import_error(str(e))
                        )

                self.import_thread = threading.Thread(
                    target=threaded_import, daemon=True
                )
                self.import_thread.start()

                # Start polling for thread completion
                self.loop.set_alarm_in(0.5, self._check_import_thread)

            self._show_input_dialog("Playlist Name (Optional)", "Name", on_name_entered)

        self._show_input_dialog(
            "Import YouTube Playlist", "Playlist URL", on_url_entered
        )

    def _check_import_thread(self, loop=None, user_data=None):
        """Poll import thread status."""
        if hasattr(self, "import_thread") and self.import_thread.is_alive():
            # Still running, keep polling
            self.spinner_frame += 1
            self._update_loading_message("Fetching playlist from YouTube...")
            self.loop.set_alarm_in(0.3, self._check_import_thread)

    def _on_import_complete(self, result):
        """Called when import thread finishes successfully."""
        self.playlists = list_playlists()

        if result["added"] == 0 and result["skipped"] > 0:
            self.status.set(
                f"Playlist '{result['name']}' up-to-date ({result['skipped']} tracks)"
            )
            self._switch_to_menu()
            return

        # Start downloading first track in thread
        pl_name = result["name"]
        missing = get_missing_tracks(pl_name)

        if not missing:
            self._load_playlist_by_name(pl_name)
            self._switch_to_player()
            self.loop.set_alarm_in(0.3, lambda l, d: self._start_playback())
            return

        # Download first track in thread, then play
        self._download_first_and_play(pl_name, missing)

    def _on_import_error(self, error_msg):
        """Called when import thread fails."""
        self._handle_error(Exception(error_msg), "import_playlist")
        self._switch_to_menu()

    def _download_first_and_play(self, pl_name, missing_tracks):
        """Download first track in thread, start playback, then bg download rest."""
        first_track = missing_tracks[0]
        self._update_loading_message(
            f"Downloading: {first_track.get('title', 'Unknown')[:35]}"
        )

        def download_first():
            try:
                logger.info(
                    f"[THREAD] Downloading first track: {first_track.get('title')}"
                )
                self.downloader.download(first_track["url"])
                logger.info(f"[THREAD] First track done!")
                self.loop.set_alarm_in(
                    0,
                    lambda l, d: self._on_first_download_complete(
                        pl_name, missing_tracks[1:]
                    ),
                )
            except Exception as e:
                logger.error(f"[THREAD] First track failed: {e}")
                self.loop.set_alarm_in(
                    0,
                    lambda l, d: self._on_first_download_complete(
                        pl_name, missing_tracks[1:]
                    ),
                )

        self.download_thread = threading.Thread(target=download_first, daemon=True)
        self.download_thread.start()
        self.loop.set_alarm_in(0.5, self._check_download_thread)

    def _check_download_thread(self, loop=None, user_data=None):
        """Poll download thread status."""
        if hasattr(self, "download_thread") and self.download_thread.is_alive():
            self.spinner_frame += 1
            self.loop.set_alarm_in(0.3, self._check_download_thread)

    def _on_first_download_complete(self, pl_name, remaining_tracks):
        """Start playback and background downloads."""
        self._load_playlist_by_name(pl_name)
        self._switch_to_player()
        self.loop.set_alarm_in(0.3, lambda l, d: self._start_playback())

        if remaining_tracks:
            self._start_background_downloads(remaining_tracks)

    def _load_playlist_by_name(self, name: str):
        """Load a playlist by name and set as current."""
        idx = self.playlists.index(name) if name in self.playlists else 0
        self._load_playlist(idx, auto_play=False)

    def _start_background_downloads(self, tracks: list):
        """Download tracks in background using alarms (non-blocking feel)."""
        if not tracks:
            return

        self.bg_download_queue = tracks.copy()
        self.bg_download_total = len(tracks)
        self.bg_download_current = 0
        self.bg_download_failures = []
        self.bg_download_active = True

        # Start first background download after a delay
        self.loop.set_alarm_in(2.0, self._bg_download_next)

    def _cancel_background_downloads(self):
        """Cancel any ongoing background downloads."""
        self.bg_download_active = False
        self.bg_download_queue = []
        logger.info("[BG] Downloads cancelled")

    def _bg_download_next(self, loop=None, user_data=None):
        """Download next track in background queue using a thread."""
        # Check if cancelled or queue empty
        if not getattr(self, "bg_download_active", False):
            return
        if not self.bg_download_queue:
            self._bg_download_complete()
            return

        track = self.bg_download_queue.pop(0)
        self.bg_download_current += 1
        title = track.get("title", "Unknown")[:20]
        playlist = track.get("_playlist", "")[:15]

        # Update notification line (top) for download progress
        prefix = f"[{playlist}] " if playlist else ""
        self.status.notify(
            f"⬇️ {self.bg_download_current}/{self.bg_download_total}: {prefix}{title}"
        )

        # Progress callback for real-time percentage updates
        def on_progress(percent, downloaded, total):
            self.status.notify(
                f"⬇️ {self.bg_download_current}/{self.bg_download_total}: {prefix}{title} ({percent:.0f}%)"
            )

        # Download in a thread
        def do_download():
            try:
                self.downloader.download(track["url"], progress_callback=on_progress)
                logger.info(f"[BG] ✓ Downloaded: {title}")
                # Refresh menu if in menu state to update download counts
                if self.state == UIState.MENU:
                    self.loop.set_alarm_in(0, lambda l, d: self._refresh_menu_counts())
            except Exception as e:
                self.bg_download_failures.append(track)
                logger.error(f"[BG] ✗ Failed: {title} - {e}")

            # Schedule next download in main thread
            if self.bg_download_queue and getattr(self, "bg_download_active", False):
                self.loop.set_alarm_in(0.1, self._bg_download_next)
            else:
                self.loop.set_alarm_in(0.1, lambda l, d: self._bg_download_complete())

        self.bg_thread = threading.Thread(target=do_download, daemon=True)
        self.bg_thread.start()

    def _bg_download_complete(self):
        """Called when background downloads finish."""
        self.bg_download_active = False
        failed = len(getattr(self, "bg_download_failures", []))
        total = getattr(self, "bg_download_total", 0)

        if failed > 0:
            self.status.notify(
                f"✓ Done: {total - failed}/{total} tracks ({failed} failed)"
            )
        else:
            self.status.notify(f"✓ All {total} tracks downloaded!")

        # Clear notification after 5 seconds
        self.loop.set_alarm_in(5.0, lambda l, d: self.status.clear_notify())

        logger.info(f"[BG] Complete: {total - failed}/{total} success, {failed} failed")

    def _on_download_all(self):
        """Trigger download of all missing tracks in current playlist."""
        if not self.current_playlist:
            # If called from menu with no active playlist context,
            # maybe ask user to pick one? For now let's just ignore or status
            self.status.set("Play a playlist first to download it!")
            return

        pl_name = self.current_playlist.get_name()
        missing = get_missing_tracks(pl_name)
        if not missing:
            self.status.set("All tracks are already downloaded! ✓")
            return

        self._start_batch_download(missing)

    # ---------- actions ----------
    def _on_playlist_select(self, button, playlist_idx):
        """Select a playlist without playing it."""
        if not self.playlists or playlist_idx >= len(self.playlists):
            return

        # Update selection and refresh menu
        self.selected_playlist_idx = playlist_idx
        self.menu_widget = self._create_menu()
        self.main_widget.original_widget = self.menu_widget

    def _refresh_menu_counts(self):
        """Refresh menu to update download counts without changing state."""
        if self.state == UIState.MENU:
            self.menu_widget = self._create_menu()
            self.main_widget.original_widget = self.menu_widget

    def _on_play_selected(self):
        """Play the currently selected playlist."""
        if self.selected_playlist_idx is None or self.selected_playlist_idx >= len(
            self.playlists
        ):
            return

        pl_name = self.playlists[self.selected_playlist_idx]
        self.status.set("Loading playlist...")
        try:
            self._load_playlist(self.selected_playlist_idx, auto_play=False)
            self._switch_to_player()
            self.loop.set_alarm_in(0.1, lambda l, d: self._start_playback())

            # Start background downloads for missing tracks
            missing = get_missing_tracks(pl_name)
            if missing:
                self.loop.set_alarm_in(
                    1.0, lambda l, d: self._start_background_downloads(missing)
                )
        except Exception as e:
            self._handle_error(e, "playlist_select")
            self._switch_to_menu()

    def _on_delete_selected(self):
        """Delete the currently selected playlist."""
        if self.selected_playlist_idx is None or self.selected_playlist_idx >= len(
            self.playlists
        ):
            return

        pl_name = self.playlists[self.selected_playlist_idx]
        pl_path = Path("playlists") / f"{pl_name}.json"

        try:
            if pl_path.exists():
                pl_path.unlink()
                logger.info(f"Deleted playlist: {pl_name}")

            # Refresh playlists and menu
            self.playlists = list_playlists()
            self.selected_playlist_idx = None
            self._switch_to_menu()
            self.status.set(f"Deleted '{pl_name}' ✓")
        except Exception as e:
            logger.error(f"Failed to delete playlist: {e}")
            self.status.set(f"Error deleting playlist: {e}")

    def _start_playback(self):
        if self.current_playlist and self.current_playlist.tracks:
            self._play_current_track(0)

    def _on_skin_select(self, button, skin_idx):
        if not self.skins or skin_idx >= len(self.skins):
            return
        self._switch_to_loading("Loading skin...")
        self.loop.draw_screen()
        try:
            self._load_skin(skin_idx)
            self.status.set("✓ Skin changed! Select a playlist (1-9) to start")
            self._switch_to_menu()
        except Exception as e:
            self._handle_error(e, "skin_select")
            self._switch_to_menu()

    # ---------- lifecycle ----------
    def run(self):
        if self.skins:
            self._safe_call(self._load_skin, 0)
        else:
            self.skin_lines = self._create_emergency_skin()
        self._switch_to_menu()

        # Start auto-downloading missing tracks after 2 seconds
        self.loop.set_alarm_in(2.0, lambda l, d: self._start_auto_downloads())

        self.loop.run()

    def _start_auto_downloads(self):
        """Auto-download missing tracks from all playlists on startup."""
        all_missing = []
        for pl_name in self.playlists:
            try:
                missing = get_missing_tracks(pl_name)
                for track in missing:
                    track["_playlist"] = pl_name  # Tag with source playlist
                    all_missing.append(track)
            except Exception:
                pass

        if all_missing:
            logger.info(
                f"[AUTO] Starting auto-download of {len(all_missing)} missing tracks"
            )
            self._start_background_downloads(all_missing)
        else:
            self.status.set("All playlists fully cached! ✓")

    def refresh(self, loop=None, data=None):
        if self.state == UIState.PLAYER:
            self._render_skin()
            if loop:
                self.refresh_alarm = loop.set_alarm_in(0.2, self.refresh)

    def _render_skin(self):
        if self.current_playlist:
            track = self.current_playlist.get_current_track()
            if track:
                cached_path = self.downloader.is_cached(track.url)
                self.is_cached_playback = cached_path is not None

        context = {
            "PREV": "<<",
            "NEXT": ">>",
            "PLAY": "||" if self.player.is_playing() else "▶",
            "VOL_DOWN": "─",
            "VOL_UP": "+",
            "QUIT": "Q",
            "TITLE": "",
            "ARTIST": "",
            "TIME": "00:00/00:00",
            "TIME_CURRENT": "00:00",
            "TIME_TOTAL": "00:00",
            "PROGRESS": "[          ]",
            "VOLUME": f"{self.player.volume}%",
            "STATUS": "♪" if self.player.is_playing() else "■",
            "NEXT_TRACK": "",
            "PLAYLIST": "",
            "TRACK_NUM": "",
            "CACHE_STATUS": "✓" if self.is_cached_playback else "✗",
            "SHUFFLE_STATUS": "OFF",
            "REPEAT_STATUS": "ALL",
        }

        if self.current_playlist:
            track = self.current_playlist.get_current_track()
            if track:
                context["TITLE"] = track.title[:35]
                context["ARTIST"] = track.artist[:30]
                context["PLAYLIST"] = self.current_playlist.get_name()[:25]
                context["TRACK_NUM"] = self.current_playlist.get_position_info()
                context["SHUFFLE_STATUS"] = (
                    "ON" if self.current_playlist.shuffle_enabled else "OFF"
                )
                context["REPEAT_STATUS"] = (
                    self.current_playlist.repeat_mode.value.upper()
                )
                next_idx = self.current_playlist.current_index + 1
                if next_idx < self.current_playlist.get_track_count():
                    nt = self.current_playlist.tracks[next_idx]
                    context["NEXT_TRACK"] = nt.title[:30]

        info = self.player.get_time_info()
        context["TIME_CURRENT"] = info["current_formatted"]
        context["TIME_TOTAL"] = info["total_formatted"]
        context["TIME"] = f"{info['current_formatted']}/{info['total_formatted']}"
        if info["total_duration"] > 0:
            bar_width = 25
            filled = int((info["percentage"] / 100) * bar_width)
            context["PROGRESS"] = "[" + "█" * filled + "░" * (bar_width - filled) + "]"

        lines = pad_lines(self.skin_lines, PAD_WIDTH, PAD_HEIGHT)
        rendered = self.skin_loader.render(
            lines, context, pad_width=PAD_WIDTH, pad_height=PAD_HEIGHT
        )
        self.skin_widget.update("\n".join(rendered))

    def _load_skin(self, idx):
        if not self.skins:
            self.skin_lines = self._create_emergency_skin()
            return

        if self._loading_skin:
            return
        self._loading_skin = True
        try:
            self.current_skin_idx = idx % len(self.skins)
            skin_name = self.skins[self.current_skin_idx]
            skin_path = Path("skins") / f"{skin_name}.txt"

            # 1. Validate first
            is_valid, errors = self.skin_loader.validate_skin(str(skin_path))

            if not is_valid:
                # 2. Show detailed error report
                self.skin_lines = self.skin_loader.create_error_skin(errors)
                if self.state == UIState.PLAYER:
                    self.status.set(
                        f"⚠️ Skin '{skin_name}' is broken! Press S to switch."
                    )
            else:
                # 3. Load if valid
                meta, lines = self.skin_loader.load(str(skin_path))
                self.skin_lines = pad_lines(lines, PAD_WIDTH, PAD_HEIGHT)
                if self.state == UIState.PLAYER:
                    self.status.set(f"Skin: {meta.get('name', '')[:20]} | " + HELP_TEXT)

        except Exception as e:
            # Fallback for unexpected crashes
            self.skin_lines = self._create_emergency_skin()
            self._handle_error(e, "load_skin")
        finally:
            self._loading_skin = False

    def _create_emergency_skin(self):
        emergency = [
            "",
            "  ═══════════════════════════════════════════════════════════",
            "",
            "    Y T B M U S I C   P L A Y E R",
            "",
            "  ═══════════════════════════════════════════════════════════",
            "",
            "    ♪  {{TITLE}}",
            "       {{ARTIST}}",
            "",
            "  ───────────────────────────────────────────────────────────",
            "",
            "    {{TIME}}                          {{STATUS}}  Cache:{{CACHE_STATUS}}",
            "",
            "    {{PROGRESS}}",
            "",
            "  ───────────────────────────────────────────────────────────",
            "",
            "    Track {{TRACK_NUM}}          {{PLAYLIST}}",
            "",
            "    Next: {{NEXT_TRACK}}",
            "",
            "    Shuffle: {{SHUFFLE_STATUS}}  •  Repeat: {{REPEAT_STATUS}}",
            "",
            "  ───────────────────────────────────────────────────────────",
            "",
            "",
            "      [ {{PREV}} ]    [ {{PLAY}} ]    [ {{NEXT}} ]",
            "",
            "      [ {{VOL_DOWN}} ]  {{VOLUME}}  [ {{VOL_UP}} ]",
            "",
            "                                          [ {{QUIT}} ]",
            "",
            "  ═══════════════════════════════════════════════════════════",
        ]
        return pad_lines(emergency, PAD_WIDTH, PAD_HEIGHT)

    def _load_playlist(self, idx, auto_play=True):
        if not self.playlists:
            self.current_playlist = None
            return
        self.current_playlist_idx = idx % len(self.playlists)
        name = self.playlists[self.current_playlist_idx]
        self.current_playlist = self.playlist_manager.load_playlist(name)

    def _play_current_track(self, index):
        if (
            not self.current_playlist
            or index < 0
            or index >= len(self.current_playlist.tracks)
        ):
            return
        track = self.current_playlist.tracks[index]
        self.current_playlist.current_index = index

        # Track request ID to handle rapid skipping
        self._play_req_id = getattr(self, "_play_req_id", 0) + 1
        current_req = self._play_req_id

        try:
            cached_path = self.downloader.is_cached(track.url)
            if cached_path:
                self.player.play(cached_path)
                self.is_cached_playback = True
                self.status.set(f"♪ {track.title[:35]} (cached)")
            else:
                # Stop current playback before streaming
                self.player.stop()

                # Stream it asynchronously
                self.status.set(f"Buffering {track.title[:30]}...")
                self.is_cached_playback = False

                def fetch_stream():
                    try:
                        logger.info(f"[STREAM] Fetching URL for: {track.title}")
                        stream_url = self.downloader.get_stream_url(track.url)

                        # Only play if we are still on the same request
                        if getattr(self, "_play_req_id", 0) == current_req:
                            self.loop.set_alarm_in(
                                0,
                                lambda l, d: self._finalize_play_stream(
                                    stream_url, track
                                ),
                            )
                    except Exception as e:
                        logger.error(f"[STREAM] Failed: {e}")
                        # Auto-skip on error?
                        if getattr(self, "_play_req_id", 0) == current_req:
                            self.loop.set_alarm_in(0, lambda l, d: self._next_track())

                t = threading.Thread(target=fetch_stream, daemon=True)
                t.start()

            self.consecutive_errors = 0

        except Exception as e:
            self.consecutive_errors += 1
            if self.consecutive_errors >= 5:
                self._handle_error(e, "play_track")
                self.player.stop()
                self.consecutive_errors = 0
                return
            if not self._next_track():
                self.player.stop()

    def _finalize_play_stream(self, stream_url, track):
        """Called from thread when stream URL is ready."""
        try:
            self.player.play(stream_url)
            self.status.set(f"♪ {track.title[:35]} (streaming) | " + HELP_TEXT)
        except Exception as e:
            logger.error(f"Playback failed: {e}")
            self._next_track()

    def _on_track_end_callback(self):
        """Called by VLC when track ends (runs in VLC thread)."""
        # Schedule next track in main thread to avoid urwid thread-safety issues
        if hasattr(self, "loop") and self.loop:
            self.loop.set_alarm_in(0.1, lambda loop, user_data: self._next_track())

    def _next_track(self):
        if not self.current_playlist:
            return False
        nxt = self.current_playlist.next()
        if nxt:
            self._play_current_track(self.current_playlist.current_index)
            return True
        self.player.stop()
        self.status.set("Playlist finished • Press M for menu")
        return False

    def _prev_track(self):
        if not self.current_playlist:
            return
        prv = self.current_playlist.previous()
        if prv:
            self._play_current_track(self.current_playlist.current_index)

    def cleanup(self):
        try:
            if self.refresh_alarm:
                self.loop.remove_alarm(self.refresh_alarm)
            if self.spinner_alarm:
                self.loop.remove_alarm(self.spinner_alarm)
            self.player.cleanup()
        except Exception:
            pass

    def unhandled_input(self, key):
        # Ignore mouse events and other non-string keys
        if not isinstance(key, str):
            return

        # Debug logging (goes to file, not stdout)
        logger.debug(f"[KEY] state={self.state.value} key='{key}'")

        # Q always quits
        if key in ("q", "Q"):
            self._cancel_background_downloads()
            self.cleanup()
            raise urwid.ExitMainLoop()

        # Allow escape during loading
        if self.state == UIState.LOADING:
            if key in ("esc", "m", "M"):
                logger.debug("[KEY] Escaping from loading state")
                self._cancel_background_downloads()
                self._switch_to_menu()
            return
        if self.state == UIState.MENU:
            if key.isdigit() and "1" <= key <= "9":
                idx = int(key) - 1
                if idx < len(self.playlists):
                    self._on_playlist_select(None, idx)
            elif key.upper() in "ABCDEFGHIJ":
                idx = ord(key.upper()) - ord("A")
                if idx < len(self.skins):
                    self._on_skin_select(None, idx)
            elif key in ("i", "I"):
                logger.debug("[KEY] Calling _prompt_import_playlist()")
                self._prompt_import_playlist()
            elif key in ("p", "P"):
                self._on_play_selected()
            elif key in ("x", "X"):
                self._on_delete_selected()
            return
        if key == " ":
            self.player.toggle_pause()
        elif key in ("n", "N"):
            self._next_track()
        elif key in ("p", "P"):
            self._prev_track()
        elif key in ("s", "S"):
            if self.skins:
                next_idx = (self.current_skin_idx + 1) % len(self.skins)
                self._load_skin(next_idx)
        elif key in ("m", "M"):
            self._switch_to_menu()
        elif key == "up":
            self.player.volume_up()
        elif key == "down":
            self.player.volume_down()
        elif key == "right":
            self.player.seek(10)
        elif key == "left":
            self.player.seek(-10)
        elif key in ("z", "Z"):
            if self.current_playlist:
                self.current_playlist.toggle_shuffle()
                status = "ON" if self.current_playlist.shuffle_enabled else "OFF"
                self.status.set(f"Shuffle: {status} | " + HELP_TEXT)
        elif key in ("r", "R"):
            if self.current_playlist:
                self.current_playlist.cycle_repeat_mode()
                mode = self.current_playlist.repeat_mode.value
                self.status.set(f"Repeat: {mode} | " + HELP_TEXT)
        elif key in ("d", "D"):
            self._on_download_all()


def main():
    cols, lines = shutil.get_terminal_size()
    if cols < PAD_WIDTH or lines < PAD_HEIGHT:
        print(f"\n⚠️  Terminal: {cols}x{lines}")
        print(f"   Recommended: {PAD_WIDTH}x{PAD_HEIGHT} or larger")
        print("   Starting in 2 seconds...")
        time.sleep(2)
    try:
        app = YTBMusicUI()
        app.run()
    except Exception as e:
        print(f"\n❌ Critical Error: {e}")
        import traceback

        traceback.print_exc()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
