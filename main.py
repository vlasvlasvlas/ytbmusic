import os
import queue
import shutil
import signal
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Any, List

import urwid

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
from ui.background_loader import BackgroundLoader
from ui.animation_loader import AnimationLoader, AnimationWidget
from ui.views.player_view import PlayerView, pad_lines
from ui.dialogs import InputDialog, ConfirmDialog
from ui.gradient_background import GradientRenderer
from ui.widgets import StatusBar, MessageLog
from core.stream_broadcaster import StreamBroadcaster, check_ffmpeg_available
from config.i18n import t

logger = setup_logging()


HELP_TEXT = "Space=⏯ N/P=⏭⏮ ←/→=Seek ↑/↓=Vol S=Skin A=Anim V=NextAnim M=Menu Q=Quit"
PAD_WIDTH = 120
PAD_HEIGHT = 88
SKIN_HOTKEYS = "BCDGHJKL"  # skip A (Animation), E (Rename), F (Search), I (Import)


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


# StatusBar and MessageLog are now imported from ui.widgets


class ListDialog(urwid.WidgetWrap):
    """Generic list selector dialog with optional disclaimer."""

    def __init__(
        self,
        title: str,
        items: List[dict],
        on_select,
        on_cancel=None,
        disclaimer: str = None,
    ):
        self.on_select = on_select
        self.on_cancel = on_cancel

        walker = urwid.SimpleFocusListWalker([])
        walker.append(urwid.Text(("title", f" {title} "), align="center"))
        walker.append(urwid.Divider("─"))
        if disclaimer:
            walker.append(urwid.Text(("error", disclaimer), align="center"))
            walker.append(urwid.Divider())

        first_focus = None
        for entry in items:
            label = entry.get("label", "")
            value = entry.get("value", label)
            note = entry.get("note")
            btn = urwid.Button(label)
            urwid.connect_signal(btn, "click", lambda b, v=value: self._do_select(v))
            widget = urwid.AttrMap(btn, None, focus_map="highlight")
            walker.append(widget)
            if note:
                walker.append(urwid.Text(("info", f"   {note}")))
            if first_focus is None:
                first_focus = len(walker) - 1

        if first_focus is not None:
            try:
                walker.set_focus(first_focus)
            except Exception:
                pass

        walker.append(urwid.Divider())
        walker.append(
            urwid.Text("↑/↓ Navegar • Enter seleccionar • Esc/Q cerrar", align="center")
        )

        listbox = urwid.ListBox(walker)
        frame = urwid.Frame(body=listbox)
        super().__init__(urwid.LineBox(frame))

    def _do_select(self, value):
        if self.on_select:
            self.on_select(value)

    def keypress(self, size, key):
        if key in ("esc", "q", "Q"):
            if self.on_cancel:
                self.on_cancel()
            return None
        return super().keypress(size, key)


class ModalOverlay(urwid.WidgetWrap):
    """Generic modal with ESC/Q close support."""

    def __init__(self, title: str, body: urwid.Widget, on_close=None):
        self._on_close = on_close
        header = urwid.Text(("title", f" {title} "), align="center")
        frame = urwid.Frame(body=body, header=header)
        super().__init__(urwid.LineBox(frame))

    def keypress(self, size, key):
        if key in ("esc", "q", "Q"):
            if self._on_close:
                self._on_close()
            return None
        return super().keypress(size, key)


