"""
MessageLog Widget

Scrolling log widget for displaying activity messages.
"""

import time
import urwid


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
