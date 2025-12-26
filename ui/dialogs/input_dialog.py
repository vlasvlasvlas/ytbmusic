"""
InputDialog Widget

ASCII-styled input dialog for retro aesthetic.
"""

import urwid


class InputDialog(urwid.WidgetWrap):
    """ASCII-styled input dialog for retro aesthetic."""

    def __init__(self, title, label, callback, default_text=""):
        self.callback = callback
        self.edit = urwid.Edit(f"  {label}: ", edit_text=default_text)
        edit_row_index = None

        # ASCII box art header
        header_art = [
            "╔════════════════════════════════════════════════════════╗",
            f"║  {title:^54}  ║",
            "╠════════════════════════════════════════════════════════╣",
        ]

        footer_art = [
            "╠════════════════════════════════════════════════════════╣",
            "║     [Enter] Confirm            [Esc] Cancel            ║",
            "╚════════════════════════════════════════════════════════╝",
        ]

        body_widgets = []
        for line in header_art:
            body_widgets.append(urwid.Text(line))
        body_widgets.append(
            urwid.Text("║                                                          ║")
        )
        body_widgets.append(
            urwid.Columns(
                [
                    ("fixed", 2, urwid.Text("║ ")),
                    self.edit,
                    ("fixed", 2, urwid.Text(" ║")),
                ]
            )
        )
        edit_row_index = len(body_widgets) - 1
        body_widgets.append(
            urwid.Text("║                                                          ║")
        )
        for line in footer_art:
            body_widgets.append(urwid.Text(line))

        pile = urwid.Pile(body_widgets)
        if edit_row_index is not None:
            pile.focus_position = edit_row_index
        fill = urwid.Filler(pile, valign="middle")
        super().__init__(fill)

    def keypress(self, size, key):
        if key == "enter":
            self.callback(self.edit.edit_text)
        elif key == "esc":
            self.callback(None)
        return super().keypress(size, key)
