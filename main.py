import urwid
import time
import signal
import shutil
import threading
import queue
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional

from core.player import MusicPlayer, PlayerState
from core.downloader import YouTubeDownloader
from core.download_manager import DownloadManager, new_request_id
from core.playlist import PlaylistManager, RepeatMode
from core.playlist_editor import (
    import_playlist_from_youtube,
    list_playlists,
    get_missing_tracks,
    delete_playlist,
    load_playlist,
)

from core.logger import setup_logging
from ui.skin_loader import SkinLoader
from ui.animation_loader import AnimationLoader, AnimationWidget

logger = setup_logging()


HELP_TEXT = "Space=⏯ N/P=⏭⏮ ←/→=Seek ↑/↓=Vol S=Skin A=Anim V=NextAnim M=Menu Q=Quit"
PAD_WIDTH = 120
PAD_HEIGHT = 88
SKIN_HOTKEYS = "BCDFGHJKL"  # skip A (Animation), E (Rename), I (Import)


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
    """Three-line status bar: Info (Top) + Playback Shortcuts (Mid) + App Shortcuts (Bot)."""

    SHORTCUTS_PLAY = "Space=⏯  N/P=⏭⏮  ←/→=Seek  ↑↓=Vol  Z=Shuffle  R=Repeat"
    SHORTCUTS_APP = "T=Tracks  S=Skin  A=Anim  V=NextAnim  M=Menu  Q=Quit"

    def __init__(self, context_text=""):
        self.top_line = urwid.Text(context_text, align="center")
        self.mid_line = urwid.Text(self.SHORTCUTS_PLAY, align="center")
        self.bot_line = urwid.Text(self.SHORTCUTS_APP, align="center")

        self._default_info = context_text

        self.pile = urwid.Pile(
            [
                urwid.AttrWrap(self.top_line, "status"),
                urwid.AttrWrap(self.mid_line, "status"),
                urwid.AttrWrap(self.bot_line, "status"),
            ]
        )
        super().__init__(self.pile)

    def set(self, text):
        """Set the persistent info message (Top Line)."""
        # Clean up any " | HELP_TEXT" that might be passed from legacy calls
        if " | Space=" in text:
            text = text.split(" | Space=")[0]

        self.top_line.set_text(text)
        self._default_info = text

    def notify(self, text):
        """Set a transient notification (Top Line)."""
        self.top_line.set_text(text)

    def clear_notify(self):
        """Restore default info to Top Line."""
        self.top_line.set_text(self._default_info)


class MessageLog(urwid.WidgetWrap):
    """Scrolling log widget for download activity."""

    def __init__(self, height=3):
        self.height = height
        self.walker = urwid.SimpleListWalker([])
        self.listbox = urwid.ListBox(self.walker)
        self.box = urwid.LineBox(self.listbox)
        super().__init__(self.box)

    def log(self, message: str, style: str = "normal"):
        """Add a message to the log."""
        timestamp = time.strftime("%H:%M:%S")
        txt = urwid.Text((style, f"[{timestamp}] {message}"))
        self.walker.append(txt)
        # Scroll to bottom
        if len(self.walker) > 50:
            self.walker.pop(0)
        self.listbox.set_focus(len(self.walker) - 1)


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
        "k",
        "K",
        "l",
        "L",
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
        edit_row_index = None

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
        edit_row_index = len(body_widgets) - 1
        body_widgets.append(
            urwid.Text("║                                                          ║")
        )
        for line in footer_art:
            body_widgets.append(urwid.Text(line))

        pile = urwid.Pile(body_widgets)
        if edit_row_index is not None:
            pile.focus_position = edit_row_index
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


