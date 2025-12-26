"""
ConfirmDialog Widget

Modal confirmation dialog with Yes/No buttons.
"""

import urwid


class ConfirmDialog(urwid.WidgetWrap):
    """
    Modal confirmation dialog that traps focus and keys.
    Prevents key leakage to underlying widgets.
    """

    def __init__(self, title, message, on_confirm, on_cancel=None):
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        yes_btn = urwid.Button(" Yes ")
        no_btn = urwid.Button(" No ")

        urwid.connect_signal(yes_btn, "click", self._do_confirm)
        urwid.connect_signal(no_btn, "click", self._do_cancel)

        # Build UI
        pile = urwid.Pile(
            [
                urwid.Text(("title", f" {title} "), align="center"),
                urwid.Divider(),
                urwid.Text(message, align="center"),
                urwid.Divider(),
                urwid.Columns(
                    [
                        (
                            "weight",
                            1,
                            urwid.AttrMap(yes_btn, None, focus_map="highlight"),
                        ),
                        (
                            "weight",
                            1,
                            urwid.AttrMap(no_btn, None, focus_map="highlight"),
                        ),
                    ],
                    dividechars=2,
                ),
            ]
        )

        # Frame it
        frame = urwid.LineBox(urwid.Filler(pile, valign="middle"))
        super().__init__(frame)

    def _do_confirm(self, button=None):
        if self.on_confirm:
            self.on_confirm()

    def _do_cancel(self, button=None):
        if self.on_cancel:
            self.on_cancel()

    def keypress(self, size, key):
        """
        Trap all keys to ensure modality.
        Only handle navigation/activation keys, consume everything else.
        """
        # Global cancel
        if key in ("esc", "q", "Q"):
            self._do_cancel()
            return None

        # Confirm on Enter if general focus (though buttons handle it too)
        if key == "enter":
            return super().keypress(size, key)

        # Allow navigation
        if key in ("left", "right", "tab", "up", "down"):
            return super().keypress(size, key)

        # Consume any other key to prevent leakage
        return None