class TrackPickerDialog(urwid.WidgetWrap):
    """Scrollable track picker overlay for the current playlist."""

    def __init__(
        self,
        title: str,
        tracks: list,
        current_idx: int,
        on_select,
        on_cancel,
        status_checker=None,
    ):
        self._on_select = on_select
        self._on_cancel = on_cancel
        self.status_checker = status_checker

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
            attr = "normal"
            if self.status_checker:
                status = self.status_checker(self._tracks[original_index])
                if status == "downloaded":
                    attr = "track_downloaded"
                elif status == "downloading":
                    attr = "track_downloading"
                elif status == "missing":
                    attr = "track_missing"

            self._walker.append(urwid.AttrMap(btn, attr, focus_map="highlight"))

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
    def __init__(
        self,
        downloader: Optional[YouTubeDownloader] = None,
        download_manager: Optional[DownloadManager] = None,
        player: Optional[MusicPlayer] = None,
        playlist_manager: Optional[PlaylistManager] = None,
        skin_loader: Optional[SkinLoader] = None,
        download_events_queue: "Optional[queue.Queue[dict]]" = None,
    ):
        # Core components
        # Core components
        self.player = player or MusicPlayer()
        self.player.on_end_callback = self._on_track_end_callback
        self.downloader = downloader or YouTubeDownloader(cache_dir="cache")
        self.playlist_manager = playlist_manager or PlaylistManager(
            playlists_dir="playlists"
        )
        self.skin_loader = skin_loader or SkinLoader()
        self.background_loader = BackgroundLoader()

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

        # Backgrounds
        self.backgrounds = BackgroundLoader.list_available_backgrounds()
        self.current_background_idx = 0
        self.current_background_meta = None
        self._background_alarm = None
        self._background_cycle = []
        self._background_cycle_idx = 0
        self._background_palette_name = "skin_bg_active"

        # Gradient animation state (demoscene mode)
        self._gradient_renderer = None
        self._gradient_active = False
        self._gradient_alarm = None

        # Streaming config
        self._stream_config_path = Path("config") / "stream_config.json"
        self._load_stream_config()

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
        # Download manager (single worker, priority queue)
        self._download_events: "queue.Queue[dict]" = (
            download_events_queue or queue.Queue()
        )
        self._download_event_alarm = None
        self._download_request_summary: Dict[str, Dict[str, int]] = {}
        self._active_download_request_id: Optional[str] = None
        self._auto_download_request_id = new_request_id("AUTO")
        self._pending_autoplay: Optional[Dict[str, str]] = None
        self._player_overlay_active = False
        self._cookie_prompt_active = False
        self._settings_overlay_active = False
        self._diagnostic_overlay_active = False
        self._precheck_done = False
        self._precheck_result: Dict[str, str] = {}
        self._last_download_error: str = ""
        self._last_download_error_context: str = ""
        self._last_cache_scan = None
        self._settings_update_fn = None
        self._track_index: list[dict] = []
        self._track_index_dirty = True
        self._stream_config = {}
        self._stream_config_source = "default"
        self._input_overlay_active = False

        if download_manager:
            self.download_manager = download_manager
            # Assume it's started by the caller
        else:
            self.download_manager = DownloadManager(
                self.downloader,
                event_callback=self._download_events.put,
                progress_throttle_sec=0.25,
            )
            self.download_manager.start()

        # Widgets
        self.player_view = PlayerView(self)
        self.skin_widget = self.player_view.widget
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
                ("error_toast", "white", "dark red"),
                ("success_toast", "black", "light green"),
                ("track_downloaded", "light green", ""),
                ("track_missing", "light red", ""),
                ("track_downloading", "yellow", ""),
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
        Returns (downloaded_count, total_playable_count).
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

            total = 0
            downloaded = 0

            for track in pl.tracks:
                # Skip unplayable tracks (deleted/private/unavailable)
                if getattr(track, "is_playable", True) is False:
                    continue
                total += 1
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
        from ui.views.menu_view import MenuView

        return MenuView(self).create()

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

    def _show_input_dialog(self, title, label, callback, default_text=""):
        """Show a modal input dialog."""

        def on_done(text):
            # Restore previous widget
            self._input_overlay_active = False
            self.state = UIState.MENU
            self.main_widget.original_widget = self.menu_widget
            # Postpone callback to avoid freezing during keypress
            self.loop.set_alarm_in(0, lambda l, d: callback(text))

        # Keep menu visible underneath but freeze state so bg refresh doesn't replace overlay
        self.state = UIState.EDIT
        self._input_overlay_active = True
        dialog = InputDialog(title, label, on_done, default_text=default_text)
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
        """Show a modal yes/no confirmation dialog."""

        # Save previous widget to restore later
        previous_widget = self.main_widget.original_widget

        def cleanup():
            self.state = UIState.MENU
            self.main_widget.original_widget = self.menu_widget

        def wrapped_confirm():
            cleanup()
            # Defer execution to avoid callback recursion issues
            self.loop.set_alarm_in(0, lambda l, d: on_confirm())

        def wrapped_cancel():
            cleanup()
            if on_cancel:
                self.loop.set_alarm_in(0, lambda l, d: on_cancel())

        # Set state to EDIT to block global hotkeys in main loop
        self.state = UIState.EDIT

        dialog = ConfirmDialog(title, message, wrapped_confirm, wrapped_cancel)

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
        if getattr(self, "_input_overlay_active", False):
            return
        self.state = UIState.MENU
        self.status.update_context("menu")
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
        self._invalidate_track_index()
        self.menu_widget = self._create_menu()
        self.main_widget.original_widget = self.menu_widget

        # Always set context message
        if self.playlists and self.skins:
            skin_keys_label = self._skin_keys_label()
            self.status.set(
                f"Select playlist (1-9) or skin ({skin_keys_label}) • O Settings • Q to quit"
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
        self.status.update_context("player")
        self._player_overlay_active = False
        if self.spinner_alarm:
            self.loop.remove_alarm(self.spinner_alarm)
            self.spinner_alarm = None
        self.main_widget.original_widget = self.skin_widget
        # Reapply background palette for player canvas
        if self.current_background_meta or self.backgrounds:
            self._apply_background_by_idx(self.current_background_idx)
        if self.refresh_alarm:
            self.loop.remove_alarm(self.refresh_alarm)
        self.refresh_alarm = self.loop.set_alarm_in(0.2, self.refresh)

    # ---------- helpers ----------
    def _handle_error(self, error: Exception, context: str = ""):
        error_msg = str(error)[:60]
        self.status.notify(f"❌ Error: {error_msg}", style="error_toast")
        # Auto-clear after 5 seconds
        self.loop.set_alarm_in(5.0, lambda l, d: self.status.clear_notify())
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

    def _format_bytes(self, num: float) -> str:
        """Human-friendly byte formatter."""
        try:
            num = float(num)
        except Exception:
            return "0 B"

        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if num < 1024 or unit == "TB":
                return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} {unit}"
            num /= 1024.0
        return f"{num:.1f} TB"

    def _run_preflight_checks(self, *, force: bool = False, silent: bool = False):
        """Lightweight environment check (VLC + cookies + versions)."""
        if self._precheck_done and not force:
            return self._precheck_result

        warnings = []
        result: Dict[str, str] = {}

        try:
            vlc_version = self.player.get_backend_version()
            result["vlc_version"] = vlc_version
            if not vlc_version:
                warnings.append("VLC no detectado")
        except Exception:
            result["vlc_version"] = ""
            warnings.append("VLC no inicializado")

        try:
            versions = self.downloader.get_versions()
            result["yt_dlp_version"] = versions.get("yt_dlp", "")
            result["python_version"] = versions.get("python", "")
        except Exception:
            warnings.append("yt-dlp no disponible")

        try:
            cookie_status = self.downloader.get_cookie_status()
            result["cookies"] = cookie_status
            warning = cookie_status.get("warning")
            if warning:
                warnings.append(warning)
            elif cookie_status.get("mode") in ("none", "disabled"):
                warnings.append("Sin cookies; YouTube puede bloquear descargas")
        except Exception:
            warnings.append("No se pudo leer estado de cookies")

        result["checked_at"] = time.time()
        self._precheck_result = result
        self._precheck_done = True

        if not silent:
            if warnings:
                self.status.notify(f"Pre-check: {' | '.join(warnings)}", "error_toast")
            else:
                self.status.set("Entorno listo ✓")

        return result

    def _compute_cache_state(self) -> Dict[str, Any]:
        """Scan cache directory and detect orphaned files."""
        cache_dir = getattr(self.downloader, "cache_dir", Path("cache"))
        if not isinstance(cache_dir, Path):
            cache_dir = Path(cache_dir)

        total_size = 0
        total_files = 0
        expected_stems = set()

        for pl_name in self.playlists:
            try:
                pl = self.playlist_manager.load_playlist(pl_name)
            except Exception:
                continue

            for track in getattr(pl, "tracks", []):
                if getattr(track, "is_playable", True) is False:
                    continue
                try:
                    candidates = self.downloader.cache_candidates(
                        getattr(track, "url", ""),
                        getattr(track, "title", None),
                        getattr(track, "artist", None),
                    )
                except Exception:
                    continue
                for cand in candidates:
                    expected_stems.add(Path(cand).stem)

        orphans = []
        try:
            cache_dir.mkdir(exist_ok=True)
            for f in cache_dir.glob("*"):
                if not f.is_file():
                    continue
                total_files += 1
                try:
                    total_size += f.stat().st_size
                except Exception:
                    pass
                if f.stem not in expected_stems:
                    orphans.append(f)
        except Exception as e:
            logger.warning(f"Cache scan failed: {e}")

        orphan_size = 0
        for f in orphans:
            try:
                orphan_size += f.stat().st_size
            except Exception:
                pass

        snapshot = {
            "total_files": total_files,
            "total_size": total_size,
            "orphans": orphans,
            "orphan_size": orphan_size,
            "expected": len(expected_stems),
            "cache_dir": str(cache_dir),
            "timestamp": time.time(),
        }
        self._last_cache_scan = snapshot
        return snapshot

    def _normalize_color(self, value: Optional[str]) -> str:
        """
        Convert color strings to urwid-friendly names.
        If hex (#rrggbb), degrade to basic names by luminance.
        """
        if not value:
            return "white"
        v = value.strip().lower()
        basic_colors = {
            "black",
            "white",
            "dark gray",
            "light gray",
            "dark red",
            "dark green",
            "dark blue",
            "dark cyan",
            "light red",
            "light green",
            "light blue",
            "light cyan",
            "yellow",
            "brown",
        }
        if v in basic_colors:
            return v
        if v.startswith("#") and len(v) == 7:
            try:
                r = int(v[1:3], 16) / 255.0
                g = int(v[3:5], 16) / 255.0
                b = int(v[5:7], 16) / 255.0
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                if lum < 0.2:
                    return "black"
                if lum < 0.4:
                    return "dark gray"
                if lum < 0.7:
                    return "light gray"
                return "white"
            except Exception:
                return "white"
        return v

    def _friendly_error_message(self, err: str) -> Optional[str]:
        """Map raw yt-dlp errors to actionable tips."""
        if not err:
            return None
        err_l = err.lower()

        if "429" in err_l or "too many requests" in err_l:
            return "Rate-limit de YouTube. Reintentando con backoff; podés refrescar cookies en Settings."
        if (
            "sign in to confirm you're not a bot" in err_l
            or "confirm you're not a bot" in err_l
        ):
            return (
                "YouTube pidió verificación. Refrescá cookies (Settings) y reintentá."
            )
        if "private" in err_l:
            return "Video privado. Se marcará como no reproducible."
        if "blocked" in err_l or "forbidden" in err_l:
            return "Bloqueo de acceso (403). Podría requerir cookies o proxy."
        return None

    def _load_stream_config(self):
        """Load stream config from env or config file."""
        cfg = {
            "url": "",
            "user": "",
            "password": "",
            "bitrate": 128,
            "format": "mp3",
        }
        source = "default"

        env_url = os.environ.get("YTBMUSIC_STREAM_URL")
        env_user = os.environ.get("YTBMUSIC_STREAM_USER")
        env_pass = os.environ.get("YTBMUSIC_STREAM_PASS")
        if env_url:
            cfg["url"] = env_url
            source = "env"
        if env_user:
            cfg["user"] = env_user
            source = "env"
        if env_pass:
            cfg["password"] = env_pass
            source = "env"

        try:
            cfg_path = self._stream_config_path
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            if cfg_path.exists():
                import json

                with cfg_path.open("r", encoding="utf-8") as f:
                    file_cfg = json.load(f)
                cfg.update({k: v for k, v in file_cfg.items() if v is not None})
                source = "file"
        except Exception as e:
            logger.warning(f"Failed to load stream config: {e}")

        self._stream_config = cfg
        self._stream_config_source = source

    def _save_stream_config(self, cfg: Dict[str, Any]):
        """Persist stream config to config/stream_config.json."""
        import json

        try:
            cfg_path = self._stream_config_path
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            with cfg_path.open("w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            self._stream_config = cfg
            self._stream_config_source = "file"
            self.status.set("Stream config guardada")
            self.log_activity("Stream config guardada", "info")
        except Exception as e:
            self._handle_error(e, "save_stream_config")

    def _invalidate_track_index(self):
        self._track_index_dirty = True

    def _rebuild_track_index(self) -> list[dict]:
        """Index all playable tracks across playlists for global search."""
        index: list[dict] = []
        for pl_name in self.playlists:
            try:
                pl = self.playlist_manager.load_playlist(pl_name)
            except Exception:
                continue
            for idx, track in enumerate(getattr(pl, "tracks", []) or []):
                if getattr(track, "is_playable", True) is False:
                    continue
                title = getattr(track, "title", "") or ""
                artist = getattr(track, "artist", "") or ""
                index.append(
                    {
                        "playlist": pl_name,
                        "index": idx,
                        "title": title,
                        "artist": artist,
                        "title_l": title.lower(),
                        "artist_l": artist.lower(),
                    }
                )
        self._track_index = index
        self._track_index_dirty = False
        return index

    def _ensure_track_index(self) -> list[dict]:
        if self._track_index_dirty or not self._track_index:
            return self._rebuild_track_index()
        return self._track_index

    def _filter_track_index(self, query: str) -> list[dict]:
        """Return matches (case-insensitive) from the global index."""
        q = (query or "").lower().strip()
        if not q:
            return []
        index = self._ensure_track_index()
        matches = []
        for entry in index:
            if q in entry.get("title_l", "") or q in entry.get("artist_l", ""):
                matches.append(entry)
        return matches

    def _map_track_index_for_shuffle(self, target_idx: int) -> int:
        """Map absolute track idx to current shuffle position if needed."""
        if not self.current_playlist:
            return target_idx
        if getattr(self.current_playlist, "shuffle_enabled", False) and getattr(
            self.current_playlist, "_shuffle_order", None
        ):
            try:
                return self.current_playlist._shuffle_order.index(target_idx)
            except ValueError:
                return target_idx
        return target_idx

    def _play_search_result(self, result: dict):
        """Load playlist and play the selected track from search results."""
        pl_name = result.get("playlist") or ""
        track_idx = int(result.get("index", 0) or 0)

        # Close overlay if open
        try:
            self._close_modal_overlay()
        except Exception:
            pass

        if not pl_name:
            self.status.set("No playlist selected")
            return

        try:
            self._load_playlist_by_name(pl_name)
        except Exception as e:
            self._handle_error(e, "search_load_playlist")
            self._switch_to_menu()
            return

        try:
            self.selected_playlist_idx = self.playlists.index(pl_name)
        except Exception:
            pass

        if not self.current_playlist:
            self.status.set("No playlist loaded")
            return

        mapped_idx = self._map_track_index_for_shuffle(track_idx)
        self._switch_to_player()
        title = (result.get("title") or "")[:40]
        self.status.notify(f"▶ {title} ({pl_name})")

        # Slight delay to ensure UI switches before starting playback
        self.loop.set_alarm_in(0.05, lambda l, d: self._play_current_track(mapped_idx))

    def _show_search_results(self, query: str, results: list[dict], total: int):
        """Display search results in a modal list; Enter plays the track."""
        header = urwid.Text(
            ("title", f" Resultados {len(results)}/{total} para '{query}' "),
            align="center",
        )
        walker = urwid.SimpleFocusListWalker([header, urwid.Divider("─")])
        first_focus = None

        if total > len(results):
            walker.append(
                urwid.Text(
                    f"Mostrando primeros {len(results)} resultados (de {total})",
                    align="center",
                )
            )
            walker.append(urwid.Divider())

        for entry in results:
            label = f"[{entry.get('playlist')}] {entry.get('title') or ''} — {entry.get('artist') or ''}"
            btn = urwid.Button(label)
            urwid.connect_signal(
                btn, "click", lambda b, e=entry: self._play_search_result(e)
            )
            walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))
            if first_focus is None:
                first_focus = len(walker) - 1

        walker.append(urwid.Divider())
        walker.append(
            urwid.Text("↑/↓ Navegar • Enter reproducir • Esc/Q cerrar", align="center")
        )

        if first_focus is not None:
            try:
                walker.set_focus(first_focus)
            except Exception:
                pass

        listbox = urwid.ListBox(walker)
        modal = ModalOverlay(
            t("modal.search_playlists"), listbox, on_close=self._close_modal_overlay
        )
        overlay = urwid.Overlay(
            modal,
            self.menu_widget,
            align="center",
            width=90,
            valign="middle",
            height=26,
        )
        self.state = UIState.EDIT
        self.main_widget.original_widget = overlay

    def _perform_global_search(self, query: str):
        q = (query or "").strip()
        if not q:
            self.status.set("Ingresa texto para buscar")
            return
        try:
            matches = self._filter_track_index(q)
        except Exception as e:
            self._handle_error(e, "global_search")
            return

        if not matches:
            self.status.set(f"Sin resultados: '{q}'")
            return

        # Limit to keep UI responsive
        limited = matches[:200]
        self._show_search_results(q, limited, total=len(matches))

    def _prompt_global_search(self):
        """Open input dialog to search across all playlists."""

        def on_query_entered(text):
            if text is None:
                return
            self._perform_global_search(text)

        self._show_input_dialog(
            t("modal.search_all"),
            t("modal.search_text"),
            on_query_entered,
            default_text="",
        )

    def _collect_diagnostics_snapshot(self) -> Dict[str, Any]:
        precheck = self._run_preflight_checks(force=False, silent=True) or {}
        cache_state = self._last_cache_scan or self._compute_cache_state()
        try:
            dl_snapshot = self.download_manager.get_snapshot()
        except Exception:
            dl_snapshot = {"running": False, "queue_size": 0, "current": None}

        cookies = precheck.get("cookies", {}) if isinstance(precheck, dict) else {}
        versions = {}
        try:
            versions = self.downloader.get_versions()
        except Exception:
            pass

        active_task = dl_snapshot.get("current")
        return {
            "queue_running": dl_snapshot.get("running", False),
            "queue_size": dl_snapshot.get("queue_size", 0),
            "active_title": getattr(active_task, "title", "") if active_task else "",
            "active_playlist": (
                getattr(active_task, "playlist", "") if active_task else ""
            ),
            "bg_status": self._get_bg_download_status(),
            "last_error": self._last_download_error,
            "cache": cache_state,
            "cookies": cookies,
            "versions": versions,
            "vlc_version": precheck.get("vlc_version", ""),
        }

    def _build_diagnostics_body(self) -> urwid.Widget:
        snap = self._collect_diagnostics_snapshot()
        cache = snap.get("cache", {}) or {}
        lines = urwid.SimpleFocusListWalker([])

        lines.append(urwid.Text(("title", " Cola de descargas ")))
        lines.append(
            urwid.Text(
                f"Running: {snap.get('queue_running')}  |  Queue size: {snap.get('queue_size')}"
            )
        )
        if snap.get("bg_status"):
            lines.append(urwid.Text(f"Status: {snap.get('bg_status')}"))
        if snap.get("active_title"):
            lines.append(
                urwid.Text(
                    f"Procesando: {snap.get('active_title')}"
                    + (
                        f" ({snap.get('active_playlist')})"
                        if snap.get("active_playlist")
                        else ""
                    )
                )
            )

        lines.append(urwid.Divider("─"))
        lines.append(urwid.Text(("title", " Cache ")))
        cache_summary = f"Archivos: {cache.get('total_files', 0)} • Tamaño: {self._format_bytes(cache.get('total_size', 0))}"
        lines.append(urwid.Text(cache_summary))
        orphan_count = len(cache.get("orphans", []) or [])
        orphan_size = self._format_bytes(cache.get("orphan_size", 0))
        lines.append(urwid.Text(f"Huérfanos: {orphan_count} • Peso: {orphan_size}"))

        lines.append(urwid.Divider("─"))
        lines.append(urwid.Text(("title", " Dependencias ")))
        yt_dlp_version = (snap.get("versions") or {}).get("yt_dlp", "") or "?"
        vlc_version = snap.get("vlc_version") or "?"
        lines.append(urwid.Text(f"yt-dlp: {yt_dlp_version}"))
        lines.append(urwid.Text(f"VLC: {vlc_version}"))

        lines.append(urwid.Divider("─"))
        lines.append(urwid.Text(("title", " 🎧 Streaming ")))
        stream_cfg = getattr(self, "_stream_config", {}) or {}
        stream_src = getattr(self, "_stream_config_source", "default")
        stream_url = stream_cfg.get("url") or ""

        if stream_url:
            lines.append(urwid.AttrMap(urwid.Text(f"✅ URL: {stream_url}"), "success"))
            # Show shareable link
            if "/" in stream_url:
                base = stream_url.rsplit("/", 1)[0]
                mount = stream_url.rsplit("/", 1)[1].split("?")[0]
                lines.append(urwid.Text(f"🔗 Shareable: {base}/{mount}"))
        else:
            lines.append(urwid.Text("❌ URL: no configurado"))

        user_label = stream_cfg.get("user") or "anon"
        lines.append(
            urwid.Text(
                f"User: {user_label} | {stream_cfg.get('bitrate', 128)}kbps | {stream_cfg.get('format', 'mp3')}"
            )
        )
        lines.append(urwid.Text(f"Config source: {stream_src}"))

        lines.append(urwid.Divider("─"))
        lines.append(urwid.Text(("title", " Cookies ")))
        cookies = snap.get("cookies") or {}
        cookie_mode = cookies.get("mode") or "none"
        cookie_line = f"Modo: {cookie_mode}"
        if cookies.get("path"):
            cookie_line += f" • {cookies.get('path')}"
            exists = cookies.get("exists")
            if exists is False:
                cookie_line += " (no existe)"
        if cookies.get("browser"):
            cookie_line += f" • Browser: {cookies.get('browser')}"
        if cookies.get("warning"):
            lines.append(urwid.Text(("error", cookies.get("warning"))))
        lines.append(urwid.Text(cookie_line))

        lines.append(urwid.Divider("─"))
        lines.append(urwid.Text(("title", " Último error ")))
        last_err = snap.get("last_error") or "N/A"
        lines.append(urwid.Text(last_err))

        lines.append(urwid.Divider())
        lines.append(urwid.Text("↑/↓ mover • Esc/Q cerrar", align="center"))

        return urwid.ListBox(lines)

    def _close_modal_overlay(self):
        self.state = UIState.MENU
        self._settings_overlay_active = False
        self._diagnostic_overlay_active = False
        self._settings_update_fn = None
        self.main_widget.original_widget = self.menu_widget

    def _open_diagnostics_panel(self):
        if not self.menu_widget:
            return
        body = self._build_diagnostics_body()
        modal = ModalOverlay(
            t("modal.diagnostics"), body, on_close=self._close_modal_overlay
        )
        overlay = urwid.Overlay(
            modal,
            self.menu_widget,
            align="center",
            width=78,
            valign="middle",
            height=24,
        )
        self.state = UIState.EDIT
        self._diagnostic_overlay_active = True
        self.main_widget.original_widget = overlay

    def _open_diagnostics_from_settings(self):
        self._close_modal_overlay()
        self.loop.set_alarm_in(0, lambda l, d: self._open_diagnostics_panel())

    def _build_settings_list(self) -> urwid.Widget:
        precheck = self._run_preflight_checks(force=True, silent=True) or {}
        cache_state = self._last_cache_scan or self._compute_cache_state()

        walker = urwid.SimpleFocusListWalker([])
        walker.append(urwid.Text(("title", " Estado ")))

        vlc_version = precheck.get("vlc_version") or "no detectado"
        cookies = precheck.get("cookies") or {}
        cookie_mode = cookies.get("mode") or "none"
        cookie_path = cookies.get("path")
        cookie_exists = cookies.get("exists")
        cookie_warn = cookies.get("warning")
        yt_dlp_version = precheck.get("yt_dlp_version") or "?"

        env_line = urwid.Text(f"VLC: {vlc_version}")
        cookie_desc = f"Cookies: {cookie_mode}"
        if cookie_path:
            suffix = " (ok)" if cookie_exists else " (no existe)"
            cookie_desc += f" • {cookie_path}{suffix}"
        elif cookies.get("browser"):
            cookie_desc += f" • Browser: {cookies.get('browser')}"
        if cookie_warn:
            cookie_desc += f" • {cookie_warn}"
        cookie_line = urwid.Text(cookie_desc)
        ytdlp_line = urwid.Text(f"yt-dlp: {yt_dlp_version}")
        cache_line = urwid.Text(
            f"Cache: {cache_state.get('total_files',0)} archivos • {self._format_bytes(cache_state.get('total_size',0))}"
        )
        orphan_line = urwid.Text(
            f"Huérfanos: {len(cache_state.get('orphans', []) or [])} • {self._format_bytes(cache_state.get('orphan_size',0))}"
        )

        status_line = urwid.Text("")

        def set_status_line(msg: str, style: str = "info"):
            try:
                status_line.set_text((style, msg))
            except Exception:
                status_line.set_text(msg)

        walker.extend(
            [
                env_line,
                cookie_line,
                ytdlp_line,
                cache_line,
                orphan_line,
                urwid.Divider("─"),
            ]
        )
        walker.append(urwid.Text(("title", " Acciones ")))

        # Helper to refresh status labels in-place
        def refresh_status(button=None):
            set_status_line("Reevaluando entorno...", "info")
            fresh = self._run_preflight_checks(force=True, silent=True) or {}
            fresh_cache = self._compute_cache_state()
            env_line.set_text(f"VLC: {fresh.get('vlc_version') or 'no detectado'}")
            cookies_f = fresh.get("cookies") or {}
            desc = f"Cookies: {cookies_f.get('mode') or 'none'}"
            if cookies_f.get("path"):
                suffix = " (ok)" if cookies_f.get("exists") else " (no existe)"
                desc += f" • {cookies_f.get('path')}{suffix}"
            elif cookies_f.get("browser"):
                desc += f" • Browser: {cookies_f.get('browser')}"
            if cookies_f.get("warning"):
                desc += f" • {cookies_f.get('warning')}"
            cookie_line.set_text(desc)
            ytdlp_line.set_text(f"yt-dlp: {fresh.get('yt_dlp_version') or '?'}")
            cache_line.set_text(
                f"Cache: {fresh_cache.get('total_files',0)} archivos • {self._format_bytes(fresh_cache.get('total_size',0))}"
            )
            orphan_line.set_text(
                f"Huérfanos: {len(fresh_cache.get('orphans', []) or [])} • {self._format_bytes(fresh_cache.get('orphan_size',0))}"
            )
            ts = time.strftime("%H:%M:%S")
            self.status.notify("Pre-check actualizado")
            set_status_line(f"Pre-check actualizado {ts}", "success")

        self._settings_update_fn = refresh_status

        diag_btn = urwid.Button(f"  {t('settings.diagnostics')}")
        urwid.connect_signal(
            diag_btn, "click", lambda b: self._open_diagnostics_from_settings()
        )

        cache_btn = urwid.Button(f"  {t('settings.cache_cleanup')}")
        urwid.connect_signal(
            cache_btn, "click", lambda b: self._trigger_cache_cleanup_from_settings()
        )

        cookies_btn = urwid.Button(f"  {t('settings.refresh_cookies')}")
        urwid.connect_signal(
            cookies_btn, "click", lambda b: self._trigger_cookie_refresh_from_settings()
        )

        refresh_btn = urwid.Button(f"  {t('settings.refresh_env')}")
        urwid.connect_signal(refresh_btn, "click", refresh_status)

        # Streaming config summary
        stream_cfg = self._stream_config or {}
        stream_src = self._stream_config_source
        stream_url = stream_cfg.get("url") or ""

        # Build shareable link (if configured)
        shareable_link = ""
        if stream_url:
            # Parse mount point for public URL
            if "/" in stream_url:
                base = stream_url.rsplit("/", 1)[0]
                mount = stream_url.rsplit("/", 1)[1].split("?")[
                    0
                ]  # Remove query params
                shareable_link = f"{base}/{mount}"
            else:
                shareable_link = stream_url

        stream_status = (
            "📡 No configurado"
            if not stream_url
            else f"✅ Activo: {stream_url[:40]}..."
        )
        stream_line = urwid.Text(stream_status)

        walker.append(urwid.Divider("─"))
        walker.append(urwid.Text(("title", f" {t('stream.title')} ")))
        walker.append(
            urwid.Text(
                t("stream.description"),
                align="left",
            )
        )
        walker.append(urwid.Divider(" "))
        walker.append(
            urwid.Text(
                t("stream.requirements"),
                align="left",
            )
        )
        walker.append(
            urwid.Text(
                f"   {t('stream.req_icecast')}",
                align="left",
            )
        )
        walker.append(
            urwid.Text(
                f"   {t('stream.req_ffmpeg')}",
                align="left",
            )
        )
        walker.append(
            urwid.Text(
                f"   {t('stream.req_cache')}",
                align="left",
            )
        )
        walker.append(urwid.Divider(" "))
        walker.append(stream_line)

        # Show shareable link prominently when configured
        if shareable_link:
            walker.append(urwid.Divider(" "))
            walker.append(
                urwid.AttrMap(
                    urwid.Text(f"{t('stream.share_link')}: {shareable_link}"), "success"
                )
            )
            walker.append(urwid.Text(t("stream.share_hint"), align="left"))
        else:
            walker.append(urwid.Divider(" "))
            walker.append(urwid.Text(t("stream.config_hint"), align="left"))
            walker.append(urwid.Text(f"   {t('stream.example_url')}", align="left"))

        walker.append(urwid.Divider(" "))
        walker.append(
            urwid.Text(
                f"{t('stream.current_config')}: {stream_cfg.get('user') or t('stream.no_user')} | {stream_cfg.get('bitrate', 128)}kbps | {stream_cfg.get('format', 'mp3')}"
            )
        )
        walker.append(urwid.Text(t("stream.warning"), align="left"))

        # Streaming control buttons
        is_streaming = (
            getattr(self, "_stream_broadcaster", None)
            and self._stream_broadcaster.is_streaming()
        )
        if is_streaming:
            stream_ctrl_btn = urwid.Button(f"  {t('stream.stop')}")
            urwid.connect_signal(
                stream_ctrl_btn, "click", lambda b: self._stop_stream()
            )
        else:
            stream_ctrl_btn = urwid.Button(f"  {t('stream.start')}")
            urwid.connect_signal(
                stream_ctrl_btn, "click", lambda b: self._start_stream()
            )

        stream_btn = urwid.Button(f"  {t('stream.edit')}")
        urwid.connect_signal(
            stream_btn, "click", lambda b: self._edit_stream_config(stream_line)
        )

        # Language selector
        from config.i18n import get_language, set_language

        current_lang = get_language()
        lang_label = "🌐 Idioma / Language: " + (
            "Español" if current_lang == "es" else "English"
        )
        lang_btn = urwid.Button(f"  {lang_label} (Click to toggle)")

        def toggle_language(btn):
            from config.i18n import get_language, set_language

            new_lang = "en" if get_language() == "es" else "es"
            set_language(new_lang)
            # Refresh the menu to show new language
            self._close_modal_overlay()
            self.status.set(f"Language: {'English' if new_lang == 'en' else 'Español'}")
            self.loop.set_alarm_in(0.1, lambda l, d: self._switch_to_menu())

        urwid.connect_signal(lang_btn, "click", toggle_language)

        walker.extend(
            [
                urwid.AttrMap(diag_btn, None, focus_map="highlight"),
                urwid.AttrMap(cache_btn, None, focus_map="highlight"),
                urwid.AttrMap(cookies_btn, None, focus_map="highlight"),
                urwid.AttrMap(refresh_btn, None, focus_map="highlight"),
                urwid.AttrMap(stream_ctrl_btn, None, focus_map="highlight"),
                urwid.AttrMap(stream_btn, None, focus_map="highlight"),
                urwid.Divider(" "),
                urwid.AttrMap(lang_btn, None, focus_map="highlight"),
            ]
        )

        walker.append(urwid.Divider())
        walker.append(urwid.AttrMap(status_line, None, focus_map="highlight"))
        walker.append(
            urwid.Text("↑/↓ Navegar • Enter ejecutar • Esc/Q cerrar", align="center")
        )
        return urwid.ListBox(walker)

    def _open_settings_modal(self):
        if not self.menu_widget:
            return
        body = self._build_settings_list()
        modal = ModalOverlay(
            t("modal.settings"), body, on_close=self._close_modal_overlay
        )
        overlay = urwid.Overlay(
            modal,
            self.menu_widget,
            align="center",
            width=78,
            valign="middle",
            height=26,
        )
        self.state = UIState.EDIT
        self._settings_overlay_active = True
        self.main_widget.original_widget = overlay

    def _trigger_cache_cleanup_from_settings(self):
        self._close_modal_overlay()
        self.loop.set_alarm_in(0, lambda l, d: self._prompt_cache_cleanup())

    def _trigger_cookie_refresh_from_settings(self):
        self._close_modal_overlay()
        browser_hint = os.environ.get("YTBMUSIC_COOKIES_BROWSER", "firefox")
        self.loop.set_alarm_in(0, lambda l, d: self._start_cookie_refresh(browser_hint))

    def _edit_stream_config(self, summary_widget: Optional[urwid.Text] = None):
        """Sequential dialogs to edit streaming config."""
        cfg = self._stream_config or {}

        def ask_format(url, user, password, bitrate):
            def on_format(fmt):
                if fmt is None:
                    return
                new_cfg = {
                    "url": url or "",
                    "user": user or "",
                    "password": password or "",
                    "bitrate": int(bitrate or 128),
                    "format": (fmt or "mp3").lower(),
                }
                self._save_stream_config(new_cfg)
                if summary_widget:
                    summary_widget.set_text(
                        f"Streaming: {new_cfg.get('url') or 'no configurado'} (user={new_cfg.get('user') or 'anon'}, src=file)"
                    )

            self._show_input_dialog(
                "Streaming formato",
                "Formato (mp3/ogg)",
                on_format,
                default_text=cfg.get("format", "mp3"),
            )

        def ask_bitrate(url, user, password):
            def on_bitrate(val):
                if val is None:
                    return
                try:
                    br = int(val)
                except Exception:
                    br = 128
                ask_format(url, user, password, br)

            self._show_input_dialog(
                "Streaming bitrate",
                "Bitrate (kbps)",
                on_bitrate,
                default_text=str(cfg.get("bitrate", 128)),
            )

        def ask_password(url, user):
            def on_password(pwd):
                if pwd is None:
                    return
                ask_bitrate(url, user, pwd)

            self._show_input_dialog(
                "Streaming password",
                "Password",
                on_password,
                default_text=cfg.get("password", ""),
            )

        def ask_user(url):
            def on_user(u):
                if u is None:
                    return
                ask_password(url, u)

            self._show_input_dialog(
                "Streaming usuario",
                "Usuario",
                on_user,
                default_text=cfg.get("user", ""),
            )

        def ask_url():
            def on_url(u):
                if u is None:
                    return
                ask_user(u)

            self._show_input_dialog(
                "Streaming URL",
                "URL (icecast/shout/http)",
                on_url,
                default_text=cfg.get("url", ""),
            )

        ask_url()

    def _start_stream(self):
        """Start streaming current audio to configured Icecast server."""
        # Check FFmpeg is available
        if not check_ffmpeg_available():
            self.status.set("❌ FFmpeg no encontrado. Instalalo para streaming.")
            self.log_activity("FFmpeg no disponible", "error")
            return

        # Check stream config
        if not self._stream_config.get("url") or not self._stream_config.get(
            "password"
        ):
            self.status.set("❌ Configurá URL y password primero")
            self.log_activity("Stream no configurado", "error")
            return

        # Check we have something to stream
        if not getattr(self, "current_playlist", None):
            self.status.set("❌ No hay playlist cargada")
            return

        # Get current track's cached file
        track = self.current_playlist.get_current_track()
        if not track:
            self.status.set("❌ No hay track actual")
            return

        # Find cached file
        video_id = self._extract_video_id(track.url)
        if not video_id:
            self.status.set("❌ No se puede obtener video ID")
            return

        cache_path = None
        for ext in [".m4a", ".webm", ".mp3", ".ogg"]:
            test_path = Path("cache") / f"{video_id}{ext}"
            if test_path.exists():
                cache_path = test_path
                break

        if not cache_path:
            self.status.set("❌ Track no en cache. Descargalo primero (D).")
            return

        # Initialize broadcaster
        self._stream_broadcaster = StreamBroadcaster(self._stream_config)
        self._stream_broadcaster._on_error = lambda msg: self.status.set(
            f"Stream error: {msg[:50]}"
        )
        self._stream_broadcaster._on_status = lambda msg: self.log_activity(msg, "info")

        # Start streaming
        if self._stream_broadcaster.start_stream(str(cache_path)):
            link = self._stream_broadcaster.get_shareable_link()
            self.status.set(f"📡 Streaming: {link}")
            self.log_activity(f"🔗 LINK: {link}", "info")
            self._close_modal_overlay()
        else:
            self.status.set("❌ No se pudo iniciar el stream")

    def _stop_stream(self):
        """Stop current stream."""
        if hasattr(self, "_stream_broadcaster") and self._stream_broadcaster:
            self._stream_broadcaster.stop_stream()
            self._stream_broadcaster = None
            self.status.set("🛑 Stream detenido")
            self.log_activity("Stream detenido", "info")
            self._close_modal_overlay()
        else:
            self.status.set("No hay stream activo")

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        if not url:
            return None
        import re

        patterns = [r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", r"^([a-zA-Z0-9_-]{11})$"]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _prompt_cache_cleanup(self):
        scan = self._compute_cache_state()
        orphans = scan.get("orphans", []) or []
        if not orphans:
            self.status.set("Cache limpia ✓ (sin huérfanos)")
            return

        size_label = self._format_bytes(scan.get("orphan_size", 0))
        msg = f"Se encontraron {len(orphans)} archivos huérfanos (~{size_label}). ¿Borrarlos?"
        self._show_confirm_dialog(
            "Limpiar cache",
            msg,
            on_confirm=lambda: self._start_cache_cleanup(orphans),
        )

    def _start_cache_cleanup(self, orphans: List[Path]):
        self.status.notify("Limpiando cache...", "info")

        def worker():
            removed = 0
            freed = 0
            for f in orphans:
                try:
                    sz = f.stat().st_size
                except Exception:
                    sz = 0
                try:
                    f.unlink()
                    removed += 1
                    freed += sz
                except Exception:
                    pass
            self.loop.set_alarm_in(
                0, lambda l, d: self._on_cache_cleanup_done(removed, freed)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_cache_cleanup_done(self, removed: int, freed: int):
        self._compute_cache_state()  # refresh snapshot
        self.status.notify(
            f"Cache limpia: {removed} archivo(s) borrados, {self._format_bytes(freed)} liberados",
            "success_toast",
        )
        self.log_activity(
            f"Cache cleanup: {removed} archivos, {self._format_bytes(freed)} liberados",
            "info",
        )
        if self._settings_overlay_active and self._settings_update_fn:
            try:
                self._settings_update_fn()
            except Exception:
                pass

    # ---------- selection modals ----------
    def _open_playlist_modal(self):
        if not self.playlists:
            self.status.set("No hay playlists para mostrar")
            return

        items = []
        for name in self.playlists:
            dl, total = self._count_downloaded_tracks(name)
            items.append(
                {
                    "label": f"{name} ({dl}/{total} cached)",
                    "value": name,
                }
            )

        def on_select(name):
            try:
                idx = self.playlists.index(name)
                self.selected_playlist_idx = idx
                self._switch_to_menu()
            except Exception:
                self.status.set("Error al seleccionar playlist")

        self._show_list_modal("Playlists", items, on_select)

    def _open_skin_modal(self):
        if not self.skins:
            self.status.set("No hay skins disponibles")
            return

        items = []
        for i, name in enumerate(self.skins):
            label = name
            if i == self.current_skin_idx:
                label = f"{name} (actual)"
            items.append({"label": label, "value": i})

        def on_select(idx):
            try:
                self._load_skin(int(idx))
                self._switch_to_menu()
            except Exception as e:
                self._handle_error(e, "skin_select_modal")
                self._switch_to_menu()

        self._show_list_modal("Skins", items, on_select)

    def _open_background_modal(self):
        disclaimer = "Fondos sin restricciones; revisá combinaciones antes de usar (pueden ser intensos)."
        if not self.backgrounds:
            self.status.set("No hay fondos en backgrounds/")
            return

        items = []
        for i, name in enumerate(self.backgrounds):
            try:
                meta, _ = self.background_loader.load(name)
                label = meta.get("name") or name
                fg = meta.get("fg") or ""
                bg = meta.get("bg") or ""
                alt_bg = meta.get("alt_bg")
                note = f"fg:{fg} bg:{bg}"
                if alt_bg:
                    note += f" → {alt_bg}"
                items.append({"label": label, "value": i, "note": note})
            except Exception:
                items.append({"label": name, "value": i})

        def on_select(idx):
            try:
                self._apply_background_by_idx(int(idx))
            except Exception as e:
                self._handle_error(e, "background_select")
            self._switch_to_menu()

        self._show_list_modal("Fondos", items, on_select, disclaimer=disclaimer)

    def _show_list_modal(
        self, title: str, items: List[dict], on_select, disclaimer: str = None
    ):
        """Render a generic list modal overlay."""
        # Keep menu visible underneath
        self.state = UIState.EDIT
        dialog = ListDialog(
            title,
            items,
            on_select,
            on_cancel=self._switch_to_menu,
            disclaimer=disclaimer,
        )
        overlay = urwid.Overlay(
            dialog,
            self.menu_widget,
            align="center",
            width=72,
            valign="middle",
            height=26,
        )
        self.main_widget.original_widget = overlay

    # ---------- backgrounds ----------
    def _set_player_background(self, fg: str, bg: str):
        """Register and apply background palette for the player canvas only."""
        fg = self._normalize_color(fg)
        bg = self._normalize_color(bg)
        try:
            self.loop.screen.register_palette_entry(
                self._background_palette_name, fg, bg
            )
            logger.info(
                f"[BG] Applying palette {self._background_palette_name}: fg={fg} bg={bg}"
            )
            self.player_view.set_background_attr(self._background_palette_name)
            # Force immediate redraw to avoid stale colors
            try:
                self.player_view.force_redraw()
            except Exception:
                pass
            if self.loop:
                try:
                    self.loop.screen.clear()
                    self.loop.draw_screen()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to apply background palette: {e}")
            self.player_view.set_background_attr(None)

    def _cancel_background_cycle(self):
        if self._background_alarm and self.loop:
            try:
                self.loop.remove_alarm(self._background_alarm)
            except Exception:
                pass
        self._background_alarm = None
        self._background_cycle = []
        self._background_cycle_idx = 0

    def _schedule_background_cycle(self, meta: Dict[str, Any]):
        self._cancel_background_cycle()
        interval = float(meta.get("transition_sec") or 0)
        fg_default = meta.get("fg") or "white"
        colors: List[tuple[str, str]] = []
        bg_main = meta.get("bg") or "black"
        colors.append((fg_default, bg_main))

        palette_list = meta.get("palette") or []
        if isinstance(palette_list, list):
            for item in palette_list:
                if not isinstance(item, dict):
                    continue
                bg_val = item.get("bg")
                fg_val = item.get("fg") or fg_default
                if bg_val:
                    colors.append((fg_val, bg_val))

        alt_bg = meta.get("alt_bg")
        if alt_bg:
            colors.append((fg_default, alt_bg))

        # Need at least 2 colors to cycle
        if interval <= 0 or len(colors) < 2:
            return

        self._background_cycle = colors
        self._background_cycle_idx = 0

        def advance(loop=None, data=None):
            if not self._background_cycle:
                return
            self._background_cycle_idx = (self._background_cycle_idx + 1) % len(
                self._background_cycle
            )
            fg, bg = self._background_cycle[self._background_cycle_idx]
            self._set_player_background(fg, bg)
            self._background_alarm = self.loop.set_alarm_in(interval, advance)

        self._background_alarm = self.loop.set_alarm_in(interval, advance)

    def _apply_background_by_idx(self, idx: int):
        """Apply background preset by index (safe if none available)."""
        self._cancel_background_cycle()
        self._stop_gradient_animation()  # Stop any active gradient

        if not self.backgrounds:
            self.current_background_meta = None
            self.player_view.set_background_attr(None)
            return
        idx = idx % len(self.backgrounds)
        name = self.backgrounds[idx]
        try:
            meta, _ = self.background_loader.load(name)
        except Exception as e:
            logger.error(f"Failed to load background '{name}': {e}")
            return
        self.current_background_idx = idx
        self.current_background_meta = meta

        # Check if this is a gradient background (demoscene mode)
        if BackgroundLoader.is_gradient(meta):
            self._start_gradient_animation(meta)
            self.log_activity(f"🌈 Gradient: {meta.get('name') or name}", "info")
        else:
            # Standard solid/cycling background
            self._set_player_background(
                meta.get("fg") or "white", meta.get("bg") or "black"
            )
            self._schedule_background_cycle(meta)
            self.log_activity(f"Fondo: {meta.get('name') or name}", "info")

    def _start_gradient_animation(self, meta: Dict[str, Any]):
        """Start demoscene-style gradient animation."""
        logger.info(f"[GRADIENT] Starting animation: {meta.get('name')}")
        self._gradient_renderer = GradientRenderer(meta)
        self._gradient_active = True
        # Start animation loop
        speed = self._gradient_renderer.get_speed()
        logger.info(f"[GRADIENT] Speed: {speed}s, pattern: {meta.get('pattern')}")
        self._gradient_alarm = self.loop.set_alarm_in(
            speed, self._gradient_animate_loop
        )
        # Apply initial gradient
        self._apply_gradient_colors()

    def _stop_gradient_animation(self):
        """Stop gradient animation if active."""
        self._gradient_active = False
        if hasattr(self, "_gradient_alarm") and self._gradient_alarm:
            try:
                self.loop.remove_alarm(self._gradient_alarm)
            except Exception:
                pass
        self._gradient_alarm = None
        self._gradient_renderer = None

    def _gradient_animate_loop(self, loop=None, data=None):
        """Animation loop for gradient backgrounds."""
        if not self._gradient_active or not self._gradient_renderer:
            logger.debug("[GRADIENT] Loop skipped: not active")
            return
        # Advance animation frame
        self._gradient_renderer.advance_frame()
        self._apply_gradient_colors()
        # Schedule next frame
        speed = self._gradient_renderer.get_speed()
        self._gradient_alarm = self.loop.set_alarm_in(
            speed, self._gradient_animate_loop
        )

    def _apply_gradient_colors(self):
        """Apply current gradient colors to the player view."""
        if not self._gradient_renderer:
            logger.warning("[GRADIENT] No renderer in _apply_gradient_colors")
            return
        
        # Get terminal size for proper gradient calculation
        try:
            width, height = self.player_view._compute_canvas_size()
        except Exception:
            width, height = 80, PAD_HEIGHT
        
        # Get colors for each line - this creates the sweep effect
        colors = self._gradient_renderer.get_line_colors(height, width)
        direction = self._gradient_renderer.direction
        logger.debug(f"[GRADIENT] Applying {len(colors)} colors, direction={direction}")
        
        # Use the new per-line gradient rendering for real sweep effect
        self.player_view.set_gradient_colors(colors, self.loop, direction)
        
        # Force redraw
        try:
            self.loop.draw_screen()
        except Exception:
            pass

    def _cycle_background(self, direction: int = 1):
        """Cycle through backgrounds in player mode."""
        if not self.backgrounds:
            self.status.set("No hay fondos disponibles")
            return
        self.current_background_idx = (self.current_background_idx + direction) % len(
            self.backgrounds
        )
        self._apply_background_by_idx(self.current_background_idx)
        name = self.backgrounds[self.current_background_idx]
        self.status.notify(f"Fondo: {name}")

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

        if etype == "retry":
            delay = float(event.get("delay", 0.0) or 0.0)
            attempt = int(event.get("attempt", 1) or 1)
            max_attempts = int(event.get("max_attempts", attempt + 1) or attempt + 1)
            err = event.get("error", "") or ""
            self._last_download_error = err
            self._last_download_error_context = "retry"
            task = event.get("task")
            title = getattr(task, "title", "") if task else ""
            rid = request_id or ""
            msg = f"Reintento {attempt}/{max_attempts} en {delay:.0f}s"
            if title:
                msg += f" — {title[:40]}"
            logger.warning(
                f"[DL {rid}] retry {attempt}/{max_attempts} in {delay:.1f}s: {err}"
            )
            self.log_activity(
                f"Retrying download ({attempt}/{max_attempts}) in {delay:.0f}s", "info"
            )
            self.status.notify(msg)
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
            self._last_download_error = err
            self._last_download_error_context = "download"
            logger.error(f"[DL {rid}] failed: {title} - {err}")
            if title:
                self.log_activity(f"Failed: {title}", "error")

            err_l = (err or "").lower()
            auth_tokens = [
                "sign in to confirm you're not a bot",
                "confirm you're not a bot",
                "--cookies-from-browser",
                "too many requests",
                "http error 429",
            ]
            if any(token in err_l for token in auth_tokens):
                self._handle_auth_challenge(err or "")
                return

            friendly = self._friendly_error_message(err or "")
            if friendly:
                self.status.notify(friendly, "error_toast")

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

    def _handle_auth_challenge(self, error_message: str):
        """Pause downloads and prompt the user to refresh cookies."""
        if getattr(self, "_cookie_prompt_active", False):
            return

        self._cookie_prompt_active = True
        try:
            self.download_manager.cancel_all(cancel_in_progress=True)
        except Exception:
            pass

        browser_hint = os.environ.get("YTBMUSIC_COOKIES_BROWSER", "firefox")
        browser_label = browser_hint.split(":", 1)[0].title()
        instructions = (
            "YouTube está pidiendo que confirmes que sos un humano.\n"
            f"1) Abrí {browser_label} y logueate en YouTube.\n"
            "2) Volvé a YTBMusic y elegí 'Yes' para refrescar las cookies automáticamente."
        )

        self.status.notify("⚠️ YouTube pidió verificación. Seguí las instrucciones.")

        self._show_confirm_dialog(
            "Verificación requerida",
            instructions,
            on_confirm=lambda: self._start_cookie_refresh(browser_hint),
            on_cancel=self._cancel_cookie_refresh,
        )

    def _cancel_cookie_refresh(self):
        self._cookie_prompt_active = False
        self.status.set("Actualización de cookies cancelada")

    def _start_cookie_refresh(self, browser_hint: str):
        """Run yt-dlp cookies export in a background thread."""
        self._switch_to_loading("Actualizando cookies...")

        def worker():
            try:
                path = self.downloader.refresh_cookies_from_browser(
                    browser=browser_hint
                )
                self.loop.set_alarm_in(
                    0,
                    lambda l, d: self._cookie_refresh_result(
                        True, browser_hint, path, None
                    ),
                )
            except Exception as e:
                self.loop.set_alarm_in(
                    0,
                    lambda l, d: self._cookie_refresh_result(
                        False, browser_hint, None, str(e)
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _cookie_refresh_result(
        self,
        success: bool,
        browser_hint: str,
        cookie_path: Optional[str],
        error: Optional[str],
    ):
        self._cookie_prompt_active = False
        self._switch_to_menu()

        browser_label = browser_hint.split(":", 1)[0].title()
        if success:
            msg = (
                f"Cookies actualizadas desde {browser_label} ✓. "
                "Retomando descargas pendientes..."
            )
            self.status.notify(msg)
            self.log_activity(msg, "success")
            self.loop.set_alarm_in(6.0, lambda l, d: self.status.clear_notify())
            # Reanudar auto-download global una vez que las cookies están listas
            self.loop.set_alarm_in(0.5, lambda l, d: self._start_auto_downloads())
        else:
            error_msg = error or "Error desconocido"
            self.status.set(f"Error al refrescar cookies: {error_msg}")
            self.log_activity(
                f"Cookie refresh failed ({browser_label}): {error_msg}", "error"
            )

    def _prompt_import_playlist(self):
        """Show dialog to import a YouTube playlist."""

        def on_url_entered(url):
            if not url:
                return

            # Sota: Fetch title first to pre-fill the name dialog
            self._switch_to_loading("Fetching metadata...")

            def fetch_metadata_thread():
                try:
                    # Use extract_playlist_items to get title quickly (lightweight)
                    info = self.downloader.extract_playlist_items(url)
                    suggested_name = info.get("title", "")
                    # Clean up title if it contains " - Topic" etc? maybe not.

                    # Schedule the name dialog on main thread
                    self.loop.set_alarm_in(
                        0, lambda l, d: show_name_dialog(suggested_name)
                    )
                except Exception as e:
                    logger.error(f"Metadata fetch failed: {e}")
                    # Fallback to empty name
                    self.loop.set_alarm_in(0, lambda l, d: show_name_dialog(""))

            def show_name_dialog(default_name):
                # Guard: If user cancelled (state switched back to MENU), abort
                if self.state != UIState.LOADING:
                    return

                # Restore menu state so the dialog displays correctly over it
                self.state = UIState.MENU
                self.main_widget.original_widget = self.menu_widget

                def on_name_entered(name):
                    self._switch_to_loading("Contacting YouTube...")
                    self.status.notify("⬇️ Importing playlist info...")
                    self.loop.draw_screen()

                    # Run import in background thread
                    def threaded_import():
                        try:
                            logger.info(f"[THREAD] Starting import for URL: {url}")

                            result = import_playlist_from_youtube(
                                url,
                                playlist_name=name or default_name or None,
                                overwrite=False,
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

                self._show_input_dialog(
                    "Playlist Name (Optional)",
                    "Name",
                    on_name_entered,
                    default_text=default_name,
                )

            # Start the metadata fetch
            threading.Thread(target=fetch_metadata_thread, daemon=True).start()

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
        self._invalidate_track_index()

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

    def _collect_missing_tracks(self, playlist_name: str) -> list:
        """Return track dicts that are not cached for given playlist."""
        try:
            playlist = self.playlist_manager.load_playlist(playlist_name)
        except Exception:
            return []

        missing = []
        for track in getattr(playlist, "tracks", []):
            url = getattr(track, "url", None)
            if not url:
                continue
            # Skip unplayable tracks (marked as unavailable/deleted/private)
            if getattr(track, "is_playable", True) is False:
                continue
            title = getattr(track, "title", "")
            artist = getattr(track, "artist", "")
            if self.downloader.is_cached(url, title=title, artist=artist):
                continue
            missing.append(
                {
                    "title": title,
                    "artist": artist,
                    "url": url,
                    "_playlist": playlist_name,
                }
            )
        return missing

    def _on_download_all(self):
        """Trigger download of all missing tracks in current playlist."""
        if not self.current_playlist:
            self.status.set("Play a playlist first to download it!")
            return

        pl_name = self.current_playlist.get_name()
        missing = self._collect_missing_tracks(pl_name)
        if not missing:
            self.status.set("All tracks are already downloaded! ✓")
            return

        self._start_batch_download(missing)

    def _download_selected_playlist(self):
        """Download missing tracks for the playlist selected in the menu."""
        if self.selected_playlist_idx is None or self.selected_playlist_idx >= len(
            self.playlists
        ):
            self.status.set("Select a playlist first!")
            return

        pl_name = self.playlists[self.selected_playlist_idx]
        missing = self._collect_missing_tracks(pl_name)
        if not missing:
            self.status.set(f"'{pl_name}' ya está descargada ✓")
            return

        self._start_background_downloads(
            missing, start_delay=0.0, default_playlist=pl_name, force_reset=False
        )
        self.status.notify(f"⬇️ Descargando {len(missing)} track(s) de '{pl_name}'")

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
            name="Random All",
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

        def find_deletable_cache_files() -> tuple[List[Path], int]:
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

        def delete_cache_files(paths: List[Path]):
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
                self._invalidate_track_index()
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
                self._invalidate_track_index()

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
        # Validate playlists at startup (fix duplicates, sanitize titles, etc.)
        self._run_startup_validation()

        if self.skins:
            self._safe_call(self._load_skin, 0)
        else:
            self.skin_lines = self._create_emergency_skin()
        self._switch_to_menu()
        if self.backgrounds:
            self._apply_background_by_idx(self.current_background_idx)
        self._run_preflight_checks()
        self._start_download_event_pump()

        # Start auto-downloading missing tracks after 2 seconds
        self.loop.set_alarm_in(2.0, lambda l, d: self._start_auto_downloads())

        self.loop.run()

    def _run_startup_validation(self):
        """Validate all playlists at startup."""
        try:
            from core.playlist_validator import run_validation

            report = run_validation(auto_fix=True)
            if report.playlists_fixed:
                logger.info(f"[STARTUP] {report.summary()}")
        except Exception as e:
            logger.warning(f"[STARTUP] Playlist validation failed: {e}")

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
        self.player_view.render()

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
                self.player.play(
                    cached_path,
                    start_time=track.start_time,
                    end_time=track.end_time,
                )
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
            # Start playback
            self.player.play(
                stream_url,
                start_time=track.start_time,
                end_time=track.end_time,
            )
            self.status.set(f"Playing: {track.title} | " + HELP_TEXT)
            self._update_now_playing_footer(track)
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
        self._cancel_background_cycle()
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

        # If a search/input overlay is active, ignore global hotkeys
        if getattr(self, "_input_overlay_active", False):
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
            elif key in ("p", "P"):
                # If nothing selected but a playlist is already active, just return to player
                if self.selected_playlist_idx is None and self.current_playlist:
                    self._switch_to_player()
                else:
                    self._on_play_selected()
            elif key in ("x", "X"):
                self._on_delete_selected()
            elif key in ("r", "R"):
                self._on_random_all()
            elif key in ("e", "E"):
                # Defer to next tick so the overlay isn't clobbered by the current input cycle
                self.loop.set_alarm_in(0, lambda l, d: self._on_rename_selected())
            elif key in ("d", "D"):
                # Defer to next tick to avoid input cycle race conditions
                self.loop.set_alarm_in(
                    0, lambda l, d: self._download_selected_playlist()
                )
            elif key in ("a", "A"):
                self._toggle_animation()
            elif key in ("f", "F"):
                # Defer to next tick to avoid overlay being clobbered by menu redraws
                self.loop.set_alarm_in(0, lambda l, d: self._prompt_global_search())
            elif key in ("o", "O"):
                self._open_settings_modal()
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
        elif key in ("b", "B"):
            # Cycle backgrounds while in player
            self._cycle_background(direction=1)


def main():
    cols, lines = shutil.get_terminal_size()
    if cols < PAD_WIDTH or lines < PAD_HEIGHT:
        print(f"\n⚠️  Terminal: {cols}x{lines}")
        print(f"   Recommended: {PAD_WIDTH}x{PAD_HEIGHT} or larger")
        print("   Starting in 2 seconds...")
        time.sleep(2)
    try:
        # Dependency Injection Wiring
        events_queue = queue.Queue()

        player = MusicPlayer()
        downloader = YouTubeDownloader(cache_dir="cache")
        playlist_manager = PlaylistManager(playlists_dir="playlists")
        skin_loader = SkinLoader()

        download_manager = DownloadManager(
            downloader,
            event_callback=events_queue.put,
            progress_throttle_sec=0.25,
        )
        download_manager.start()

        app = YTBMusicUI(
            downloader=downloader,
            download_manager=download_manager,
            player=player,
            playlist_manager=playlist_manager,
            skin_loader=skin_loader,
            download_events_queue=events_queue,
        )
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
