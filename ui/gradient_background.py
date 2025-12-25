"""
Gradient Background System for Demoscene-style Effects

Implements animated color gradients with copper bar sweeping effects
inspired by 80s/90s demoscene on Commodore/Amiga.
"""

import shutil
from typing import List, Dict, Any, Optional, Tuple
import urwid


# Basic urwid colors for gradient construction
GRADIENT_COLORS = [
    "black",
    "dark blue",
    "dark cyan",
    "dark green",
    "dark magenta",
    "dark red",
    "brown",
    "light gray",
    "dark gray",
    "light blue",
    "light cyan",
    "light green",
    "light magenta",
    "light red",
    "yellow",
    "white",
]


class GradientRenderer:
    """
    Renders animated gradient backgrounds with sweep effects.
    
    Supports:
    - Vertical sweep (colors move up/down)
    - Horizontal sweep (colors move left/right) 
    - Static gradient (no animation)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize gradient renderer from config dict.
        
        Config keys:
            colors: List of color names (urwid-compatible)
            direction: "vertical" | "horizontal" | "static"
            speed: Seconds per animation frame (0.1-1.0)
            band_height: Number of lines per color band
        """
        self.colors = config.get("colors", ["dark blue", "light cyan", "white"])
        self.direction = config.get("direction", "vertical")
        self.speed = float(config.get("speed", 0.15))
        self.band_height = int(config.get("band_height", 3))
        self.fg_color = config.get("fg", "white")
        
        # Animation state
        self.offset = 0
        self.frame_count = 0
        
        # Build color cycle for seamless looping
        self._build_color_cycle()
    
    def _build_color_cycle(self):
        """
        Build extended color list for seamless gradient animation.
        Creates a ping-pong pattern: A-B-C-B-A for smooth looping.
        """
        if len(self.colors) < 2:
            self.colors = ["dark blue", "light cyan"]
        
        # Create ping-pong: [A, B, C, D, C, B] for smooth loop
        self.color_cycle = list(self.colors) + list(reversed(self.colors[1:-1]))
        if not self.color_cycle:
            self.color_cycle = self.colors
    
    def get_line_colors(self, height: int) -> List[Tuple[str, str]]:
        """
        Get (fg, bg) color tuple for each line of the display.
        
        Args:
            height: Number of lines to generate colors for
            
        Returns:
            List of (foreground, background) color tuples
        """
        if self.direction == "horizontal":
            # Horizontal: all lines same color, animated left-right
            # For terminal, we simulate with a single cycling color
            idx = self.offset % len(self.color_cycle)
            bg = self.color_cycle[idx]
            return [(self.fg_color, bg)] * height
        
        # Vertical gradient: each line gets a different color
        colors = []
        cycle_len = len(self.color_cycle)
        
        for line in range(height):
            # Calculate which color band this line belongs to
            band_idx = line // self.band_height
            # Apply animation offset
            color_idx = (band_idx + self.offset) % cycle_len
            bg = self.color_cycle[color_idx]
            colors.append((self.fg_color, bg))
        
        return colors
    
    def advance_frame(self):
        """Advance animation by one frame."""
        self.frame_count += 1
        self.offset = (self.offset + 1) % len(self.color_cycle)
    
    def get_speed(self) -> float:
        """Get animation speed in seconds."""
        return self.speed
    
    def reset(self):
        """Reset animation to initial state."""
        self.offset = 0
        self.frame_count = 0


class GradientWidget(urwid.WidgetWrap):
    """
    Widget that displays content with animated gradient background.
    
    Wraps a text content widget and applies per-line background colors.
    """
    
    def __init__(self, content_widget: urwid.Widget, renderer: GradientRenderer):
        self.content = content_widget
        self.renderer = renderer
        self._palette_registered = False
        self._line_widgets: List[urwid.AttrMap] = []
        
        # Create a pile that will hold our colored lines
        self.pile = urwid.Pile([])
        super().__init__(self.pile)
    
    def update_content(self, text_lines: List[str], loop: urwid.MainLoop = None):
        """
        Update the displayed content with gradient background.
        
        Args:
            text_lines: List of text lines to display
            loop: urwid MainLoop for registering palette entries
        """
        height = len(text_lines)
        colors = self.renderer.get_line_colors(height)
        
        # Register palette entries if we have a loop
        if loop and not self._palette_registered:
            self._register_palette(loop, colors)
            self._palette_registered = True
        
        # Create widgets for each line with its background color
        widgets = []
        for i, (line, (fg, bg)) in enumerate(zip(text_lines, colors)):
            text_widget = urwid.Text(line)
            palette_name = f"gradient_{i % 50}"  # Limit palette entries
            
            # Register this specific color combo
            if loop:
                try:
                    loop.screen.register_palette_entry(palette_name, fg, bg)
                except Exception:
                    pass
            
            attr_widget = urwid.AttrMap(text_widget, palette_name)
            widgets.append(attr_widget)
        
        # Update pile contents
        self.pile.contents = [(w, ('pack', None)) for w in widgets]
    
    def _register_palette(self, loop: urwid.MainLoop, colors: List[Tuple[str, str]]):
        """Register palette entries for gradient colors."""
        for i, (fg, bg) in enumerate(colors[:50]):  # Limit to 50 entries
            try:
                loop.screen.register_palette_entry(f"gradient_{i}", fg, bg)
            except Exception:
                pass
    
    def advance_animation(self):
        """Advance the gradient animation."""
        self.renderer.advance_frame()


def create_gradient_preset(name: str, preset_type: str = "copper") -> Dict[str, Any]:
    """
    Create a gradient preset configuration.
    
    Args:
        name: Preset name
        preset_type: "copper", "rainbow", "fire", "ocean"
        
    Returns:
        Configuration dict for GradientRenderer
    """
    presets = {
        "copper": {
            "name": name,
            "mode": "gradient",
            "direction": "vertical",
            "colors": [
                "black", "dark blue", "dark cyan", "light cyan",
                "white", "light cyan", "dark cyan", "dark blue"
            ],
            "speed": 0.12,
            "band_height": 4,
            "fg": "white"
        },
        "rainbow": {
            "name": name,
            "mode": "gradient",
            "direction": "vertical",
            "colors": [
                "dark red", "brown", "yellow", "light green",
                "dark cyan", "dark blue", "dark magenta"
            ],
            "speed": 0.1,
            "band_height": 3,
            "fg": "white"
        },
        "fire": {
            "name": name,
            "mode": "gradient",
            "direction": "vertical",
            "colors": [
                "black", "dark red", "light red", "yellow", "white"
            ],
            "speed": 0.08,
            "band_height": 5,
            "fg": "black"
        },
        "ocean": {
            "name": name,
            "mode": "gradient",
            "direction": "vertical",
            "colors": [
                "black", "dark blue", "dark cyan", "light cyan", "white"
            ],
            "speed": 0.2,
            "band_height": 6,
            "fg": "white"
        }
    }
    
    return presets.get(preset_type, presets["copper"])


if __name__ == "__main__":
    # Quick test
    config = create_gradient_preset("Test Copper", "copper")
    renderer = GradientRenderer(config)
    
    print("Gradient Colors (first 20 lines):")
    colors = renderer.get_line_colors(20)
    for i, (fg, bg) in enumerate(colors):
        print(f"  Line {i:2d}: fg={fg:12s} bg={bg}")
    
    print(f"\nAnimation speed: {renderer.get_speed()}s")
    print(f"Color cycle length: {len(renderer.color_cycle)}")
