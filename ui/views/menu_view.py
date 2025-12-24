import urwid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import YTBMusicUI

class MenuListBox(urwid.ListBox):
    """ListBox that passes certain hotkeys through to unhandled_input."""

    # Keys that should NOT be handled by the ListBox
    PASSTHROUGH_KEYS = (
        "i", "I", "d", "D", "q", "Q",
        "1", "2", "3", "4", "5", "6", "7", "8", "9",
        "a", "A", "b", "B", "c", "C",
        "e", "E", "f", "F", "g", "G", "h", "H",
        "j", "J", "k", "K", "l", "L",
        "o", "O",
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
        playlist_focus_map = {}

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

        # NOTE: We set the walker on the controller because _refresh_menu_counts() needs it.
        # Ideally, _refresh_menu_counts should be moved here too.
        self.controller.menu_walker = urwid.SimpleFocusListWalker(items)
        
        # Alias for brevity
        walker = self.controller.menu_walker

        walker.append(urwid.Text(""))
        walker.append(urwid.Divider("═"))
        walker.append(
            urwid.AttrMap(
                urwid.Text("  ♪  SELECT PLAYLIST (1-9)", align="left"), "title"
            )
        )
        walker.append(urwid.Divider("─"))

        if not self.controller.playlists:
            walker.append(urwid.Text(""))
            walker.append(
                urwid.AttrMap(
                    urwid.Text("     No playlists found!", align="center"), "error"
                )
            )
            walker.append(
                urwid.Text("     Add .json files to playlists/ folder", align="center")
            )
        else:
            for i, pl_name in enumerate(self.controller.playlists[:9]):
                meta = self.controller._get_playlist_metadata(pl_name)

                # Get download stats
                down_count, total_count = self.controller._count_downloaded_tracks(pl_name)

                if meta:
                    display = f"    [{i+1}] {meta.name} ({down_count}/{total_count} downloaded)"
                else:
                    display = f"    [{i+1}] {pl_name} ({down_count}/{total_count})"

                # Highlight selected
                style = None
                if i == self.controller.selected_playlist_idx:
                    display += "  ← SELECTED"
                    style = "highlight"

                btn = urwid.Button(display)
                urwid.connect_signal(
                    btn, "click", lambda b, idx=i: self.controller._on_playlist_select(b, idx)
                )
                walker.append(
                    urwid.AttrMap(btn, style, focus_map="highlight")
                )
                playlist_focus_map[i] = len(walker) - 1

        # Actions for selected playlist
        if self.controller.selected_playlist_idx is not None and self.controller.selected_playlist_idx < len(
            self.controller.playlists
        ):
            walker.append(urwid.Divider(" "))
            walker.append(
                urwid.Text("      Actions for selected:", align="left")
            )

            # PLAY Button
            play_btn = urwid.Button(f"      [P] PLAY NOW")
            urwid.connect_signal(play_btn, "click", lambda b: self.controller._on_play_selected())
            walker.append(
                urwid.AttrMap(play_btn, None, focus_map="highlight")
            )

            # DELETE Button
            del_btn = urwid.Button(f"      [X] DELETE PLAYLIST")
            urwid.connect_signal(del_btn, "click", lambda b: self.controller._on_delete_selected())
            walker.append(urwid.AttrMap(del_btn, None, focus_map="highlight"))

            # RENAME Button
            ren_btn = urwid.Button(f"      [E] RENAME PLAYLIST")
            urwid.connect_signal(ren_btn, "click", lambda b: self.controller._on_rename_selected())
            walker.append(urwid.AttrMap(ren_btn, None, focus_map="highlight"))

            # DOWNLOAD Button
            dl_btn = urwid.Button(f"      [D] DOWNLOAD MISSING")
            urwid.connect_signal(
                dl_btn, "click", lambda b: self.controller._download_selected_playlist()
            )
            walker.append(urwid.AttrMap(dl_btn, None, focus_map="highlight"))

        walker.append(urwid.Text(""))
        walker.append(urwid.Divider("═"))

        # Import button
        import_btn = urwid.Button("    [I] Import from YouTube")
        urwid.connect_signal(
            import_btn, "click", lambda b: self.controller._prompt_import_playlist()
        )
        walker.append(urwid.AttrMap(import_btn, None, focus_map="highlight"))

        # Random All button
        random_btn = urwid.Button("    [R] 🔀 Random All Songs")
        urwid.connect_signal(random_btn, "click", lambda b: self.controller._on_random_all())
        walker.append(urwid.AttrMap(random_btn, None, focus_map="highlight"))

        # Settings button
        settings_btn = urwid.Button("    [O] Settings / Herramientas")
        urwid.connect_signal(settings_btn, "click", lambda b: self.controller._open_settings_modal())
        walker.append(urwid.AttrMap(settings_btn, None, focus_map="highlight"))

        walker.append(urwid.Divider(" "))
        
        skin_keys_label = self._get_skin_keys_label()
        
        walker.append(
            urwid.AttrMap(
                urwid.Text(f"  🎨  SELECT SKIN ({skin_keys_label})", align="left"),
                "title",
            )
        )
        walker.append(urwid.Divider("─"))

        if not self.controller.skins:
            walker.append(
                urwid.AttrMap(
                    urwid.Text("     No skins found!", align="center"), "error"
                )
            )
            walker.append(
                urwid.Text("     Add .txt files to skins/ folder", align="center")
            )
        else:
            for i, skin_name in enumerate(self.controller.skins[: len(str(self.controller.skin_hotkeys))]):
                meta = self.controller._get_skin_metadata(skin_name)
                hotkey = self.controller.skin_hotkeys[i]
                display = f"    [{hotkey}] {meta.name if meta else skin_name}"
                if i == self.controller.current_skin_idx:
                    display += " ← Current"
                btn = urwid.Button(display)
                urwid.connect_signal(
                    btn, "click", lambda b, idx=i: self.controller._on_skin_select(b, idx)
                )
                walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))

        walker.append(urwid.Text(""))
        walker.append(
            urwid.AttrMap(
                urwid.Text(
                    "  ↑/↓ Navigate  •  Enter Select  •  O Settings  •  Q Quit", align="center"
                ),
                "status",
            )
        )
        
        listbox = MenuListBox(walker)
        
        # Keep focus on the selected playlist row if available
        # Note: We need payload_focus_map which was local variable.
        # It's populated during iteration.
        # Logic: i (playlist index) -> walker index.
        # Since I'm reconstructing, I should probably restore focus.
        if (
            self.controller.selected_playlist_idx is not None
            and self.controller.selected_playlist_idx in playlist_focus_map
        ):
            try:
                walker.set_focus(
                    playlist_focus_map[self.controller.selected_playlist_idx]
                )
            except Exception:
                pass
                
        return listbox

    def _get_skin_keys_label(self) -> str:
        hotkeys = self.controller.skin_hotkeys
        if hotkeys == "ABCDFGHJKL":
            return "A-D/F-H/J-L"
        if hotkeys == "ABCDEFGHJK":
            return "A-H/J-K"
        return hotkeys
