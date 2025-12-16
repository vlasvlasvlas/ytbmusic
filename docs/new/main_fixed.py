import urwid
import time
from pathlib import Path

from core.player import MusicPlayer, PlayerState
from core.downloader import YouTubeDownloader
from core.playlist import PlaylistManager
from ui.skin_loader import SkinLoader


HELP_TEXT = "Space=Play/Pause  N/P=Next/Prev  ←/→=Seek  ↑/↓=Vol  S=Skin  L=Next  Q=Quit"
PAD_WIDTH = 78  # Changed from 80
PAD_HEIGHT = 38  # Changed from 40


def pad_lines(lines, width=PAD_WIDTH, height=PAD_HEIGHT):
    """Pad lines to fixed size without breaking."""
    padded = []
    for line in lines:
        # Truncate if too long
        if len(line) > width:
            line = line[:width]
        # Pad if too short
        if len(line) < width:
            line = line + " " * (width - len(line))
        padded.append(line)

    # Ensure we have exactly height lines
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
        self.text = urwid.Text(text)
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

        self.skin_widget = SkinWidget()
        self.track_walker = urwid.SimpleFocusListWalker([])
        self.track_listbox = urwid.ListBox(self.track_walker)
        self.status = StatusBar(HELP_TEXT)

        # Main layout: skin on left, tracks on right
        self.body = urwid.Columns(
            [
                ("weight", 3, self.skin_widget),  # Removed LineBox
                ("weight", 1, urwid.LineBox(self.track_listbox, title="Tracks")),
            ],
            dividechars=1,
        )
        frame = urwid.Frame(body=self.body, footer=self.status)
        self.loop = urwid.MainLoop(
            frame,
            unhandled_input=self.unhandled_input,
            palette=[("status", "black", "light gray")],
        )

    def run(self):
        self._load_skin(0)
        self._load_playlist(0, auto_play=False)
        self.loop.set_alarm_in(0.2, self.refresh)
        self.loop.run()

    def refresh(self, loop=None, data=None):
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
            "STATUS": "",
            "NEXT_TRACK": "",
            "PLAYLIST": "",
            "TRACK_NUM": "",
        }
        if self.current_playlist:
            track = self.current_playlist.get_current_track()
            if track:
                context["TITLE"] = track.title[:25]  # Shorter for small screen
                context["ARTIST"] = track.artist[:20]
                context["PLAYLIST"] = self.current_playlist.get_name()[:20]
                context["TRACK_NUM"] = self.current_playlist.get_position_info()
                next_idx = self.current_playlist.current_index + 1
                if next_idx < self.current_playlist.get_track_count():
                    nt = self.current_playlist.tracks[next_idx]
                    context["NEXT_TRACK"] = nt.title[:20]

        info = self.player.get_time_info()
        context["TIME_CURRENT"] = info["current_formatted"]
        context["TIME_TOTAL"] = info["total_formatted"]
        context["TIME"] = f"{info['current_formatted']}/{info['total_formatted']}"

        if info["total_duration"] > 0:
            bar_width = 20  # Smaller progress bar
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
            self.status.set(
                f"Skin: {meta.get('name', skin_path.stem)[:20]} | " + HELP_TEXT
            )
        except Exception as e:
            self.skin_lines = pad_lines([], PAD_WIDTH, PAD_HEIGHT)
            self.status.set(f"Skin error: {str(e)[:30]}")

    def _load_playlist(self, idx, auto_play=True):
        if not self.playlists:
            self.current_playlist = None
            self.track_walker.clear()
            return
        self.current_playlist_idx = idx % len(self.playlists)
        name = self.playlists[self.current_playlist_idx]
        self.current_playlist = self.playlist_manager.load_playlist(name)
        self.track_walker.clear()
        for i, track in enumerate(self.current_playlist.tracks):
            w = urwid.Text(f"{i+1}. {track.title[:20]}")
            item = urwid.AttrMap(w, None, focus_map="reversed")
            item.track_index = i
            self.track_walker.append(item)
        if self.track_walker:
            self.track_listbox.focus_position = 0
            if auto_play:
                self._play_current_track(0)
        self.status.set(f"Playlist: {name[:15]} | " + HELP_TEXT)

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
            self.status.set(f"▶ {track.title[:30]} | " + HELP_TEXT)
            self.consecutive_errors = 0
        except Exception as e:
            self.consecutive_errors += 1
            if self.consecutive_errors >= 5:
                self.status.set(f"Too many errors. Stopped. | " + HELP_TEXT)
                self.player.stop()
                self.consecutive_errors = 0
                return
            self.status.set(f"Error, skipping... | " + HELP_TEXT)
            if not self._next_track():
                self.player.stop()
                self.status.set("End of playlist. | " + HELP_TEXT)

    def _next_track(self):
        if not self.current_playlist:
            return False
        nxt = self.current_playlist.next()
        if nxt:
            self._play_current_track(self.current_playlist.current_index)
            return True
        else:
            self.player.stop()
            self.status.set("Playlist finished. | " + HELP_TEXT)
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
        elif key == " ":
            self.player.toggle_pause()
        elif key in ("n", "N"):
            self._next_track()
        elif key in ("p", "P"):
            self._prev_track()
        elif key in ("s", "S"):
            self._load_skin(self.current_skin_idx + 1)
        elif key in ("l", "L"):
            self.player.stop()
            self._load_playlist(self.current_playlist_idx + 1, auto_play=False)
        elif key in ("m", "M"):
            self.player.stop()
            self.playlists = self.playlist_manager.list_playlists()
            self._load_playlist(0, auto_play=False)
        elif key == "up":
            self.player.volume_up()
        elif key == "down":
            self.player.volume_down()
        elif key == "right":
            self.player.seek(10)
        elif key == "left":
            self.player.seek(-10)
        elif key == "enter":
            try:
                focus = self.track_listbox.focus
                idx = getattr(focus, "track_index", 0)
                self._play_current_track(idx)
            except Exception:
                pass


def main():
    import shutil

    cols, lines = shutil.get_terminal_size()
    if cols < 80 or lines < 40:
        print(f"\n⚠️  Terminal: {cols}x{lines}")
        print("   Recomendado: 80x40 o más")
        print("   Continuando en 3 seg...")
        time.sleep(3)

    try:
        app = YTBMusicUI()
        app.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
    except KeyboardInterrupt:
        print("\n👋 Bye!")


if __name__ == "__main__":
    main()