class TrackPickerDialog(urwid.WidgetWrap):
    """Scrollable track picker overlay for the current playlist."""

    def __init__(
        self, title: str, tracks: list, current_idx: int, on_select, on_cancel
    ):
        self._on_select = on_select
        self._on_cancel = on_cancel

        self._title = title
        self._tracks = list(tracks)
        self._current_idx = int(current_idx)
        self._filtered_indices: list[int] = []
        self._search_active = False

        self._header = urwid.Text("", align="center")
        self._hint = urwid.Text(
            " Enter=Play  /=Search  Esc=Close  ↑/↓=Navigate ", align="center"
        )
        self._search = urwid.Edit(" Search: ")
        self._footer = urwid.Pile([self._hint, self._search])
        self._footer.focus_position = 0

        self._walker = urwid.SimpleFocusListWalker([])
        self._listbox = urwid.ListBox(self._walker)

        self._frame = urwid.Frame(
            body=self._listbox, header=self._header, footer=self._footer
        )
        super().__init__(urwid.LineBox(self._frame))

        self._apply_filter("")

    def _update_header(self, query: str) -> None:
        total = len(self._tracks)
        shown = len(self._filtered_indices)
        q = (query or "").strip()
        suffix = f"  (filter: {q})" if q else ""
        self._header.set_text(
            ("title", f" {self._title} — Tracks {shown}/{total}{suffix} ")
        )

    def _track_label(self, original_index: int) -> str:
        tr = self._tracks[original_index]
        artist = (getattr(tr, "artist", "") or "").strip()
        ttitle = (getattr(tr, "title", "") or "").strip()

        label = f"{original_index + 1:>3}. "
        if original_index == self._current_idx:
            label += "▶ "
        if getattr(tr, "is_playable", True) is False:
            label += "✗ "

        if artist and ttitle:
            label += f"{artist} - {ttitle}"
        else:
            label += ttitle or artist or "Unknown"
        return label

    def _apply_filter(self, query: str) -> None:
        q = (query or "").casefold().strip()
        self._filtered_indices = []
        for i, tr in enumerate(self._tracks):
            artist = (getattr(tr, "artist", "") or "").casefold()
            ttitle = (getattr(tr, "title", "") or "").casefold()
            if not q or q in f"{artist} {ttitle}":
                self._filtered_indices.append(i)

        del self._walker[:]

        if not self._filtered_indices:
            self._walker.append(urwid.Text(" No matches"))
            self._update_header(query)
            return

        for original_index in self._filtered_indices:
            btn = urwid.Button(self._track_label(original_index))
            urwid.connect_signal(
                btn, "click", lambda b, idx=original_index: self._on_select(idx)
            )
            self._walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))

        focus_pos = 0
        if self._current_idx in self._filtered_indices:
            try:
                focus_pos = self._filtered_indices.index(self._current_idx)
            except ValueError:
                focus_pos = 0
        try:
            self._walker.set_focus(max(0, min(int(focus_pos), len(self._walker) - 1)))
        except Exception:
            pass

        self._update_header(query)

    def _enter_search(self) -> None:
        self._search_active = True
        self._frame.focus_part = "footer"
        self._footer.focus_position = 1

    def _exit_search(self) -> None:
        self._search_active = False
        self._frame.focus_part = "body"
        self._footer.focus_position = 0

    def keypress(self, size, key):
        if key == "/" and not self._search_active:
            self._enter_search()
            return None

        if key == "esc":
            if self._search_active:
                if self._search.get_edit_text():
                    self._search.set_edit_text("")
                    self._apply_filter("")
                    self._exit_search()
                    return None
                self._exit_search()
            self._on_cancel()
            return None

        if key in ("t", "T") and not self._search_active:
            self._on_cancel()
            return None

        result = super().keypress(size, key)

        if self._search_active:
            if key == "enter":
                self._exit_search()
                return None
            self._apply_filter(self._search.get_edit_text())

        return result


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
        self.skin_frames: Optional[list[list[str]]] = None
        self._skin_frame_index = 0
        self._skin_frame_interval_sec = 0.5
        self._skin_next_frame_at = 0.0
        self._loading_skin = False

        # Playlists
        self.playlists = self.playlist_manager.list_playlists()
        self.current_playlist_idx = 0
        self.current_playlist = None
        self.consecutive_errors = 0

        # Caching
        self.playlist_cache: Dict[str, PlaylistMetadata] = {}
        self.skin_cache: Dict[str, SkinMetadata] = {}
        self.download_count_cache: Dict[str, tuple[int, int, float]] = (
            {}
        )  # name -> (dl, tot, time)
        self.cache_ttl = 300  # 5 minutes

        # UI state
        self.refresh_alarm = None
        self.spinner_alarm = None
        self.spinner_frame = 0
        self.loading_message = ""
        self.is_cached_playback = False
        self.is_buffering = False
        self.skin_hotkeys = SKIN_HOTKEYS
        # Background download state (driven by DownloadManager events)
        self.bg_download_active = False
        self.bg_download_current = 0
        self.bg_download_total = 0
        self.bg_download_title = ""
        self.bg_download_artist = ""
        self.bg_download_playlist = ""
        self.bg_download_progress = None
        self.bg_download_current_url = None
        self.bg_download_queue_size = 0
        self.bg_download_kind = ""

        # Download manager (single worker, priority queue)
        self._download_events: "queue.Queue[dict]" = queue.Queue()
        self._download_event_alarm = None
        self._download_request_summary: Dict[str, Dict[str, int]] = {}
        self._active_download_request_id: Optional[str] = None
        self._auto_download_request_id = new_request_id("AUTO")
        self._pending_autoplay: Optional[Dict[str, str]] = None
        self._player_overlay_active = False

        self.download_manager = DownloadManager(
            self.downloader,
            event_callback=self._download_events.put,
            progress_throttle_sec=0.25,
        )
        self.download_manager.start()

        # Widgets
        self.skin_widget = SkinWidget()
        self.menu_widget = None
        self.loading_widget = None
        self.status = StatusBar("")
        self.message_log = MessageLog(height=3)
        self.main_widget = urwid.WidgetPlaceholder(urwid.Text("Initializing..."))

        # Animation system
        self.animation_widget = AnimationWidget(height=3)
        self.animation_active = False
        self.animation_alarm = None
        self.available_animations = AnimationLoader.list_available_animations()
        self.current_animation_idx = 0

        # Combine message log and status bar in footer
        # Use WidgetPlaceholder for footer content to allow swapping between log and animation
        self.footer_content = urwid.WidgetPlaceholder(self.message_log)
        footer_pile = urwid.Pile(
            [
                ("fixed", 5, self.footer_content),  # 3 lines text + 2 borders = 5 lines
                self.status,  # Flow widget (natural height)
            ]
        )

        frame = urwid.Frame(body=self.main_widget, footer=footer_pile)

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
        Optimized with caching to avoid disk I/O on every frame.
        """
        # Check cache (10 second TTL for download counts as they change often during DL)
        now = time.time()
        if playlist_name in self.download_count_cache:
            dl, tot, ts = self.download_count_cache[playlist_name]
            if now - ts < 10:  # 10s TTL
                return dl, tot

        try:
            # We need to peek into the playlist without fully loading it as the current object
            mgr = PlaylistManager()
            pl = mgr.load_playlist(playlist_name)

            total = len(pl.tracks)
            downloaded = 0

            for track in pl.tracks:
                if self.downloader.is_cached(
                    track.url, title=track.title, artist=track.artist
                ):
                    downloaded += 1

            # Update cache
            self.download_count_cache[playlist_name] = (downloaded, total, now)
            return downloaded, total
        except Exception:
            return 0, 0

    # ---------- UI builders ----------
    def _create_menu(self):
        items = []
        playlist_focus_map = {}

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
                playlist_focus_map[i] = len(self.menu_walker) - 1

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

            # RENAME Button
            ren_btn = urwid.Button(f"      [E] RENAME PLAYLIST")
            urwid.connect_signal(ren_btn, "click", lambda b: self._on_rename_selected())
            self.menu_walker.append(urwid.AttrMap(ren_btn, None, focus_map="highlight"))

        self.menu_walker.append(urwid.Text(""))
        self.menu_walker.append(urwid.Divider("═"))

        # Import button
        import_btn = urwid.Button("    [I] Import from YouTube")
        urwid.connect_signal(
            import_btn, "click", lambda b: self._prompt_import_playlist()
        )
        self.menu_walker.append(urwid.AttrMap(import_btn, None, focus_map="highlight"))

        # Random All button
        random_btn = urwid.Button("    [R] 🔀 Random All Songs")
        urwid.connect_signal(random_btn, "click", lambda b: self._on_random_all())
        self.menu_walker.append(urwid.AttrMap(random_btn, None, focus_map="highlight"))

        self.menu_walker.append(urwid.Divider(" "))
        skin_keys_label = self._skin_keys_label()
        self.menu_walker.append(
            urwid.AttrMap(
                urwid.Text(f"  🎨  SELECT SKIN ({skin_keys_label})", align="left"),
                "title",
            )
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
            for i, skin_name in enumerate(self.skins[: len(self.skin_hotkeys)]):
                meta = self._get_skin_metadata(skin_name)
                hotkey = self.skin_hotkeys[i]
                display = f"    [{hotkey}] {meta.name if meta else skin_name}"
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

        listbox = MenuListBox(self.menu_walker)

        # Keep focus on the selected playlist row if available
        if (
            self.selected_playlist_idx is not None
            and self.selected_playlist_idx in playlist_focus_map
        ):
            try:
                self.menu_walker.set_focus(
                    playlist_focus_map[self.selected_playlist_idx]
                )
            except Exception:
                pass

        return listbox

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
            self.state = UIState.MENU
            self.main_widget.original_widget = self.menu_widget
            # Postpone callback to avoid freezing during keypress
            self.loop.set_alarm_in(0, lambda l, d: callback(text))

        # Keep menu visible underneath but freeze state so bg refresh doesn't replace overlay
        self.state = UIState.EDIT
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

    def _show_confirm_dialog(self, title, message, on_confirm, on_cancel=None):
        """Simple yes/no confirmation dialog."""
        self.state = UIState.EDIT

        def finish():
            self.state = UIState.MENU
            self.main_widget.original_widget = self.menu_widget

        def do_confirm(button=None):
            finish()
            self.loop.set_alarm_in(0, lambda l, d: on_confirm())

        def do_cancel(button=None):
            finish()
            if on_confirm and on_cancel:
                self.loop.set_alarm_in(0, lambda l, d: on_cancel())

        yes_btn = urwid.Button(" Yes ")
        no_btn = urwid.Button(" No ")
        urwid.connect_signal(yes_btn, "click", do_confirm)
        urwid.connect_signal(no_btn, "click", do_cancel)

        pile = urwid.Pile(
            [
                urwid.Text(("title", f" {title} "), align="center"),
                urwid.Divider(),
                urwid.Text(message, align="center"),
                urwid.Divider(),
                urwid.Columns(
                    [
                        (
                            "weight",
                            1,
                            urwid.AttrMap(yes_btn, None, focus_map="highlight"),
                        ),
                        (
                            "weight",
                            1,
                            urwid.AttrMap(no_btn, None, focus_map="highlight"),
                        ),
                    ],
                    dividechars=2,
                ),
            ]
        )
        pile.focus_position = 4
        overlay = urwid.Overlay(
            urwid.LineBox(urwid.Filler(pile, valign="middle")),
            self.menu_widget,
            align="center",
            width=60,
            valign="middle",
            height=10,
        )
        self.main_widget.original_widget = overlay

    def _start_batch_download(self, tracks: list):
        """Start batch download without blocking the UI."""
        if not tracks:
            self.status.set("All tracks downloaded! ✓")
            return

        playlist_label = ""
        if self.current_playlist:
            playlist_label = self.current_playlist.get_name()[:15]

        queue_items = []
        for t in tracks:
            item = dict(t)
            if playlist_label:
                item["_playlist"] = playlist_label
            queue_items.append(item)

        queued = len(queue_items)
        self.status.notify(f"⬇️ Queued {queued} track(s) for download...")
        self._start_background_downloads(queue_items, start_delay=0.1, force_reset=True)

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
        self._player_overlay_active = False
        # Do NOT stop the player here to allow background playback
        # self.player.stop()
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
            skin_keys_label = self._skin_keys_label()
            self.status.set(
                f"Select playlist (1-9) or skin ({skin_keys_label}) • Q to quit"
            )
        else:
            self.status.set("Add playlists and skins to get started")

        # Show download notification if active
        if getattr(self, "bg_download_active", False):
            msg = self._get_bg_download_status()
            if msg:
                self.status.notify(msg)
        else:
            self.status.clear_notify()

    def _switch_to_player(self):
        self.state = UIState.PLAYER
        self._player_overlay_active = False
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
        logger.error(
            "ERROR [%s]: %s",
            context or "unknown",
            error,
            exc_info=(type(error), error, error.__traceback__),
        )
        print(f"ERROR [{context}]: {error}")
        import traceback

        traceback.print_exception(type(error), error, error.__traceback__)

    def _safe_call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self._handle_error(e, context=func.__name__)
            return None

    def _skin_keys_label(self) -> str:
        """Human-friendly label for skin hotkeys."""
        if self.skin_hotkeys == "ABCDFGHJKL":
            return "A-D/F-H/J-L"
        if self.skin_hotkeys == "ABCDEFGHJK":
            return "A-H/J-K"
        return self.skin_hotkeys

    def _get_bg_download_status(self) -> Optional[str]:
        """Build a human-friendly background download status string."""
        if not getattr(self, "bg_download_active", False):
            return None
        curr = getattr(self, "bg_download_current", 0)
        total = getattr(self, "bg_download_total", 0)
        kind = (getattr(self, "bg_download_kind", "") or "").strip()

        parts = []
        if self.bg_download_playlist:
            parts.append(f"[{self.bg_download_playlist}]")

        if self.bg_download_artist and self.bg_download_title:
            parts.append(f"{self.bg_download_artist} - {self.bg_download_title}")
        elif self.bg_download_title:
            parts.append(self.bg_download_title)

        detail = " ".join(parts).strip()
        percent = (
            f" ({self.bg_download_progress:.0f}%)"
            if self.bg_download_progress is not None
            else ""
        )

        base = f"⬇️ {curr}/{total}"
        if kind:
            base = f"⬇️ {kind} {curr}/{total}"
        if detail:
            return f"{base}: {detail}{percent}"
        return f"{base}{percent}" if percent else base

    def _notify_bg_download_status(self):
        """Update the status bar with the latest background download info."""
        msg = self._get_bg_download_status()
        if msg:
            self.status.notify(msg)
            # Log significant events or errors occasionally?
            # For now, just keep status bar lively.
            # But let's log completion:
            pass

    def log_activity(self, message: str, style="info"):
        """Log to the scrolling message log."""
        self.message_log.log(message, style)

    def _start_download_event_pump(self):
        """Drain DownloadManager events on the main loop (thread-safe)."""
        if getattr(self, "_download_event_alarm", None):
            return
        self._download_event_alarm = self.loop.set_alarm_in(
            0.1, self._process_download_events
        )

    def _process_download_events(self, loop=None, user_data=None):
        # Clear the handle first to avoid duplicate scheduling if handler is slow
        self._download_event_alarm = None

        try:
            while True:
                try:
                    event = self._download_events.get_nowait()
                except queue.Empty:
                    break
                self._handle_download_event(event)
        finally:
            # Keep pumping while app is alive
            if hasattr(self, "loop") and self.loop:
                self._download_event_alarm = self.loop.set_alarm_in(
                    0.1, self._process_download_events
                )

    def _handle_download_event(self, event: dict):
        etype = event.get("type")
        request_id = event.get("request_id")

        if request_id:
            summary = self._download_request_summary.setdefault(
                request_id, {"total": 0, "done": 0, "failed": 0, "canceled": 0}
            )
            if "total" in event and isinstance(event["total"], int):
                summary["total"] = max(summary["total"], event["total"])

        if etype == "queue":
            rid = request_id or ""
            added = event.get("added", 0)
            qsize = event.get("queue_size", 0)
            logger.info(f"[DL {rid}] queued +{added} (queue={qsize})")
            return

        if etype == "cancel_all":
            logger.info("[DL] cancel_all")
            self.bg_download_active = False
            self.bg_download_progress = None
            self.bg_download_current_url = None
            self.bg_download_queue_size = 0
            self.bg_download_kind = ""
            self.status.clear_notify()
            return

        if etype == "start":
            task = event.get("task")
            self._active_download_request_id = request_id
            self.bg_download_active = True
            self.bg_download_current = int(event.get("position", 0) or 0)
            self.bg_download_total = int(event.get("total", 0) or 0)
            self.bg_download_queue_size = int(event.get("queue_size", 0) or 0)
            self.bg_download_title = getattr(task, "title", "") if task else ""
            self.bg_download_artist = getattr(task, "artist", "") if task else ""
            self.bg_download_playlist = getattr(task, "playlist", "") if task else ""
            self.bg_download_current_url = getattr(task, "url", None) if task else None
            self.bg_download_progress = None
            self.bg_download_kind = (request_id or "").split("-", 1)[0]

            label = event.get("label") or ""
            rid = request_id or ""
            logger.info(
                f"[DL {rid}] start {self.bg_download_current}/{self.bg_download_total} "
                f"[{self.bg_download_playlist}] {self.bg_download_title}"
            )
            if label:
                self.log_activity(f"{label}: downloading…", "info")

            # If importing, keep the LOADING message meaningful
            if self.state == UIState.LOADING and self._pending_autoplay:
                pl = self._pending_autoplay.get("playlist", "")
                if pl and pl == self._pending_autoplay.get("playlist"):
                    self._update_loading_message(
                        f"Downloading 1/{self.bg_download_total}: {self.bg_download_title[:35]}"
                    )

            self._notify_bg_download_status()
            return

        if etype == "progress":
            self.bg_download_progress = float(event.get("percent", 0.0))
            self.bg_download_queue_size = int(event.get("queue_size", 0) or 0)
            self._notify_bg_download_status()

            if self.state == UIState.LOADING and self._pending_autoplay:
                self._update_loading_message(
                    f"Downloading {self.bg_download_current}/{self.bg_download_total}: "
                    f"{self.bg_download_title[:35]} ({self.bg_download_progress:.0f}%)"
                )
            return

        if etype == "complete":
            task = event.get("task")
            rid = request_id or ""
            if rid:
                self._download_request_summary.setdefault(
                    rid, {"total": 0, "done": 0, "failed": 0, "canceled": 0}
                )["done"] += 1
            title = getattr(task, "title", "") if task else ""
            logger.info(f"[DL {rid}] complete: {title}")
            if title:
                self.log_activity(f"Downloaded: {title}", "success")
            if self.state == UIState.MENU:
                self._refresh_menu_counts()

            # Autoplay after import: start playback when first track is ready
            if self._pending_autoplay and task and getattr(task, "url", None):
                if task.url == self._pending_autoplay.get("first_url"):
                    pl_name = self._pending_autoplay.get("playlist", "")
                    self._pending_autoplay = None
                    self._load_playlist_by_name(pl_name)
                    self._switch_to_player()
                    self.loop.set_alarm_in(0.1, lambda l, d: self._start_playback())
            return

        if etype == "canceled":
            task = event.get("task")
            rid = request_id or ""
            if rid:
                self._download_request_summary.setdefault(
                    rid, {"total": 0, "done": 0, "failed": 0, "canceled": 0}
                )["canceled"] += 1
            title = getattr(task, "title", "") if task else ""
            logger.info(f"[DL {rid}] canceled: {title}")
            return

        if etype == "error":
            task = event.get("task")
            rid = request_id or ""
            if rid:
                self._download_request_summary.setdefault(
                    rid, {"total": 0, "done": 0, "failed": 0, "canceled": 0}
                )["failed"] += 1
            title = getattr(task, "title", "") if task else ""
            err = event.get("error", "")
            logger.error(f"[DL {rid}] failed: {title} - {err}")
            if title:
                self.log_activity(f"Failed: {title}", "error")

            # Persist "unplayable" for known cases so we don't retry forever
            if task and getattr(task, "playlist", ""):
                reason = None
                task_title = getattr(task, "title", "") or ""
                err_l = (err or "").lower()
                if task_title in ["[Private video]", "[Deleted video]"]:
                    reason = task_title
                elif "private" in err_l and "video" in err_l:
                    reason = "[Private video]"
                elif "deleted" in err_l and "video" in err_l:
                    reason = "[Deleted video]"
                elif "video unavailable" in err_l:
                    reason = "Video unavailable"

                if reason:
                    try:
                        self.playlist_manager.mark_track_unplayable(
                            task.playlist, task.url, reason
                        )
                    except Exception:
                        pass

            # If the first track of an import fails, don't leave the user stuck in LOADING
            if self._pending_autoplay and task and getattr(task, "url", None):
                if task.url == self._pending_autoplay.get("first_url"):
                    pl_name = self._pending_autoplay.get("playlist", "")
                    self._pending_autoplay = None
                    self._load_playlist_by_name(pl_name)
                    self._switch_to_player()
                    self.loop.set_alarm_in(0.1, lambda l, d: self._start_playback())
            return

        if etype == "idle":
            # Queue drained
            self.bg_download_active = False
            self.bg_download_progress = None
            self.bg_download_current_url = None
            self.bg_download_queue_size = 0
            self.bg_download_kind = ""

            rid = self._active_download_request_id
            if rid and rid in self._download_request_summary:
                s = self._download_request_summary[rid]
                total = s.get("total", 0) or self.bg_download_total
                done = s.get("done", 0)
                failed = s.get("failed", 0)
                if total:
                    if failed:
                        self.status.notify(f"✓ Done: {done}/{total} ({failed} failed)")
                    else:
                        self.status.notify(f"✓ All {done}/{total} downloaded!")
                    self.loop.set_alarm_in(5.0, lambda l, d: self.status.clear_notify())
            self._active_download_request_id = None
            return

    def _prompt_import_playlist(self):
        """Show dialog to import a YouTube playlist."""

        def on_url_entered(url):
            if not url:
                return

            def on_name_entered(name):
                self._switch_to_loading("Contacting YouTube...")
                self.status.notify("⬇️ Importing playlist info...")
                self.loop.draw_screen()

                # Run import in background thread
                def threaded_import():
                    try:
                        logger.info(f"[THREAD] Starting import for URL: {url}")

                        # We can't safely log to UI from thread directly without loop.set_alarm_in
                        # but we can rely on the loading message for now.

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
            # Removed spammy status.notify; loading message is enough
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

        if result["added"] == 0 and result["skipped"] == 0:
            self.status.set(
                f"⚠️ Imported 0 tracks from '{result['name']}'. Check URL validity."
            )
            self._switch_to_menu()
            return

        # Start downloading first track in thread
        pl_name = result["name"]
        missing = get_missing_tracks(pl_name)
        self.status.notify(
            f"⬇️ Imported '{pl_name}': added {result['added']}, skipped {result['skipped']}"
        )
        self.log_activity(
            f"Imported '{pl_name}': {result['added']} new, {result['skipped']} skipped",
            "success",
        )

        if not missing:
            self._load_playlist_by_name(pl_name)
            self._switch_to_player()
            self.loop.set_alarm_in(0.3, lambda l, d: self._start_playback())
            return

        # Highest priority: download this playlist now, then autoplay when track 1 is ready
        first_url = missing[0].get("url") if missing else None
        if first_url:
            self._pending_autoplay = {"playlist": pl_name, "first_url": first_url}

        self._update_loading_message(
            f"Queued {len(missing)} track(s) from '{pl_name}' for download..."
        )
        self._start_background_downloads(
            missing, start_delay=0.0, default_playlist=pl_name, force_reset=True
        )

    def _on_import_error(self, error_msg):
        """Called when import thread fails."""
        self._handle_error(Exception(error_msg), "import_playlist")
        self._switch_to_menu()

    # First-track download is handled via DownloadManager + _pending_autoplay

    def _load_playlist_by_name(self, name: str):
        """Load a playlist by name and set as current."""
        idx = self.playlists.index(name) if name in self.playlists else 0
        self._load_playlist(idx, auto_play=False)

    def _start_background_downloads(
        self,
        tracks: list,
        start_delay: float = 0.5,
        default_playlist: str = "",
        force_reset: bool = False,
    ):
        """Enqueue background downloads through DownloadManager."""
        if not tracks:
            return

        delay = max(float(start_delay), 0.0)
        if delay > 0:
            self.loop.set_alarm_in(
                delay,
                lambda l, d: self._start_background_downloads(
                    tracks,
                    start_delay=0.0,
                    default_playlist=default_playlist,
                    force_reset=force_reset,
                ),
            )
            return

        # Priority model:
        # - force_reset: user wants focus now (highest)
        # - default_playlist: user is playing something (high)
        # - otherwise: auto-download (low)
        if force_reset:
            priority = 0
            request_id = new_request_id("FOCUS")
            label = f"Download '{default_playlist}'" if default_playlist else "Download"
            replace = True
            cancel_in_progress = True
        elif default_playlist:
            priority = 10
            request_id = new_request_id("PLAY")
            label = f"Prefetch '{default_playlist}'"
            replace = False
            cancel_in_progress = False
        else:
            priority = 100
            request_id = self._auto_download_request_id
            label = "Auto-download"
            replace = False
            cancel_in_progress = False

        # Skip known-unusable items early
        prepared = []
        skipped = 0
        for t in tracks:
            if not t or not t.get("url"):
                continue
            title = t.get("title") or ""
            if title in ["[Private video]", "[Deleted video]"]:
                skipped += 1
                pl_name = t.get("_playlist") or default_playlist or ""
                if pl_name:
                    try:
                        self.playlist_manager.mark_track_unplayable(
                            pl_name, t["url"], title
                        )
                    except Exception:
                        pass
                continue
            item = dict(t)
            if default_playlist and not item.get("_playlist"):
                item["_playlist"] = default_playlist
            prepared.append(item)

        added = self.download_manager.enqueue(
            prepared,
            request_id=request_id,
            priority=priority,
            default_playlist=default_playlist,
            replace=replace,
            cancel_in_progress=cancel_in_progress,
            label=label,
        )

        if skipped:
            self.log_activity(f"Skipped {skipped} unusable track(s)", "error")

        if added:
            self.log_activity(f"{label}: queued {added} track(s)", "info")
            if default_playlist:
                self.status.notify(f"⬇️ Queued {added} track(s) from {default_playlist}")
            else:
                self.status.notify(f"⬇️ Queued {added} track(s)")

    def _cancel_background_downloads(self):
        """Cancel any ongoing background downloads."""
        try:
            self.download_manager.cancel_all(cancel_in_progress=True)
        except Exception:
            pass
        self.bg_download_active = False
        self.bg_download_progress = None
        self.bg_download_title = ""
        self.bg_download_artist = ""
        self.bg_download_playlist = ""
        self.bg_download_current_url = None
        self.bg_download_queue_size = 0
        logger.info("[DL] Downloads cancelled")

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

    def _on_random_all(self):
        """Play all songs from all playlists in random order."""
        import random
        from core.playlist import Playlist, Track

        all_tracks = []

        # Collect all tracks from all playlists
        for pl_name in self.playlists:
            try:
                pl = self.playlist_manager.load_playlist(pl_name)
                if pl and pl.tracks:
                    all_tracks.extend(pl.tracks)
            except Exception:
                continue

        if not all_tracks:
            self.status.set("No tracks found in any playlist!")
            return

        # Shuffle all tracks
        random.shuffle(all_tracks)

        # Create a virtual playlist
        self.current_playlist = Playlist(
            name="🔀 Random All",
            description=f"All songs shuffled ({len(all_tracks)} tracks)",
            tracks=all_tracks,
            settings={"shuffle": True, "repeat": "playlist"},
        )
        self.current_playlist.current_index = 0

        self.status.set(f"🔀 Loaded {len(all_tracks)} random tracks!")
        self._switch_to_player()
        self.loop.set_alarm_in(0.1, lambda l, d: self._start_playback())

    def _on_play_selected(self):
        """Play the currently selected playlist."""
        if self.selected_playlist_idx is None or self.selected_playlist_idx >= len(
            self.playlists
        ):
            return

        pl_name = self.playlists[self.selected_playlist_idx]

        # Smart Resume: If selecting the active playlist, just go to player view
        if self.current_playlist and self.current_playlist.get_name() == pl_name:
            self._switch_to_player()
            return

        self.status.set("Loading playlist...")
        try:
            self._load_playlist(self.selected_playlist_idx, auto_play=False)
            self._switch_to_player()
            self.loop.set_alarm_in(0.1, lambda l, d: self._start_playback())

            # Start background downloads for missing tracks
            missing = get_missing_tracks(pl_name)
            if missing:
                self.loop.set_alarm_in(
                    1.0,
                    lambda l, d: self._start_background_downloads(
                        missing, default_playlist=pl_name
                    ),
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

        def find_deletable_cache_files() -> tuple[list[Path], int]:
            """
            Return (files, total_bytes) for cache files that appear unused by other playlists.
            This is best-effort and intentionally conservative.
            """
            try:
                data = load_playlist(pl_name)
            except Exception:
                return [], 0

            tracks = data.get("tracks", []) or []

            other_urls: set[str] = set()
            other_cache_paths: set[Path] = set()
            cache_root = self.downloader.cache_dir.resolve()

            for other in self.playlists:
                if other == pl_name:
                    continue
                try:
                    other_data = load_playlist(other)
                except Exception:
                    continue
                for t in other_data.get("tracks", []) or []:
                    url = t.get("url")
                    if url:
                        other_urls.add(url)
                        cached = self.downloader.is_cached(
                            url, title=t.get("title"), artist=t.get("artist")
                        )
                        if cached:
                            p = Path(cached).resolve()
                            try:
                                p.relative_to(cache_root)
                            except ValueError:
                                continue
                            other_cache_paths.add(p)

            candidates: dict[Path, int] = {}
            for t in tracks:
                url = t.get("url")
                if not url:
                    continue
                # If the same URL exists in other playlists, assume shared and keep cache.
                if url in other_urls:
                    continue
                cached = self.downloader.is_cached(
                    url, title=t.get("title"), artist=t.get("artist")
                )
                if not cached:
                    continue
                p = Path(cached).resolve()
                try:
                    p.relative_to(cache_root)
                except ValueError:
                    continue
                if p in other_cache_paths:
                    continue
                try:
                    size = p.stat().st_size if p.exists() else 0
                except Exception:
                    size = 0
                candidates[p] = max(candidates.get(p, 0), size)

            files = sorted(candidates.keys())
            total_bytes = sum(candidates.values())
            return files, total_bytes

        def delete_cache_files(paths: list[Path]):
            deleted = 0
            deleted_bytes = 0
            for p in paths:
                try:
                    if p.exists():
                        try:
                            deleted_bytes += p.stat().st_size
                        except Exception:
                            pass
                        p.unlink()
                        deleted += 1
                except Exception:
                    pass
            if deleted:
                mb = deleted_bytes / (1024 * 1024)
                self.log_activity(
                    f"Cache cleaned: {deleted} file(s) ({mb:.1f} MB)", "info"
                )
                self.status.set(f"Cache cleaned: {deleted} file(s) ({mb:.1f} MB) ✓")
            else:
                self.status.set("No cache files deleted")

        def confirm_delete():
            try:
                # Stop any pending downloads for this playlist
                try:
                    self.download_manager.cancel_playlist(
                        pl_name, cancel_in_progress=True
                    )
                except Exception:
                    pass
                if (
                    self._pending_autoplay
                    and self._pending_autoplay.get("playlist") == pl_name
                ):
                    self._pending_autoplay = None

                cache_files, cache_bytes = find_deletable_cache_files()

                delete_playlist(pl_name)
                logger.info(f"Deleted playlist: {pl_name}")

                # Refresh playlists and menu
                self.playlists = list_playlists()
                self.selected_playlist_idx = None
                self._switch_to_menu()
                self.status.set(f"Deleted '{pl_name}' ✓")

                if cache_files:
                    mb = cache_bytes / (1024 * 1024)
                    self._show_confirm_dialog(
                        "Delete Cache Too?",
                        f"Delete {len(cache_files)} cached file(s) ({mb:.1f} MB) that look unused?",
                        on_confirm=lambda: delete_cache_files(cache_files),
                        on_cancel=lambda: self.status.set("Cache kept"),
                    )
            except Exception as e:
                logger.error(f"Failed to delete playlist: {e}")
                self.status.set(f"Error deleting playlist: {e}")

        self._show_confirm_dialog(
            "Delete Playlist",
            f"Are you sure you want to delete '{pl_name}'?",
            on_confirm=confirm_delete,
            on_cancel=lambda: self.status.set("Delete cancelled"),
        )

    def _on_rename_selected(self):
        """Rename the currently selected playlist."""
        if self.selected_playlist_idx is None or self.selected_playlist_idx >= len(
            self.playlists
        ):
            return

        old_name = self.playlists[self.selected_playlist_idx]

        def on_rename_confirm(new_name):
            if not new_name or new_name == old_name:
                return

            try:
                self.playlist_manager.rename_playlist(old_name, new_name)

                # Refresh list
                self.playlists = list_playlists()

                # Try to keep selection on renamed item
                try:
                    new_idx = self.playlists.index(new_name)
                    self.selected_playlist_idx = new_idx
                except ValueError:
                    self.selected_playlist_idx = 0

                self.status.set(f"Renamed '{old_name}' to '{new_name}' ✓")
                self._switch_to_menu()

            except Exception as e:
                self._handle_error(e, "rename_playlist")
                self._switch_to_menu()

        self._show_input_dialog(f"Rename '{old_name}'", "New Name", on_rename_confirm)

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
        self._start_download_event_pump()

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
            self._start_background_downloads(all_missing, start_delay=0.1)
        else:
            self.status.set("All playlists fully cached! ✓")

    def refresh(self, loop=None, data=None):
        if self.state == UIState.PLAYER or getattr(
            self, "_player_overlay_active", False
        ):
            self._advance_skin_frame()
            self._render_skin()
            if loop:
                self.refresh_alarm = loop.set_alarm_in(0.2, self.refresh)

    def _advance_skin_frame(self) -> None:
        if not self.skin_frames or len(self.skin_frames) < 2:
            return
        now = time.time()
        if now < self._skin_next_frame_at:
            return
        self._skin_frame_index = (self._skin_frame_index + 1) % len(self.skin_frames)
        self.skin_lines = self.skin_frames[self._skin_frame_index]
        self._skin_next_frame_at = now + max(0.05, float(self._skin_frame_interval_sec))

    def _render_skin(self):
        if self.current_playlist:
            track = self.current_playlist.get_current_track()
            if track:
                cached_path = self.downloader.is_cached(
                    track.url, title=track.title, artist=track.artist
                )
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
            "STATUS": (
                "♪"
                if self.player.is_playing()
                else ("⌛" if self.is_buffering else "■")
            ),
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

                # Use peek_next() for clean next track prediction
                next_track = self.current_playlist.peek_next()
                if next_track:
                    context["NEXT_TRACK"] = next_track.title[:30]

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
                self.skin_frames = None
                self._skin_frame_index = 0
                self._skin_next_frame_at = 0.0

                is_frames = bool(lines) and isinstance(lines[0], list)
                if is_frames:
                    self.skin_frames = [
                        pad_lines(frame, PAD_WIDTH, PAD_HEIGHT) for frame in lines
                    ]
                    self.skin_lines = self.skin_frames[0]

                    interval = None
                    fps = meta.get("fps") or meta.get("frame_rate")
                    delay = (
                        meta.get("frame_delay")
                        or meta.get("frame_interval")
                        or meta.get("animation_delay")
                    )
                    if fps is not None:
                        try:
                            interval = 1.0 / float(fps)
                        except (TypeError, ValueError, ZeroDivisionError):
                            interval = None
                    if interval is None and delay is not None:
                        try:
                            interval = float(delay)
                        except (TypeError, ValueError):
                            interval = None
                    self._skin_frame_interval_sec = (
                        interval if interval is not None else 0.5
                    )
                    self._skin_next_frame_at = time.time() + float(
                        self._skin_frame_interval_sec
                    )
                else:
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
        if not self.current_playlist or not self.current_playlist.tracks:
            return
        if index < 0 or index >= len(self.current_playlist.tracks):
            return

        # Respect shuffle order when selecting the track to play
        self.current_playlist.current_index = index
        track = self.current_playlist.get_current_track()
        if not track:
            return

        # SOTA Check: Skip unusable tracks (Private/Deleted)
        title = track.title or ""
        if title in ["[Private video]", "[Deleted video]"]:
            logger.info(f"Skipping unusable track: {title}")
            self.status.notify(f"⏭ Skipping {title}...")

            # Persist unplayable state
            if self.current_playlist and self.current_playlist.metadata.get("name"):
                self.playlist_manager.mark_track_unplayable(
                    self.current_playlist.metadata["name"], track.url, title
                )

            self.loop.set_alarm_in(0.5, lambda l, d: self._next_track())
            return

        self._update_loading_message(f"Buffering: {track.title}...")
        # Track request ID to handle rapid skipping
        self._play_req_id = getattr(self, "_play_req_id", 0) + 1
        current_req = self._play_req_id

        try:
            cached_path = self.downloader.is_cached(
                track.url, title=track.title, artist=track.artist
            )
            if cached_path:
                self.player.play(cached_path)
                self.is_cached_playback = True
                self.status.set(f"♪ {track.title} (cached)")
            else:
                # Stop current playback before streaming
                self.player.stop()

                # Stream it asynchronously
                self.status.set(f"Buffering {track.title}...")
                self.is_cached_playback = False
                self.is_buffering = True
                # Force instant render to show hourglass
                self._render_skin()
                self.loop.draw_screen()

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
                            # Reset buffering flag on error
                            self.loop.set_alarm_in(
                                0, lambda l, d: setattr(self, "is_buffering", False)
                            )
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
            self.is_buffering = False
            self.player.play(stream_url)
            self.status.set(f"♪ {track.title} (streaming) | " + HELP_TEXT)
        except Exception as e:
            logger.error(f"Playback failed: {e}")
            self.is_buffering = False
            self._next_track()

    def _show_track_picker(self):
        """Popup track list to jump to a specific song in the current playlist."""
        if not self.current_playlist or not self.current_playlist.tracks:
            return

        pl_name = self.current_playlist.get_name()
        current_track = self.current_playlist.get_current_track()
        current_idx = 0
        if current_track:
            try:
                current_idx = next(
                    i
                    for i, t in enumerate(self.current_playlist.tracks)
                    if t.url == current_track.url
                )
            except StopIteration:
                current_idx = 0

        def close_overlay():
            self._player_overlay_active = False
            self.state = UIState.PLAYER
            self.main_widget.original_widget = self.skin_widget

        def on_select(original_idx: int):
            close_overlay()
            self.current_playlist.set_position_by_original_index(int(original_idx))
            self._play_current_track(self.current_playlist.current_index)

        dialog = TrackPickerDialog(
            pl_name,
            list(self.current_playlist.tracks),
            current_idx,
            on_select,
            close_overlay,
        )
        height = min(30, max(10, len(self.current_playlist.tracks) + 6))
        overlay = urwid.Overlay(
            dialog,
            self.skin_widget,
            align="center",
            width=90,
            valign="middle",
            height=height,
        )
        self._player_overlay_active = True
        self.state = UIState.EDIT
        self.main_widget.original_widget = overlay

    def _on_track_end_callback(self):
        """Called by VLC when track ends (runs in VLC thread)."""
        # Schedule next track in main thread to avoid urwid thread-safety issues
        if hasattr(self, "loop") and self.loop:
            self.loop.set_alarm_in(0.1, lambda loop, user_data: self._next_track())

    def _next_track(self):
        if not self.current_playlist or not self.current_playlist.tracks:
            return False

        # Repeat single track
        if self.current_playlist.repeat_mode == RepeatMode.TRACK:
            self._play_current_track(self.current_playlist.current_index)
            return True

        next_idx = self.current_playlist.current_index + 1
        if next_idx >= len(self.current_playlist.tracks):
            if self.current_playlist.repeat_mode == RepeatMode.PLAYLIST:
                next_idx = 0
            else:
                self.player.stop()
                self.status.set("Playlist finished • Press M for menu")
                return False

        self._play_current_track(next_idx)
        return True

    def _prev_track(self):
        if not self.current_playlist or not self.current_playlist.tracks:
            return

        prev_idx = self.current_playlist.current_index - 1
        if prev_idx < 0:
            prev_idx = len(self.current_playlist.tracks) - 1

        self._play_current_track(prev_idx)

    def cleanup(self):
        self._stop_animation()
        try:
            if self.refresh_alarm:
                self.loop.remove_alarm(self.refresh_alarm)
            if self.spinner_alarm:
                self.loop.remove_alarm(self.spinner_alarm)
            if getattr(self, "_download_event_alarm", None):
                try:
                    self.loop.remove_alarm(self._download_event_alarm)
                except Exception:
                    pass
                self._download_event_alarm = None
            if getattr(self, "download_manager", None):
                self.download_manager.stop(cancel_in_progress=True)
            self.player.cleanup()
        except Exception:
            pass

    # ---------- animation system ----------
    def _toggle_animation(self):
        """Toggle the animation overlay/widget in the footer."""
        if not self.available_animations:
            self.status.notify("No animations found in animations/ folder")
            return

        self.animation_active = not self.animation_active

        if self.animation_active:
            # Load current animation if not loaded
            if self.available_animations:
                anim_name = self.available_animations[self.current_animation_idx]
                if (
                    not self.animation_widget.is_loaded()
                    or self.animation_widget.get_current_animation() != anim_name
                ):
                    self.animation_widget.load_animation(anim_name)
                    self.status.notify(f"Animation: {anim_name} (A=Toggle V=Next)")

            # Switch footer content to animation widget
            self.footer_content.original_widget = self.animation_widget
            self._start_animation()
        else:
            # Switch back to message log
            self._stop_animation()
            self.footer_content.original_widget = self.message_log
            self.status.clear_notify()

    def _start_animation(self):
        """Start the animation loop."""
        if self.animation_alarm:
            self.loop.remove_alarm(self.animation_alarm)

        # Initial draw
        self.animation_widget.advance_frame()
        interval = self.animation_widget.get_interval()
        self.animation_alarm = self.loop.set_alarm_in(interval, self._animate_loop)

    def _stop_animation(self):
        """Stop the animation loop."""
        if self.animation_alarm:
            self.loop.remove_alarm(self.animation_alarm)
            self.animation_alarm = None

    def _animate_loop(self, loop, data):
        """Animation loop callback."""
        if not self.animation_active:
            return

        self.animation_widget.advance_frame()
        interval = self.animation_widget.get_interval()
        self.animation_alarm = loop.set_alarm_in(interval, self._animate_loop)

    def _next_animation(self):
        """Switch to next available animation."""
        if not self.available_animations or not self.animation_active:
            return

        self.current_animation_idx = (self.current_animation_idx + 1) % len(
            self.available_animations
        )
        anim_name = self.available_animations[self.current_animation_idx]
        self.animation_widget.load_animation(anim_name)
        self.status.notify(f"Animation: {anim_name}")

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
        # Ignore global hotkeys while in dialogs/overlays
        if self.state == UIState.EDIT:
            if key in ("q", "Q"):
                self._cancel_background_downloads()
                self.cleanup()
                raise urwid.ExitMainLoop()
            return
        if self.state == UIState.MENU:
            if key in ("i", "I"):
                logger.debug("[KEY] Calling _prompt_import_playlist()")
                self._prompt_import_playlist()
            elif key.isdigit() and "1" <= key <= "9":
                idx = int(key) - 1
                if idx < len(self.playlists):
                    self._on_playlist_select(None, idx)
            elif key.upper() in self.skin_hotkeys:
                idx = self.skin_hotkeys.index(key.upper())
                if idx < len(self.skins):
                    self._on_skin_select(None, idx)
            elif key in ("p", "P"):
                self._on_play_selected()
            elif key in ("x", "X"):
                self._on_delete_selected()
            elif key in ("r", "R"):
                self._on_random_all()
            elif key in ("e", "E"):
                # Defer to next tick so the overlay isn't clobbered by the current input cycle
                self.loop.set_alarm_in(0, lambda l, d: self._on_rename_selected())
            return
        if key == " ":
            self.player.toggle_pause()
        elif key in ("n", "N"):
            self._next_track()
        elif key in ("p", "P"):
            self._prev_track()
        elif key in ("t", "T"):
            self._show_track_picker()
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
        elif key in ("a", "A"):
            self._toggle_animation()
        elif key in ("v", "V"):
            self._next_animation()


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
        logger.critical("Critical Error: %s", e, exc_info=(type(e), e, e.__traceback__))
        print(f"\n❌ Critical Error: {e}")
        import traceback

        traceback.print_exception(type(e), e, e.__traceback__)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
