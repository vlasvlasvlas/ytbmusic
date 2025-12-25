"""
Menu Stack System for Scalable Navigation

Implements a push/pop navigation stack for submenu support,
allowing nested menus with back navigation.
"""

from typing import Optional, List, Callable, Any, NamedTuple
import urwid


class MenuEntry(NamedTuple):
    """Entry in the menu stack."""
    widget: urwid.Widget
    title: str
    on_exit: Optional[Callable[[], None]] = None


class MenuStack:
    """
    Manages a stack of menus for hierarchical navigation.
    
    Supports:
    - Push new submenus onto the stack
    - Pop back to previous menu
    - Query current menu state
    - Exit callbacks for cleanup
    """
    
    def __init__(self, on_change: Optional[Callable[[urwid.Widget], None]] = None):
        """
        Initialize empty menu stack.
        
        Args:
            on_change: Callback when active menu changes, receives new widget
        """
        self._stack: List[MenuEntry] = []
        self._on_change = on_change
    
    def push(self, widget: urwid.Widget, title: str = "", 
             on_exit: Optional[Callable[[], None]] = None):
        """
        Push a new menu onto the stack.
        
        Args:
            widget: The menu widget to display
            title: Human-readable title for breadcrumb display
            on_exit: Optional callback when this menu is popped
        """
        entry = MenuEntry(widget=widget, title=title, on_exit=on_exit)
        self._stack.append(entry)
        
        if self._on_change:
            self._on_change(widget)
    
    def pop(self) -> Optional[urwid.Widget]:
        """
        Pop the current menu and return to previous.
        
        Returns:
            The previous menu widget, or None if stack is empty
        """
        if not self._stack:
            return None
        
        # Get the menu being removed
        removed = self._stack.pop()
        
        # Call exit callback if defined
        if removed.on_exit:
            try:
                removed.on_exit()
            except Exception:
                pass
        
        # Return previous menu if available
        if self._stack:
            current = self._stack[-1].widget
            if self._on_change:
                self._on_change(current)
            return current
        
        return None
    
    def current(self) -> Optional[urwid.Widget]:
        """Get the current (top) menu widget."""
        if self._stack:
            return self._stack[-1].widget
        return None
    
    def current_title(self) -> str:
        """Get the current menu title."""
        if self._stack:
            return self._stack[-1].title
        return ""
    
    def depth(self) -> int:
        """Get the current stack depth."""
        return len(self._stack)
    
    def breadcrumb(self, separator: str = " > ") -> str:
        """
        Get breadcrumb string showing navigation path.
        
        Returns:
            String like "Main > Settings > Advanced"
        """
        titles = [entry.title for entry in self._stack if entry.title]
        return separator.join(titles)
    
    def can_go_back(self) -> bool:
        """Check if back navigation is possible."""
        return len(self._stack) > 1
    
    def clear(self):
        """Clear the entire stack, calling all exit callbacks."""
        while self._stack:
            self.pop()
    
    def reset_to_root(self) -> Optional[urwid.Widget]:
        """
        Clear all but the first (root) menu.
        
        Returns:
            The root menu widget
        """
        while len(self._stack) > 1:
            self.pop()
        
        return self.current()


class SubMenuBuilder:
    """Helper class for building submenu widgets with consistent styling."""
    
    @staticmethod
    def create_list_menu(
        title: str,
        items: List[dict],
        on_select: Callable[[Any], None],
        on_back: Optional[Callable[[], None]] = None,
        footer_text: str = "↑/↓ Navigate • Enter Select • Esc Back"
    ) -> urwid.Widget:
        """
        Create a standard list-style submenu.
        
        Args:
            title: Menu title
            items: List of dicts with 'label' and 'value' keys
            on_select: Callback when item selected, receives item value
            on_back: Callback for back button/Esc
            footer_text: Help text at bottom
            
        Returns:
            urwid Widget for the submenu
        """
        walker = urwid.SimpleFocusListWalker([])
        
        # Title
        walker.append(urwid.Text(("title", f" {title} "), align="center"))
        walker.append(urwid.Divider("═"))
        walker.append(urwid.Divider(" "))
        
        # Menu items
        first_focus = None
        for item in items:
            label = item.get("label", str(item.get("value", "")))
            value = item.get("value", label)
            
            btn = urwid.Button(label)
            urwid.connect_signal(btn, "click", lambda b, v=value: on_select(v))
            walker.append(urwid.AttrMap(btn, None, focus_map="highlight"))
            
            if first_focus is None:
                first_focus = len(walker) - 1
        
        # Back button if callback provided
        if on_back:
            walker.append(urwid.Divider(" "))
            back_btn = urwid.Button("← Back")
            urwid.connect_signal(back_btn, "click", lambda b: on_back())
            walker.append(urwid.AttrMap(back_btn, None, focus_map="highlight"))
        
        # Footer
        walker.append(urwid.Divider(" "))
        walker.append(urwid.AttrMap(
            urwid.Text(footer_text, align="center"),
            "status"
        ))
        
        # Set focus to first item
        if first_focus is not None:
            try:
                walker.set_focus(first_focus)
            except Exception:
                pass
        
        return urwid.ListBox(walker)


if __name__ == "__main__":
    print("MenuStack module loaded successfully")
    
    # Quick test
    stack = MenuStack()
    
    # Simulate pushing menus
    stack.push(urwid.Text("Root Menu"), "Main")
    stack.push(urwid.Text("Settings"), "Settings")
    stack.push(urwid.Text("Advanced"), "Advanced")
    
    print(f"Depth: {stack.depth()}")
    print(f"Breadcrumb: {stack.breadcrumb()}")
    print(f"Can go back: {stack.can_go_back()}")
    
    # Pop back
    stack.pop()
    print(f"After pop - Breadcrumb: {stack.breadcrumb()}")
