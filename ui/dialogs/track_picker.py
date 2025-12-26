"""
TrackPickerDialog Widget

Scrollable track picker overlay for playlists with search functionality.
"""

import urwid
from typing import List, Callable, Optional


class TrackPickerDialog(urwid.WidgetWrap):
    """Scrollable track picker overlay for the current playlist."""

    def __init__(
        self,
        title: str,
        tracks: list,
        current_idx: int,
        on_select,
        on_cancel,
        status_checker=None,
    ):
        self._on_select = on_select
        self._on_cancel = on_cancel
        self.status_checker = status_checker

        self._title = title
        self._tracks = list(tracks)
        self._current_idx = int(current_idx)
        self._filtered_indices: list[int] = []
        self._search_active = False

        self._header = urwid.Text("", align="center")
        self._hint = urwid.Text(
            " Enter=Play  /=Search  Esc=Close  ↑/↓=Navigate ", align="center"
        )
        self._search = urwid.Edit(" Search: ")
        self._footer = urwid.Pile([self._hint, self._search])
        self._footer.focus_position = 0

        self._walker = urwid.SimpleFocusListWalker([])
        self._listbox = urwid.ListBox(self._walker)

        self._frame = urwid.Frame(
            body=self._listbox, header=self._header, footer=self._footer
        )
        super().__init__(urwid.LineBox(self._frame))

        self._apply_filter("")

    def _update_header(self, query: str) -> None:
        total = len(self._tracks)
        shown = len(self._filtered_indices)
        q = (query or "").strip()
        suffix = f"  (filter: {q})" if q else ""
        self._header.set_text(
            ("title", f" {self._title} — Tracks {shown}/{total}{suffix} ")
        )

    def _track_label(self, original_index: int) -> str:
        tr = self._tracks[original_index]
        artist = (getattr(tr, "artist", "") or "").strip()
        ttitle = (getattr(tr, "title", "") or "").strip()

        label = f"{original_index + 1:>3}. "
        if original_index == self._current_idx:
            label += "▶ "
        if getattr(tr, "is_playable", True) is False:
            label += "✗ "

        if artist and ttitle:
            label += f"{artist} - {ttitle}"
        else:
            label += ttitle or artist or "Unknown"
        return label

    def _apply_filter(self, query: str) -> None:
        q = (query or "").casefold().strip()
        self._filtered_indices = []
        for i, tr in enumerate(self._tracks):
            artist = (getattr(tr, "artist", "") or "").casefold()
            ttitle = (getattr(tr, "title", "") or "").casefold()
            if not q or q in f"{artist} {ttitle}":
                self._filtered_indices.append(i)

        del self._walker[:]

        if not self._filtered_indices:
            self._walker.append(urwid.Text(" No matches"))
            self._update_header(query)
            return

        for original_index in self._filtered_indices:
            btn = urwid.Button(self._track_label(original_index))
            urwid.connect_signal(
                btn, "click", lambda b, idx=original_index: self._on_select(idx)
            )
            attr = "normal"
            if self.status_checker:
                status = self.status_checker(self._tracks[original_index])
                if status == "downloaded":
                    attr = "track_downloaded"
                elif status == "downloading":
                    attr = "track_downloading"
                elif status == "missing":
                    attr = "track_missing"

            self._walker.append(urwid.AttrMap(btn, attr, focus_map="highlight"))

        focus_pos = 0
        if self._current_idx in self._filtered_indices:
            try:
                focus_pos = self._filtered_indices.index(self._current_idx)
            except ValueError:
                focus_pos = 0
        try:
            self._walker.set_focus(max(0, min(int(focus_pos), len(self._walker) - 1)))
        except Exception:
            pass

        self._update_header(query)

    def _enter_search(self) -> None:
        self._search_active = True
        self._frame.focus_part = "footer"
        self._footer.focus_position = 1

    def _exit_search(self) -> None:
        self._search_active = False
        self._frame.focus_part = "body"
        self._footer.focus_position = 0

    def keypress(self, size, key):
        if key == "/" and not self._search_active:
            self._enter_search()
            return None

        if key == "esc":
            if self._search_active:
                if self._search.get_edit_text():
                    self._search.set_edit_text("")
                    self._apply_filter("")
                    self._exit_search()
                    return None
                self._exit_search()
            self._on_cancel()
            return None

        if key in ("t", "T") and not self._search_active:
            self._on_cancel()
            return None

        result = super().keypress(size, key)

        if self._search_active:
            if key == "enter":
                self._exit_search()
                return None
            self._apply_filter(self._search.get_edit_text())

        return result
