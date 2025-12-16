import urwid
import time
from pathlib import Path

from core.player import MusicPlayer, PlayerState
from core.downloader import YouTubeDownloader
from core.playlist import PlaylistManager
from ui.skin_loader import SkinLoader


HELP_TEXT = "Space=Play/Pause  N/P=Next/Prev  ←/→=Seek  ↑/↓=Vol  S=Skin  M=Menu  Q=Quit"
PAD_WIDTH = 78
PAD_HEIGHT = 38


def pad_lines(lines, width=PAD_WIDTH, height=PAD_HEIGHT):
    """Pad lines to fixed size without breaking."""
    padded = []
    for line in lines:
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
        self.player = MusicPlayer()
        self.player.on_end_callback = self._next_track
        self.downloader = YouTubeDownloader(cache_dir="cache")
        self.playlist_manager = PlaylistManager(playlists_dir="playlists")
        self.skin_loader = SkinLoader()

        self.skins = SkinLoader.list_available_skins()
        self.current_skin_idx = 0
        self.skin_lines = []

        self.playlists = self.playlist_manager.list_playlists()
        self.current_playlist_idx = 0
        self.current_playlist = None
        self.consecutive_errors = 0

        # UI Mode: 'menu' or 'player'
        self.mode = "menu"

        # Widgets
        self.skin_widget = SkinWidget()
        self.menu_widget = self._create_menu()
        self.status = StatusBar("")

        # Main container
        self.main_widget = urwid.WidgetPlaceholder(self.menu_widget)
        frame = urwid.Frame(body=self.main_widget, footer=self.status)

        self.loop = urwid.MainLoop(
            frame,
            unhandled_input=self.unhandled_input,
            palette=[
                ("status", "black", "dark cyan"),
                ("title", "yellow,bold", ""),
                ("highlight", "black", "dark cyan"),
                ("normal", "", ""),
            ],
        )

    def _create_menu(self):
        """Create retro ASCII menu."""
        menu_items = []

        # Title
        title = [
            "",
            "    ▄▄▄▄▄▄▄ ▄   ▄ ▄▄▄▄▄▄  ▄▄   ▄▄ ▄   ▄ ▄▄▄▄▄▄ ▄ ▄▄▄▄▄",
            "      █   █ █   █   █   █ █ █ █ █ █   █ █     ▄█ █   ",
            "      █▄▄▄█  ▀▀▀█ ▄▄█▄▄▄█ █ █ █ █ ▀▀▀▀█ █▄▄▄█  █ █▄▄▄",
            "",
            "              · Terminal Music Player ·",
            "",
            "",
        ]

        for line in title:
            menu_items.append(
                urwid.AttrMap(urwid.Text(("title", line), align="center"), None)
            )

        # Playlists
        menu_items.append(urwid.Text(""))
        menu_items.append(
            urwid.AttrMap(urwid.Text("  ♪ SELECT PLAYLIST", align="left"), None)
        )
        menu_items.append(urwid.Text(""))

        self.menu_walker = urwid.SimpleFocusListWalker([])

        for i, pl_name in enumerate(self.playlists):
            try:
                pl = self.playlist_manager.load_playlist(pl_name)
                display = f"    {pl.get_name()} ({pl.get_track_count()} tracks)"
            except:
                display = f"    {pl_name}"

            btn = urwid.Button(display)
            urwid.connect_signal(btn, "click", self._on_playlist_select, i)
            self.menu_walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))

        for item in menu_items:
            self.menu_walker.insert(0, item)

        menu_items.append(urwid.Text(""))
        menu_items.append(urwid.Text(""))
        menu_items.append(
            urwid.AttrMap(
                urwid.Text("  ↑/↓ Navigate    Enter Select    Q Quit", align="center"),
                "status",
            )
        )

        return urwid.ListBox(self.menu_walker)

    def _on_playlist_select(self, button, playlist_idx):
        """Playlist selected from menu."""
        self._load_playlist(playlist_idx, auto_play=True)
        self._switch_to_player()

    def _switch_to_player(self):
        """Switch from menu to player view."""
        self.mode = "player"
        self.main_widget.original_widget = self.skin_widget
        self.loop.set_alarm_in(0.2, self.refresh)

    def _switch_to_menu(self):
        """Switch from player to menu."""
        self.mode = "menu"
        self.player.stop()
        # Recreate menu to refresh playlist list
        self.playlists = self.playlist_manager.list_playlists()
        self.menu_widget = self._create_menu()
        self.main_widget.original_widget = self.menu_widget
        self.status.set("")

    def run(self):
        self._load_skin(0)
        self.status.set("Welcome! Select a playlist to start")
        self.loop.run()

    def refresh(self, loop=None, data=None):
        if self.mode == "player":
            self._render_skin()
            if loop:
                loop.set_alarm_in(0.2, self.refresh)

    def _render_skin(self):
        context = {
            "PREV": "<<",
            "NEXT": ">>",
            "PLAY": "||" if self.player.is_playing() else ">",
            "VOL_DOWN": "-",
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
        }

        if self.current_playlist:
            track = self.current_playlist.get_current_track()
            if track:
                context["TITLE"] = track.title[:35]
                context["ARTIST"] = track.artist[:30]
                context["PLAYLIST"] = self.current_playlist.get_name()[:25]
                context["TRACK_NUM"] = self.current_playlist.get_position_info()
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
            context["PROGRESS"] = (
                "[" + "=" * filled + ">" + " " * (bar_width - filled - 1) + "]"
            )

        lines = pad_lines(self.skin_lines, PAD_WIDTH, PAD_HEIGHT)
        rendered = self.skin_loader.render(
            lines, context, pad_width=PAD_WIDTH, pad_height=PAD_HEIGHT
        )
        self.skin_widget.update("\n".join(rendered))

    def _load_skin(self, idx):
        if not self.skins:
            return
        self.current_skin_idx = idx % len(self.skins)
        skin_path = Path("skins") / f"{self.skins[self.current_skin_idx]}.txt"
        try:
            meta, lines = self.skin_loader.load(str(skin_path))
            self.skin_lines = pad_lines(lines, PAD_WIDTH, PAD_HEIGHT)
            if self.mode == "player":
                self.status.set(f"Skin: {meta.get('name', '')[:20]} | " + HELP_TEXT)
        except Exception as e:
            self.skin_lines = pad_lines([], PAD_WIDTH, PAD_HEIGHT)

    def _load_playlist(self, idx, auto_play=True):
        if not self.playlists:
            self.current_playlist = None
            return
        self.current_playlist_idx = idx % len(self.playlists)
        name = self.playlists[self.current_playlist_idx]
        self.current_playlist = self.playlist_manager.load_playlist(name)

        if auto_play and self.current_playlist.tracks:
            self._play_current_track(0)

    def _play_current_track(self, index):
        if (
            not self.current_playlist
            or index < 0
            or index >= len(self.current_playlist.tracks)
        ):
            return
        track = self.current_playlist.tracks[index]
        self.current_playlist.current_index = index
        try:
            stream_url = self.downloader.get_stream_url(track.url)
            self.player.play(stream_url)
            self.status.set(f"♪ {track.title[:40]} | " + HELP_TEXT)
            self.consecutive_errors = 0
        except Exception as e:
            self.consecutive_errors += 1
            if self.consecutive_errors >= 5:
                self.status.set("Too many errors. Press M for menu.")
                self.player.stop()
                self.consecutive_errors = 0
                return
            if not self._next_track():
                self.player.stop()

    def _next_track(self):
        if not self.current_playlist:
            return False
        nxt = self.current_playlist.next()
        if nxt:
            self._play_current_track(self.current_playlist.current_index)
            return True
        else:
            self.player.stop()
            self.status.set("Playlist finished. Press M for menu.")
            return False

    def _prev_track(self):
        if not self.current_playlist:
            return
        prv = self.current_playlist.previous()
        if prv:
            self._play_current_track(self.current_playlist.current_index)

    def unhandled_input(self, key):
        if key in ("q", "Q"):
            self.player.cleanup()
            raise urwid.ExitMainLoop()

        # Menu mode
        if self.mode == "menu":
            if key == "enter":
                # Let the button handler do the work
                pass
            return

        # Player mode
        if key == " ":
            self.player.toggle_pause()
        elif key in ("n", "N"):
            self._next_track()
        elif key in ("p", "P"):
            self._prev_track()
        elif key in ("s", "S"):
            self._load_skin(self.current_skin_idx + 1)
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


def main():
    import shutil

    cols, lines = shutil.get_terminal_size()
    if cols < 80 or lines < 40:
        print(f"\n⚠️  Terminal: {cols}x{lines}")
        print("   Recommended: 80x40 or larger")
        time.sleep(2)

    try:
        app = YTBMusicUI()
        app.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
