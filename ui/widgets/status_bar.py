"""
StatusBar Widget

Three-line status bar showing contextual shortcuts and notifications.
"""

import urwid


class StatusBar(urwid.WidgetWrap):
    """Three-line status bar: Info (Top) + Playback Shortcuts (Mid) + App Shortcuts (Bot)."""

    SHORTCUTS_PLAY = "Space=⏯  N/P=⏭⏮  ←/→=Seek  ↑/↓=Vol  Z=Shuffle  R=Repeat"
    SHORTCUTS_APP = "T=Tracks  S=Skin  A=Anim  V=NextAnim  M=Menu  Q=Quit"

    SHORTCUTS_MENU = (
        "1-9=Select  I=Import  X=Delete  E=Rename  R=RandomAll  F=Find  Q=Quit"
    )
    SHORTCUTS_MENU_APP = "S=Skin  A=Anim  D=Download  O=Settings"

    def __init__(self, context_text=""):
        self.top_line = urwid.Text(context_text, align="center")
        self.mid_line = urwid.Text(self.SHORTCUTS_PLAY, align="center")
        self.bot_line = urwid.Text(self.SHORTCUTS_APP, align="center")

        # Keep references to AttrWrappers to change styles dynamically
        self.top_attr = urwid.AttrWrap(self.top_line, "status")
        self.mid_attr = urwid.AttrWrap(self.mid_line, "status")
        self.bot_attr = urwid.AttrWrap(self.bot_line, "status")

        self._default_info = context_text

        self.pile = urwid.Pile(
            [
                self.top_attr,
                self.mid_attr,
                self.bot_attr,
            ]
        )
        super().__init__(self.pile)

    def update_context(self, context: str):
        """Update shortcuts based on context (menu/player)."""
        if context == "menu":
            self.mid_line.set_text(self.SHORTCUTS_MENU)
            self.bot_line.set_text(self.SHORTCUTS_MENU_APP)
        elif context == "player":
            self.mid_line.set_text(self.SHORTCUTS_PLAY)
            self.bot_line.set_text(self.SHORTCUTS_APP)

    def set(self, text):
        """Set the persistent info message (Top Line)."""
        # Clean up any " | HELP_TEXT" that might be passed from legacy calls
        if " | Space=" in text:
            text = text.split(" | Space=")[0]

        self.top_line.set_text(text)
        self._default_info = text

    def notify(self, text, style="status"):
        """Set a transient notification (Top Line)."""
        self.top_line.set_text(text)
        self.top_attr.set_attr(style)

    def clear_notify(self):
        """Restore default info to Top Line."""
        self.top_line.set_text(self._default_info)
        self.top_attr.set_attr("status")
