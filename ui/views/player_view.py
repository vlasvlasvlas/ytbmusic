import urwid
import logging
from typing import TYPE_CHECKING, Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

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
    
    def update_with_colors(self, lines: List[str], colors: List[Tuple[str, str]], loop=None, direction: str = "vertical"):
        """
        Update text with per-line or per-segment colors using urwid text markup.
        
        Args:
            lines: List of text strings
            colors: List of (fg, bg) tuples
            loop: urwid MainLoop for palette registration
            direction: "vertical", "horizontal", "diagonal", "diagonal_inv", "radial"
        """
        if not lines or not colors:
            self.text.set_text("\n".join(lines) if lines else "")
            return
        
        if direction == "horizontal":
            self._update_horizontal(lines, colors, loop)
        elif direction == "diagonal":
            self._update_diagonal(lines, colors, loop)
        elif direction == "diagonal_inv":
            self._update_diagonal_inv(lines, colors, loop)
        elif direction == "radial":
            self._update_radial(lines, colors, loop)
        else:
            self._update_vertical(lines, colors, loop)
    
    def _update_vertical(self, lines: List[str], colors: List[Tuple[str, str]], loop=None):
        """Apply one color per line (vertical gradient)."""
        markup = []
        for i, line in enumerate(lines):
            fg, bg = colors[i % len(colors)]
            palette_name = f"line_{bg}_{fg}"
            
            if loop:
                try:
                    loop.screen.register_palette_entry(palette_name, fg, bg)
                except Exception:
                    pass
            
            if i > 0:
                markup.append("\n")
            markup.append((palette_name, line))
        
        self.text.set_text(markup)
    
    def _update_horizontal(self, lines: List[str], colors: List[Tuple[str, str]], loop=None):
        """Apply colors across each line (horizontal gradient)."""
        markup = []
        num_colors = len(colors)
        
        for i, line in enumerate(lines):
            if i > 0:
                markup.append("\n")
            
            if not line:
                markup.append("")
                continue
            
            # Calculate segment width - divide line into color bands
            segment_width = max(1, len(line) // num_colors)
            
            for seg_idx in range(num_colors):
                start = seg_idx * segment_width
                if seg_idx == num_colors - 1:
                    # Last segment takes the rest
                    end = len(line)
                else:
                    end = start + segment_width
                
                if start >= len(line):
                    break
                
                segment = line[start:end]
                if not segment:
                    continue
                
                fg, bg = colors[seg_idx]
                palette_name = f"hseg_{bg}_{fg}"
                
                if loop:
                    try:
                        loop.screen.register_palette_entry(palette_name, fg, bg)
                    except Exception:
                        pass
                
                markup.append((palette_name, segment))
        
        self.text.set_text(markup)
    
    def _update_diagonal(self, lines: List[str], colors: List[Tuple[str, str]], loop=None):
        """Apply colors diagonally - color based on row + column position."""
        markup = []
        num_colors = len(colors)
        num_lines = len(lines)
        
        # Determine max line width for normalization
        max_width = max(len(line) for line in lines) if lines else 80
        
        for row, line in enumerate(lines):
            if row > 0:
                markup.append("\n")
            
            if not line:
                markup.append("")
                continue
            
            # Calculate segment width
            segment_width = max(1, len(line) // num_colors)
            
            for seg_idx in range(num_colors):
                start = seg_idx * segment_width
                if seg_idx == num_colors - 1:
                    end = len(line)
                else:
                    end = start + segment_width
                
                if start >= len(line):
                    break
                
                segment = line[start:end]
                if not segment:
                    continue
                
                # Diagonal: color based on normalized (row + column)
                # This creates a diagonal sweep from top-left to bottom-right
                row_factor = row / max(num_lines, 1)
                col_factor = seg_idx / max(num_colors, 1)
                diag_pos = (row_factor + col_factor) / 2  # Average gives diagonal
                color_idx = int(diag_pos * num_colors) % num_colors
                
                fg, bg = colors[color_idx]
                palette_name = f"diag_{bg}_{fg}"
                
                if loop:
                    try:
                        loop.screen.register_palette_entry(palette_name, fg, bg)
                    except Exception:
                        pass
                
                markup.append((palette_name, segment))
        
        self.text.set_text(markup)
    
    def _update_diagonal_inv(self, lines: List[str], colors: List[Tuple[str, str]], loop=None):
        """Apply colors diagonally in opposite direction (top-right to bottom-left)."""
        markup = []
        num_colors = len(colors)
        num_lines = len(lines)
        
        for row, line in enumerate(lines):
            if row > 0:
                markup.append("\n")
            
            if not line:
                markup.append("")
                continue
            
            segment_width = max(1, len(line) // num_colors)
            
            for seg_idx in range(num_colors):
                start = seg_idx * segment_width
                if seg_idx == num_colors - 1:
                    end = len(line)
                else:
                    end = start + segment_width
                
                if start >= len(line):
                    break
                
                segment = line[start:end]
                if not segment:
                    continue
                
                # Diagonal inverse: row - column gives opposite diagonal
                row_factor = row / max(num_lines, 1)
                col_factor = seg_idx / max(num_colors, 1)
                # Subtract column from row to invert direction
                diag_pos = (row_factor + (1 - col_factor)) / 2
                color_idx = int(diag_pos * num_colors) % num_colors
                
                fg, bg = colors[color_idx]
                palette_name = f"diaginv_{bg}_{fg}"
                
                if loop:
                    try:
                        loop.screen.register_palette_entry(palette_name, fg, bg)
                    except Exception:
                        pass
                
                markup.append((palette_name, segment))
        
        self.text.set_text(markup)
    
    def _update_radial(self, lines: List[str], colors: List[Tuple[str, str]], loop=None):
        """Apply colors radially from center - like ripples on water."""
        import math
        markup = []
        num_colors = len(colors)
        num_lines = len(lines)
        
        # Center point
        center_row = num_lines / 2
        max_width = max(len(line) for line in lines) if lines else 80
        center_col = max_width / 2
        
        # Max distance for normalization
        max_dist = math.sqrt(center_row**2 + center_col**2)
        
        for row, line in enumerate(lines):
            if row > 0:
                markup.append("\n")
            
            if not line:
                markup.append("")
                continue
            
            segment_width = max(1, len(line) // num_colors)
            
            for seg_idx in range(num_colors):
                start = seg_idx * segment_width
                if seg_idx == num_colors - 1:
                    end = len(line)
                else:
                    end = start + segment_width
                
                if start >= len(line):
                    break
                
                segment = line[start:end]
                if not segment:
                    continue
                
                # Calculate distance from center (circular)
                col_pos = start + segment_width / 2
                dist_row = row - center_row
                dist_col = col_pos - center_col
                distance = math.sqrt(dist_row**2 + dist_col**2)
                
                # Normalize and get color
                normalized = distance / max_dist if max_dist > 0 else 0
                color_idx = int(normalized * num_colors) % num_colors
                
                fg, bg = colors[color_idx]
                palette_name = f"radial_{bg}_{fg}"
                
                if loop:
                    try:
                        loop.screen.register_palette_entry(palette_name, fg, bg)
                    except Exception:
                        pass
                
                markup.append((palette_name, segment))
        
        self.text.set_text(markup)


class PlayerView:
    def __init__(self, controller: "YTBMusicUI"):
        self.controller = controller
        self.skin_widget = SkinWidget()
        
        # Background fill behind the skin text
        self.bg_fill = urwid.SolidFill(" ")
        self.bg_attr = urwid.AttrMap(self.bg_fill, None)
        
        # Wrap skin in AttrMap so we can swap palette
        self.skin_attr = urwid.AttrMap(self.skin_widget, None)
        
        # Gradient mode flag
        self._gradient_mode = False
        
        # Overlay skin over the background fill to ensure full repaint
        self.widget = urwid.Overlay(
            self.skin_attr,
            self.bg_attr,
            align="left",
            width=("relative", 100),
            valign="top",
            height=("relative", 100),
        )
        
        # Store rendered lines for gradient mode
        self._current_rendered_lines: List[str] = []

    def render(self):
        """Render the current skin with player context."""
        c = self.controller
        width, height = self._compute_canvas_size()

        # Determine cached status logic
        if c.current_playlist:
            track = c.current_playlist.get_current_track()
            if track:
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

        if not c.skin_lines:
            return

        lines = pad_lines(c.skin_lines, width, height)
        rendered = c.skin_loader.render(
            lines, context, pad_width=width, pad_height=height
        )
        
        # Store for gradient mode
        self._current_rendered_lines = rendered
        
        # If in gradient mode, don't update here - gradient will update with colors
        if not self._gradient_mode:
            self.skin_widget.update("\n".join(rendered))

    def set_background_attr(self, attr_name: str = None):
        """Apply an attribute name to both the skin and its background fill."""
        # Disable gradient mode when using solid background
        self._gradient_mode = False
        try:
            self.skin_attr.set_attr_map({None: attr_name})
            self.bg_attr.set_attr_map({None: attr_name})
        except Exception:
            pass

    def set_gradient_colors(self, colors: List[Tuple[str, str]], loop=None, direction: str = "vertical"):
        """
        Apply per-line gradient colors for demoscene effect.
        Uses urwid text markup for per-line or per-segment coloring.
        
        Args:
            colors: List of (fg, bg) tuples
            loop: urwid MainLoop for palette registration
            direction: "vertical" or "horizontal"
        """
        if not colors:
            logger.warning("[GRADIENT_VIEW] No colors provided")
            return
        
        # Enable gradient mode
        self._gradient_mode = True
        
        # Clear solid background attr - we're using per-line colors now
        try:
            self.skin_attr.set_attr_map({None: None})
            self.bg_attr.set_attr_map({None: None})
        except Exception:
            pass
        
        # Get current rendered lines
        lines = self._current_rendered_lines
        if not lines:
            width, height = self._compute_canvas_size()
            lines = [" " * width] * height
        
        # Update skin widget with colored lines
        self.skin_widget.update_with_colors(lines, colors, loop, direction)
        logger.debug(f"[GRADIENT_VIEW] Applied {len(colors)} line colors")

    def force_redraw(self):
        """Force a redraw of the skin text to apply palette changes."""
        try:
            current_text = self.skin_widget.text.get_text()[0]
            self.skin_widget.update(str(current_text) if not isinstance(current_text, str) else current_text)
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
