"""
ModalOverlay Widget

Generic modal dialog with ESC/Q close support.
"""

import urwid


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
