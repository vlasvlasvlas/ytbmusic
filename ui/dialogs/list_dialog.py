"""
ListDialog Widget

Generic list selector dialog with optional disclaimer.
"""

import urwid
from typing import List


class ListDialog(urwid.WidgetWrap):
    """Generic list selector dialog with optional disclaimer."""

    def __init__(
        self,
        title: str,
        items: List[dict],
        on_select,
        on_cancel=None,
        disclaimer: str = None,
    ):
        self.on_select = on_select
        self.on_cancel = on_cancel

        walker = urwid.SimpleFocusListWalker([])
        walker.append(urwid.Text(("title", f" {title} "), align="center"))
        walker.append(urwid.Divider("─"))
        if disclaimer:
            walker.append(urwid.Text(("error", disclaimer), align="center"))
            walker.append(urwid.Divider())

        first_focus = None
        for entry in items:
            label = entry.get("label", "")
            value = entry.get("value", label)
            note = entry.get("note")
            btn = urwid.Button(label)
            urwid.connect_signal(btn, "click", lambda b, v=value: self._do_select(v))
            widget = urwid.AttrMap(btn, None, focus_map="highlight")
            walker.append(widget)
            if note:
                walker.append(urwid.Text(("info", f"   {note}")))
            if first_focus is None:
                first_focus = len(walker) - 1

        if first_focus is not None:
            try:
                walker.set_focus(first_focus)
            except Exception:
                pass

        walker.append(urwid.Divider())
        walker.append(
            urwid.Text("↑/↓ Navegar • Enter seleccionar • Esc/Q cerrar", align="center")
        )

        listbox = urwid.ListBox(walker)
        frame = urwid.Frame(body=listbox)
        super().__init__(urwid.LineBox(frame))

    def _do_select(self, value):
        if self.on_select:
            self.on_select(value)

    def keypress(self, size, key):
        if key in ("esc", "q", "Q"):
            if self.on_cancel:
                self.on_cancel()
            return None
        return super().keypress(size, key)
