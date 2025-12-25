import urwid
from typing import TYPE_CHECKING
from config.i18n import t

if TYPE_CHECKING:
    from main import YTBMusicUI


class MenuListBox(urwid.ListBox):
    """ListBox that passes certain hotkeys through to unhandled_input."""

    # Keys that should NOT be handled by the ListBox
    PASSTHROUGH_KEYS = (
        "i",
        "I",
        "d",
        "D",
        "q",
        "Q",
        "a",
        "A",
        "b",
        "B",
        "c",
        "C",
        "e",
        "E",
        "f",
        "F",
        "g",
        "G",
        "h",
        "H",
        "j",
        "J",
        "k",
        "K",
        "l",
        "L",
        "o",
        "O",
        "p",
        "P",
        "r",
        "R",
        "x",
        "X",
    )

    def keypress(self, size, key):
        if key in self.PASSTHROUGH_KEYS:
            return key  # Pass through to unhandled_input
        return super().keypress(size, key)


class MenuView:
    def __init__(self, controller: "YTBMusicUI"):
        self.controller = controller

    def create(self) -> urwid.Widget:
        """Create and return the Menu ListBox."""
        items = []

        # Title Art
        title = [
            "",
            "  ________  ________  ________  _______   ________  ________   ________  ________ ",
            " ╱    ╱   ╲╱        ╲╱       ╱ ╱       ╲╲╱    ╱   ╲╱        ╲ ╱        ╲╱        ╲",
            "╱         ╱        _╱        ╲╱        ╱╱         ╱        _╱_╱       ╱╱         ╱",
            "╲__     ╱╱╱       ╱╱         ╱         ╱         ╱-        ╱╱         ╱       --╱ ",
            "  ╲____╱╱ ╲______╱ ╲________╱╲__╱__╱__╱╲________╱╲________╱ ╲________╱╲________╱  ",
            "",
        ]
        for line in title:
            items.append(urwid.Text(line, align="center"))

        self.controller.menu_walker = urwid.SimpleFocusListWalker(items)
        walker = self.controller.menu_walker

        walker.append(urwid.Divider("─"))

        # State summary
        current_pl = None
        if self.controller.current_playlist:
            current_pl = self.controller.current_playlist.get_name()
        elif self.controller.selected_playlist_idx is not None:
            try:
                current_pl = self.controller.playlists[
                    self.controller.selected_playlist_idx
                ]
            except Exception:
                current_pl = None

        dl_info = ""
        if current_pl:
            dl, tot = self.controller._count_downloaded_tracks(current_pl)
            dl_info = f" ({dl}/{tot} {t('menu.downloaded')})"

        skin_label = (
            self.controller.skins[self.controller.current_skin_idx]
            if self.controller.skins
            else "N/A"
        )
        bg_label = (
            self.controller.backgrounds[self.controller.current_background_idx]
            if getattr(self.controller, "backgrounds", None)
            else "N/A"
        )

        none_label = t("menu.none") if hasattr(t, "__call__") else "None"
        walker.append(
            urwid.Text(
                f"Playlist: {current_pl or none_label}{dl_info}  |  Skin: {skin_label}  |  {t('menu.background')}: {bg_label}",
                align="center",
            )
        )

        walker.append(urwid.Divider(" "))

        # Pickers (modal)
        playlist_picker = urwid.Button(t("menu.select_playlist"))
        urwid.connect_signal(
            playlist_picker, "click", lambda b: self.controller._open_playlist_modal()
        )
        skin_picker = urwid.Button(t("menu.select_skin"))
        urwid.connect_signal(
            skin_picker, "click", lambda b: self.controller._open_skin_modal()
        )
        bg_picker = urwid.Button(t("menu.select_background"))
        urwid.connect_signal(
            bg_picker, "click", lambda b: self.controller._open_background_modal()
        )
        for btn in [playlist_picker, skin_picker, bg_picker]:
            walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))

        walker.append(urwid.Divider("─"))
        walker.append(urwid.Text(t("menu.quick_actions"), align="center"))

        action_buttons = [
            (f"[I] {t('menu.import')}", self.controller._prompt_import_playlist),
            (f"[P] {t('menu.play')}", self.controller._on_play_selected),
            (f"[R] {t('menu.random')}", self.controller._on_random_all),
            (f"[D] {t('menu.download')}", self.controller._download_selected_playlist),
            (f"[E] {t('menu.rename')}", self.controller._on_rename_selected),
            (f"[X] {t('menu.delete')}", self.controller._on_delete_selected),
        ]
        for label, cb in action_buttons:
            btn = urwid.Button(label)
            urwid.connect_signal(btn, "click", lambda b, fn=cb: fn())
            walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))

        walker.append(urwid.Divider(" "))
        search_btn = urwid.Button(f"[F] {t('menu.search')}")
        urwid.connect_signal(
            search_btn, "click", lambda b: self.controller._prompt_global_search()
        )
        settings_btn = urwid.Button(f"[O] {t('menu.settings')}")
        urwid.connect_signal(
            settings_btn, "click", lambda b: self.controller._open_settings_modal()
        )
        walker.append(urwid.AttrMap(search_btn, None, focus_map="highlight"))
        walker.append(urwid.AttrMap(settings_btn, None, focus_map="highlight"))

        walker.append(urwid.Divider(" "))
        walker.append(
            urwid.AttrMap(
                urwid.Text(t("menu.footer"), align="center"),
                "status",
            )
        )

        listbox = MenuListBox(walker)
        return listbox
