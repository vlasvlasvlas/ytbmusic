import urwid
from typing import TYPE_CHECKING, Dict, Any, List

if TYPE_CHECKING:
    from main import YTBMusicUI

PAD_WIDTH = 120
PAD_HEIGHT = 88


def pad_lines(
    lines: List[str], width: int = PAD_WIDTH, height: int = PAD_HEIGHT
) -> List[str]:
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
        self.skin_widget = SkinWidget()
        # Background fill behind the skin text
        self.bg_fill = urwid.SolidFill(" ")
        self.bg_attr = urwid.AttrMap(self.bg_fill, None)
        # Wrap skin in AttrMap so we can swap palette
        self.skin_attr = urwid.AttrMap(self.skin_widget, None)
        # Overlay skin over the background fill to ensure full repaint
        self.widget = urwid.Overlay(
            self.skin_attr,
            self.bg_attr,
            align="left",
            width=("relative", 100),
            valign="top",
            height=("relative", 100),
        )

    def render(self):
        """Render the current skin with player context."""
        c = self.controller
        width, height = self._compute_canvas_size()

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
                else ("⌛" if getattr(c, "is_buffering", False) else "■")
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
                context["REPEAT_STATUS"] = c.current_playlist.repeat_mode.value.upper()

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

        lines = pad_lines(c.skin_lines, width, height)
        rendered = c.skin_loader.render(
            lines, context, pad_width=width, pad_height=height
        )
        self.skin_widget.update("\n".join(rendered))

    def set_background_attr(self, attr_name: str = None):
        """Apply an attribute name to both the skin and its background fill."""
        try:
            self.skin_attr.set_attr_map({None: attr_name})
            self.bg_attr.set_attr_map({None: attr_name})
        except Exception:
            # Fallback: no attr map change
            pass

    def force_redraw(self):
        """Force a redraw of the skin text to apply palette changes."""
        try:
            current_text = self.skin_widget.text.get_text()[0]
            self.skin_widget.update(current_text)
        except Exception:
            pass

    def _compute_canvas_size(self) -> (int, int):
        """Calculate a safe canvas size based on current terminal size."""
        width = PAD_WIDTH
        height = PAD_HEIGHT
        try:
            cols, rows = self.controller.loop.screen.get_cols_rows()
            width = max(40, min(PAD_WIDTH, cols))
            height = max(20, min(PAD_HEIGHT, rows))
        except Exception:
            pass
        return width, height
