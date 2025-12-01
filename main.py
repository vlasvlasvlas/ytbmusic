import urwid
import time
import signal
import shutil
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional

from core.player import MusicPlayer, PlayerState
from core.downloader import YouTubeDownloader
from core.playlist import PlaylistManager
from core.playlist_editor import import_playlist_from_youtube, list_playlists
from core import playlist_editor
from ui.skin_loader import SkinLoader


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
    def __init__(self, text):
        self.text = urwid.Text(text, align="center")
        super().__init__(urwid.AttrWrap(self.text, "status"))

    def set(self, text):
        self.text.set_text(text)


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

        # Skins (only those that fit canvas)
        self.skins = SkinLoader.list_available_skins()
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

    # ---------- UI builders ----------
    def _create_menu(self):
        items = []
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
            urwid.AttrMap(urwid.Text("  ♪  SELECT PLAYLIST (1-9)", align="left"), "title")
        )
        self.menu_walker.append(urwid.Divider("─"))

        if not self.playlists:
            self.menu_walker.append(urwid.Text(""))
            self.menu_walker.append(
                urwid.AttrMap(urwid.Text("     No playlists found!", align="center"), "error")
            )
            self.menu_walker.append(
                urwid.Text("     Add .json files to playlists/ folder", align="center")
            )
        else:
            for i, pl_name in enumerate(self.playlists[:9]):
                meta = self._get_playlist_metadata(pl_name)
                if meta:
                    display = f"    [{i+1}] {meta.name} ({meta.track_count} tracks)"
                else:
                    display = f"    [{i+1}] {pl_name} (error)"
                btn = urwid.Button(display)
                urwid.connect_signal(btn, "click", self._on_playlist_select, i)
                self.menu_walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))

        self.menu_walker.append(urwid.Text(""))
        self.menu_walker.append(urwid.Divider("═"))
        self.menu_walker.append(
            urwid.AttrMap(urwid.Text("  🎨  SELECT SKIN (A-J)", align="left"), "title")
        )
        self.menu_walker.append(urwid.Divider("─"))

        if not self.skins:
            self.menu_walker.append(urwid.Text(""))
            self.menu_walker.append(
                urwid.AttrMap(urwid.Text("     No skins found!", align="center"), "error")
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
                urwid.connect_signal(btn, "click", self._on_skin_select, i)
                self.menu_walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))

        self.menu_walker.append(urwid.Text(""))
        self.menu_walker.append(urwid.Divider("═"))

        total_tracks = (
            sum(meta.track_count for meta in [self._get_playlist_metadata(p) for p in self.playlists] if meta)
            if self.playlists
            else 0
        )
        info = f"  {len(self.playlists)} playlists  ·  {total_tracks} tracks  ·  {len(self.skins)} skins"
        self.menu_walker.append(urwid.AttrMap(urwid.Text(info, align="center"), "info"))
        self.menu_walker.append(urwid.Text(""))
        self.menu_walker.append(
            urwid.AttrMap(
                urwid.Text("  ↑/↓ Navigate  •  Enter/Number/Letter Select  •  I Import YT Playlist  •  Q Quit", align="center"),
                "status",
            )
        )

        return urwid.ListBox(self.menu_walker)

    def _create_loading_widget(self, message: str):
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        loading_text = [
            "",
            "",
            "",
            f"         {frames[self.spinner_frame]} {message}",
            "",
            "",
            "",
        ]
        return urwid.Filler(urwid.Pile([urwid.Text(line, align="center") for line in loading_text]), valign="middle")

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
        self.main_widget.original_widget = self.loading_widget
        self.spinner_alarm = self.loop.set_alarm_in(0.1, self._animate_loading)
        self.status.set("Loading... Please wait")

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
        if self.playlists and self.skins:
            self.status.set("Select playlist (1-9) or skin (A-J) • Q to quit")
        else:
            self.status.set("Add playlists and skins to get started")

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
        """Blocking prompt to import a YouTube playlist (metadata) with optional download."""
        print("\nImport YouTube playlist")
        url = input("  Playlist URL: ").strip()
        if not url:
            return
        name = input("  Target playlist name (Enter = use playlist title): ").strip()
        overwrite = input("  Overwrite if exists? (y/N): ").strip().lower() == "y"
        download = input("  Download after import? (y/N): ").strip().lower() == "y"

        try:
            self.status.set("Importing playlist...")
            result = import_playlist_from_youtube(url, playlist_name=name or None, overwrite=overwrite)
            msg = f"Imported '{result['name']}': +{result['added']} / skipped {result['skipped']}"
            self.status.set(msg)
            # Refresh playlists in menu
            self.playlists = list_playlists()

            if download and result.get("added_items"):
                yd = YouTubeDownloader()
                added = result["added_items"]
                total = len(added)
                failures = 0
                print("\nDownloading added tracks...")
                for idx, item in enumerate(added, 1):
                    title = item.get("title", "Unknown")

                    def hook(percent, downloaded, total_bytes):
                        print(f"\r[{idx}/{total}] {title[:40]:40}  {percent:5.1f}%", end="")

                    try:
                        yd.download(item["url"], progress_callback=hook)
                        print("")
                    except Exception as e:
                        failures += 1
                        print(f"\nFailed: {title} ({e})")
                print(f"\nDownload summary: {total - failures} ok, {failures} failed.")
                self.status.set(f"{msg} • Downloads: {total - failures} ok / {failures} failed")
        except Exception as e:
            self._handle_error(e, "import_playlist")

    # ---------- actions ----------
    def _on_playlist_select(self, button, playlist_idx):
        if not self.playlists or playlist_idx >= len(self.playlists):
            return
        self._switch_to_loading("Loading playlist...")
        self.loop.draw_screen()
        try:
            self._load_playlist(playlist_idx, auto_play=False)
            self._switch_to_player()
            self.loop.set_alarm_in(0.3, lambda l, d: self._start_playback())
        except Exception as e:
            self._handle_error(e, "playlist_select")
            self._switch_to_menu()

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
        self.loop.run()

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
                context["SHUFFLE_STATUS"] = "ON" if self.current_playlist.shuffle_enabled else "OFF"
                context["REPEAT_STATUS"] = self.current_playlist.repeat_mode.value.upper()
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
        rendered = self.skin_loader.render(lines, context, pad_width=PAD_WIDTH, pad_height=PAD_HEIGHT)
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
            skin_path = Path("skins") / f"{self.skins[self.current_skin_idx]}.txt"
            meta, lines = self.skin_loader.load(str(skin_path))
            self.skin_lines = pad_lines(lines, PAD_WIDTH, PAD_HEIGHT)
            if self.state == UIState.PLAYER:
                self.status.set(f"Skin: {meta.get('name', '')[:20]} | " + HELP_TEXT)
        except Exception as e:
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
        if not self.current_playlist or index < 0 or index >= len(self.current_playlist.tracks):
            return
        track = self.current_playlist.tracks[index]
        self.current_playlist.current_index = index
        try:
            cached_path = self.downloader.is_cached(track.url)
            if cached_path:
                self.player.play(cached_path)
                self.is_cached_playback = True
                self.status.set(f"♪ {track.title[:35]} (cached) | " + HELP_TEXT)
            else:
                # Download with progress and show overlay; fallback to streaming on error
                self._switch_to_loading("Downloading 0%")
                self.loop.draw_screen()

                def progress_hook(percent):
                    self._update_loading_message(f"Downloading {percent:.1f}%")

                try:
                    file_path = self.downloader.download(track.url, progress_callback=progress_hook)
                    self._switch_to_player()
                    self.player.play(file_path)
                    self.is_cached_playback = True
                    self.status.set(f"♪ {track.title[:35]} (cached) | " + HELP_TEXT)
                except Exception:
                    self._switch_to_player()
                    stream_url = self.downloader.get_stream_url(track.url)
                    self.player.play(stream_url)
                    self.is_cached_playback = False
                    self.status.set(f"♪ {track.title[:35]} (streaming) | " + HELP_TEXT)
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

    def _on_track_end_callback(self):
        """Called by VLC when track ends (runs in VLC thread)."""
        # Schedule next track in main thread to avoid urwid thread-safety issues
        if hasattr(self, 'loop') and self.loop:
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
        if key in ("q", "Q"):
            self.cleanup()
            raise urwid.ExitMainLoop()
        if self.state == UIState.LOADING:
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
                self._prompt_import_playlist()
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
