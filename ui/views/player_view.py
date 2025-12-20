import urwid
from typing import TYPE_CHECKING, Dict, Any, List

if TYPE_CHECKING:
    from main import YTBMusicUI

PAD_WIDTH = 120
PAD_HEIGHT = 88

def pad_lines(lines: List[str], width: int = PAD_WIDTH, height: int = PAD_HEIGHT) -> List[str]:
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


class PlayerView:
    def __init__(self, controller: "YTBMusicUI"):
        self.controller = controller
        self.widget = SkinWidget()

    def render(self):
        """Render the current skin with player context."""
        c = self.controller
        
        # Determine cached status logic (originally in _render_skin start)
        # Note: logic modified to access controller state
        if c.current_playlist:
            track = c.current_playlist.get_current_track()
            if track:
                # We need access to downloader.
                # Assuming c.downloader exists.
                cached_path = c.downloader.is_cached(
                    track.url, title=track.title, artist=track.artist
                )
                c.is_cached_playback = cached_path is not None

        context = {
            "PREV": "<<",
            "NEXT": ">>",
            "PLAY": "||" if c.player.is_playing() else "▶",
            "VOL_DOWN": "─",
            "VOL_UP": "+",
            "QUIT": "Q",
            "TITLE": "",
            "ARTIST": "",
            "TIME": "00:00/00:00",
            "TIME_CURRENT": "00:00",
            "TIME_TOTAL": "00:00",
            "PROGRESS": "[          ]",
            "VOLUME": f"{c.player.volume}%",
            "STATUS": (
                "♪"
                if c.player.is_playing()
                else ("⌛" if getattr(c, 'is_buffering', False) else "■")
            ),
            "NEXT_TRACK": "",
            "PLAYLIST": "",
            "TRACK_NUM": "",
            "CACHE_STATUS": "✓" if c.is_cached_playback else "✗",
            "SHUFFLE_STATUS": "OFF",
            "REPEAT_STATUS": "ALL",
        }

        if c.current_playlist:
            track = c.current_playlist.get_current_track()
            if track:
                context["TITLE"] = track.title[:35]
                context["ARTIST"] = track.artist[:30]
                context["PLAYLIST"] = c.current_playlist.get_name()[:25]
                context["TRACK_NUM"] = c.current_playlist.get_position_info()
                context["SHUFFLE_STATUS"] = (
                    "ON" if c.current_playlist.shuffle_enabled else "OFF"
                )
                context["REPEAT_STATUS"] = (
                    c.current_playlist.repeat_mode.value.upper()
                )

                # Use peek_next() for clean next track prediction
                next_track = c.current_playlist.peek_next()
                if next_track:
                    context["NEXT_TRACK"] = next_track.title[:30]

        info = c.player.get_time_info()
        context["TIME_CURRENT"] = info["current_formatted"]
        context["TIME_TOTAL"] = info["total_formatted"]
        context["TIME"] = f"{info['current_formatted']}/{info['total_formatted']}"
        if info["total_duration"] > 0:
            bar_width = 25
            filled = int((info["percentage"] / 100) * bar_width)
            context["PROGRESS"] = "[" + "█" * filled + "░" * (bar_width - filled) + "]"

        # Ensure skin_lines exists
        if not c.skin_lines:
             # Fallback or simple clear
             self.widget.update("")
             return

        lines = pad_lines(c.skin_lines, PAD_WIDTH, PAD_HEIGHT)
        rendered = c.skin_loader.render(
            lines, context, pad_width=PAD_WIDTH, pad_height=PAD_HEIGHT
        )
        self.widget.update("\n".join(rendered))
