"""
Gradient Background System for Demoscene-style Effects

Implements animated color gradients with copper bar sweeping effects,
plasma patterns, and wave animations inspired by 80s/90s demoscene.

Supports patterns:
- wave_sine: Smooth sinusoidal wave motion
- wave_triangle: Linear ping-pong motion
- wave_sawtooth: One-direction sweep with reset
- plasma: Multiple overlapping sine waves (classic demoscene)
- radial: Concentric rings from center
- diagonal: Angled sweep at configurable angle
"""

import math
import random
import shutil
from typing import List, Dict, Any, Optional, Tuple
import urwid


# Basic urwid colors for gradient construction (16 color palette)
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

# Color "brightness" order for interpolation hints
COLOR_BRIGHTNESS = {
    "black": 0,
    "dark blue": 1,
    "dark red": 1,
    "dark green": 1,
    "dark magenta": 1,
    "dark cyan": 2,
    "brown": 2,
    "dark gray": 3,
    "light gray": 5,
    "light blue": 6,
    "light red": 6,
    "light green": 6,
    "light magenta": 6,
    "light cyan": 7,
    "yellow": 8,
    "white": 9,
}


class GradientRenderer:
    """
    Renders animated gradient backgrounds with sweep effects.

    Supports:
    - Vertical/horizontal/diagonal sweep
    - Sine/triangle/sawtooth wave patterns
    - Plasma effect (overlapping waves)
    - Radial rings from center
    - Phase shift for cascade effects
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize gradient renderer from config dict.

        Config keys:
            colors: List of color names (urwid-compatible)
            pattern: "wave_sine" | "wave_triangle" | "wave_sawtooth" | "plasma" | "radial" | "raindrops" | "static"
            direction: "vertical" | "horizontal" | "diagonal" | "diagonal_inv" | "radial"
            angle: Degrees for diagonal direction (0-360)
            speed: Seconds per animation frame (0.05-1.0)
            step_size: How much to advance per frame (0.5-3.0)
            band_height: Number of lines per color band
            wave_amplitude: Intensity of wave effect (0.5-5.0)
            wave_frequency: Periods per screen height (0.5-3.0)
            phase_shift: Phase offset per line for cascade effect (0-0.5)
            color_spread: How much to "stretch" colors (0.5-3.0)
            smoothness: Interpolation steps between colors (1-5)
            drop_count: Number of raindrops for "raindrops" pattern (1-20)
            drop_speed: How fast drops expand (0.5-3.0)
            drop_lifetime: How long drops last in frames (10-100)
            
            # New pattern configs:
            aurora_waves: Number of aurora curtain waves (2-6)
            star_count: Number of stars for starfield (20-100)
            star_speed: Speed of stars moving toward viewer (0.5-3.0)
            blob_count: Number of lava blobs (3-10)
            bar_count: Number of spectrum bars (8-32)
            pulse_bpm: Heartbeat speed in BPM (40-180)
        """
        self.colors = config.get("colors", ["dark blue", "light cyan", "white"])
        self.pattern = config.get("pattern", "wave_sine")
        self.direction = config.get("direction", "vertical")
        self.angle = float(config.get("angle", 45))
        self.speed = float(config.get("speed", 0.12))
        self.step_size = float(config.get("step_size", 1.0))
        self.band_height = int(config.get("band_height", 3))
        self.wave_amplitude = float(config.get("wave_amplitude", 1.5))
        self.wave_frequency = float(config.get("wave_frequency", 1.0))
        self.phase_shift = float(config.get("phase_shift", 0.05))
        self.color_spread = float(config.get("color_spread", 1.0))
        self.smoothness = int(config.get("smoothness", 1))
        self.fg_color = config.get("fg", "white")
        
        # Raindrops-specific config
        self.drop_count = int(config.get("drop_count", 5))
        self.drop_speed = float(config.get("drop_speed", 1.5))
        self.drop_lifetime = int(config.get("drop_lifetime", 40))
        
        # Aurora config
        self.aurora_waves = int(config.get("aurora_waves", 3))
        
        # Starfield config
        self.star_count = int(config.get("star_count", 50))
        self.star_speed = float(config.get("star_speed", 1.5))
        
        # Lava lamp config
        self.blob_count = int(config.get("blob_count", 5))
        
        # Spectrum config
        self.bar_count = int(config.get("bar_count", 16))
        
        # Heartbeat config
        self.pulse_bpm = int(config.get("pulse_bpm", 60))

        # Animation state
        self.time = 0.0
        self.frame_count = 0
        
        # Raindrops state - list of (x, y, birth_frame) tuples
        self._drops: List[Tuple[float, float, int]] = []
        self._drop_rng = random.Random(42)
        
        # Starfield state - list of (x, y, z) tuples (z = depth)
        self._stars: List[List[float]] = []
        self._star_rng = random.Random(123)
        self._init_stars()
        
        # Lava lamp state - list of (x, y, size, speed, color_idx) 
        self._blobs: List[List[float]] = []
        self._blob_rng = random.Random(456)
        self._init_blobs()
        
        # Spectrum state - current bar heights
        self._bar_heights: List[float] = [0.0] * self.bar_count
        self._bar_targets: List[float] = [0.0] * self.bar_count
        self._spectrum_rng = random.Random(789)

        # Build color cycle for seamless looping
        self._build_color_cycle()
    
    def _init_stars(self):
        """Initialize starfield with random star positions."""
        self._stars = []
        for _ in range(self.star_count):
            x = self._star_rng.uniform(-1, 1)
            y = self._star_rng.uniform(-1, 1)
            z = self._star_rng.uniform(0.1, 1.0)  # Depth
            self._stars.append([x, y, z])
    
    def _init_blobs(self):
        """Initialize lava lamp blobs."""
        self._blobs = []
        for i in range(self.blob_count):
            x = self._blob_rng.uniform(0.1, 0.9)
            y = self._blob_rng.uniform(0, 1)
            size = self._blob_rng.uniform(0.1, 0.25)
            speed = self._blob_rng.uniform(0.005, 0.015)
            color_idx = i % max(len(self.colors), 1)
            self._blobs.append([x, y, size, speed, color_idx])

    def _aurora_value(self, line: int, col: int, height: int, width: int) -> float:
        """
        Calculate aurora borealis effect - flowing vertical curtains.
        Multiple sine waves create wavy curtain effect.
        """
        # Normalize position
        x = col / max(width, 1)
        y = line / max(height, 1)
        
        value = 0.0
        # Multiple overlapping waves for curtain effect
        for i in range(self.aurora_waves):
            freq = (i + 1) * 2.0
            phase = self.time * (0.5 + i * 0.3)
            # Horizontal wave that affects vertical bands
            wave = math.sin(x * freq * math.pi + phase)
            # Add vertical gradient (stronger at top)
            intensity = (1 - y) * 0.7 + 0.3
            value += wave * intensity / self.aurora_waves
        
        return (value + 1) / 2  # Normalize to 0-1

    def _starfield_value(self, line: int, height: int, width: int) -> Tuple[float, int]:
        """
        Calculate starfield effect - count stars visible on this line.
        Returns (intensity, star_count) for the line.
        """
        y_norm = (line - height / 2) / (height / 2)  # -1 to 1
        
        star_count = 0
        total_brightness = 0.0
        
        for star in self._stars:
            sx, sy, sz = star
            if sz <= 0:
                continue
            # Project star position (perspective)
            proj_y = sy / sz
            # Check if star is on this line (with some tolerance)
            if abs(proj_y - y_norm) < 0.1 / sz:
                # Closer stars (smaller z) are brighter
                brightness = 1.0 - sz
                total_brightness += brightness
                star_count += 1
        
        return min(total_brightness, 1.0), star_count

    def _lava_value(self, line: int, col: int, height: int, width: int) -> Tuple[float, int]:
        """
        Calculate lava lamp effect - overlapping circular blobs.
        Returns (intensity, dominant_blob_color_idx).
        """
        x = col / max(width, 1)
        y = line / max(height, 1)
        
        total_intensity = 0.0
        dominant_color = 0
        max_contribution = 0.0
        
        for blob in self._blobs:
            bx, by, size, speed, color_idx = blob
            # Distance from blob center
            dx = x - bx
            dy = (y - by) * 0.5  # Adjust for aspect ratio
            dist = math.sqrt(dx * dx + dy * dy)
            
            # Blob has soft edges
            if dist < size:
                intensity = 1.0 - (dist / size)
                total_intensity += intensity
                if intensity > max_contribution:
                    max_contribution = intensity
                    dominant_color = int(color_idx)
        
        return min(total_intensity, 1.0), dominant_color

    def _spectrum_value(self, line: int, bar_idx: int, height: int) -> float:
        """
        Calculate spectrum analyzer bar height for a given bar.
        """
        if bar_idx >= len(self._bar_heights):
            return 0.0
        
        bar_height = self._bar_heights[bar_idx]
        line_pos = 1.0 - (line / max(height, 1))  # Flip so bars grow up
        
        # Return 1 if line is within bar height, 0 otherwise
        return 1.0 if line_pos <= bar_height else 0.0

    def _heartbeat_value(self, line: int, height: int, width: int) -> float:
        """
        Calculate heartbeat/breathing pulse effect.
        Concentric rings that expand from center with pulse timing.
        """
        # Calculate pulse phase based on BPM
        pulse_period = 60.0 / self.pulse_bpm  # Seconds per beat
        pulse_phase = (self.time / pulse_period) % 1.0
        
        # Create expanding ring effect
        center_y = height / 2
        dy = abs(line - center_y) / max(height / 2, 1)
        
        # Ring expands during pulse
        ring_radius = pulse_phase * 1.5
        ring_width = 0.3
        
        # Distance from current ring
        dist_from_ring = abs(dy - ring_radius)
        
        if dist_from_ring < ring_width:
            # Fade based on distance from ring edge
            intensity = 1.0 - (dist_from_ring / ring_width)
            # Also fade based on age of pulse
            fade = 1.0 - pulse_phase
            return intensity * fade
        
        return 0.0

    def _update_stars(self):
        """Move stars toward viewer (decreasing z)."""
        for star in self._stars:
            star[2] -= self.star_speed * 0.02
            if star[2] <= 0:
                # Reset star to back
                star[0] = self._star_rng.uniform(-1, 1)
                star[1] = self._star_rng.uniform(-1, 1)
                star[2] = 1.0

    def _update_blobs(self):
        """Move blobs upward, reset when they reach top."""
        for blob in self._blobs:
            blob[1] -= blob[3]  # Move up
            if blob[1] < -blob[2]:  # Past top
                blob[1] = 1.0 + blob[2]  # Reset to bottom
                blob[0] = self._blob_rng.uniform(0.2, 0.8)  # New x position

    def _update_spectrum(self):
        """Update spectrum bar heights with smooth animation."""
        for i in range(len(self._bar_heights)):
            # Occasionally set new target
            if self._spectrum_rng.random() < 0.2:
                self._bar_targets[i] = self._spectrum_rng.uniform(0.1, 1.0)
            
            # Smooth interpolation toward target
            diff = self._bar_targets[i] - self._bar_heights[i]
            self._bar_heights[i] += diff * 0.3
            
            # Decay
            self._bar_targets[i] *= 0.95

    def _build_color_cycle(self):
        """
        Build extended color list for seamless gradient animation.
        Creates a ping-pong pattern with optional smoothness expansion.
        """
        if len(self.colors) < 2:
            self.colors = ["dark blue", "light cyan"]

        # Expand colors based on smoothness
        expanded = []
        for i, color in enumerate(self.colors):
            expanded.append(color)
            # Add intermediate duplicates for smoother transitions
            if self.smoothness > 1 and i < len(self.colors) - 1:
                for _ in range(self.smoothness - 1):
                    expanded.append(color)

        # Create ping-pong: [A, B, C, D, C, B] for smooth loop
        if len(expanded) > 2:
            self.color_cycle = list(expanded) + list(reversed(expanded[1:-1]))
        else:
            self.color_cycle = list(expanded)

        if not self.color_cycle:
            self.color_cycle = self.colors

    def _wave_value(self, position: float, time_offset: float = 0) -> float:
        """
        Calculate wave value at position with time offset.
        Returns value in range [0, 1] for color indexing.
        """
        t = self.time + time_offset
        freq = self.wave_frequency * 2 * math.pi
        amp = self.wave_amplitude

        if self.pattern == "wave_sine":
            # Smooth sinusoidal wave
            value = math.sin(position * freq + t) * amp
            return (value + amp) / (2 * amp)  # Normalize to [0, 1]

        elif self.pattern == "wave_triangle":
            # Linear ping-pong (triangle wave)
            phase = (position * self.wave_frequency + t) % 2.0
            if phase < 1.0:
                return phase
            else:
                return 2.0 - phase

        elif self.pattern == "wave_sawtooth":
            # One-direction sweep with reset
            return (position * self.wave_frequency + t) % 1.0

        elif self.pattern == "plasma":
            # Classic demoscene plasma: sum of multiple sine waves
            v1 = math.sin(position * freq + t)
            v2 = math.sin(position * freq * 0.5 + t * 1.5)
            v3 = math.sin((position + time_offset * 0.1) * freq * 0.7 + t * 0.8)
            value = (v1 + v2 + v3) / 3.0 * amp
            return (value + amp) / (2 * amp)

        else:
            # Static or unknown - just use position
            return position % 1.0

    def _radial_distance(self, line: int, col: int, height: int, width: int) -> float:
        """Calculate normalized distance from center for radial patterns."""
        center_y = height / 2
        center_x = width / 2
        dy = (line - center_y) / max(height, 1)
        dx = (col - center_x) / max(width, 1)
        dist = math.sqrt(dx * dx + dy * dy)
        return min(dist * 2, 1.0)  # Normalize

    def _diagonal_position(self, line: int, col: int, height: int, width: int) -> float:
        """Calculate position along diagonal axis."""
        angle_rad = math.radians(self.angle)
        # Project point onto angled line
        nx = math.cos(angle_rad)
        ny = math.sin(angle_rad)
        # Normalize coordinates
        x = col / max(width, 1)
        y = line / max(height, 1)
        # Dot product gives position along diagonal
        return (x * nx + y * ny) % 1.0

    def _update_drops(self, height: int, width: int):
        """Update raindrops: remove old ones, spawn new ones if needed."""
        # Remove expired drops
        self._drops = [
            (x, y, birth) for x, y, birth in self._drops
            if (self.frame_count - birth) < self.drop_lifetime
        ]
        
        # Spawn new drops to maintain drop_count
        while len(self._drops) < self.drop_count:
            x = self._drop_rng.random()  # 0-1 normalized x position
            y = self._drop_rng.random()  # 0-1 normalized y position
            self._drops.append((x, y, self.frame_count))

    def _raindrops_value(self, line: int, col: int, height: int, width: int) -> float:
        """
        Calculate color value based on distance from all active drops.
        Each drop creates expanding rings that overlap with other drops.
        """
        if not self._drops:
            return 0.0
        
        # Normalize position
        x = col / max(width, 1)
        y = line / max(height, 1)
        
        total_value = 0.0
        
        for drop_x, drop_y, birth_frame in self._drops:
            # Age of this drop (how much it has expanded)
            age = (self.frame_count - birth_frame) * self.drop_speed * 0.05
            
            # Distance from this drop
            dx = x - drop_x
            dy = (y - drop_y) * 0.5  # Adjust for terminal aspect ratio
            dist = math.sqrt(dx * dx + dy * dy)
            
            # Expanding ring effect - wave moves outward from drop center
            ring_pos = dist - age
            
            # Only show the wave front, with fade based on distance
            if ring_pos < 0:
                # Inside the ring - use sine wave for ripple effect
                ripple = math.sin(ring_pos * self.wave_frequency * 20) * 0.5 + 0.5
                # Fade intensity based on age and distance
                fade = max(0, 1 - (self.frame_count - birth_frame) / self.drop_lifetime)
                total_value += ripple * fade
            else:
                # Outside the ring - add small contribution for approaching wave
                if ring_pos < 0.1:
                    total_value += (0.1 - ring_pos) * 5
        
        # Normalize and clamp
        return min(total_value, 1.0)

    def get_line_colors(self, height: int, width: int = 80) -> List[Tuple[str, str]]:
        """
        Get (fg, bg) color tuple for each line of the display.

        Args:
            height: Number of lines to generate colors for
            width: Terminal width (for radial/diagonal calculations)

        Returns:
            List of (foreground, background) color tuples
        """
        cycle_len = len(self.color_cycle)
        if cycle_len == 0:
            return [(self.fg_color, "black")] * height

        colors = []
        
        # Special handling for raindrops pattern
        if self.pattern == "raindrops":
            self._update_drops(height, width)
            for line in range(height):
                # Calculate average raindrop value across the line
                total = 0.0
                samples = 5  # Sample multiple points per line
                for s in range(samples):
                    col = int((s + 0.5) * width / samples)
                    total += self._raindrops_value(line, col, height, width)
                wave_pos = (total / samples) % 1.0
                
                # Apply color spread
                wave_pos = (wave_pos * self.color_spread) % 1.0
                
                # Map to color index
                color_idx = int(wave_pos * cycle_len) % cycle_len
                bg = self.color_cycle[color_idx]
                colors.append((self.fg_color, bg))
            return colors
        
        # Aurora Borealis pattern
        if self.pattern == "aurora":
            for line in range(height):
                # Sample aurora value at line center
                wave_pos = self._aurora_value(line, width // 2, height, width)
                wave_pos = (wave_pos * self.color_spread) % 1.0
                color_idx = int(wave_pos * cycle_len) % cycle_len
                bg = self.color_cycle[color_idx]
                colors.append((self.fg_color, bg))
            return colors
        
        # Starfield warp pattern
        if self.pattern == "starfield":
            self._update_stars()
            for line in range(height):
                intensity, _ = self._starfield_value(line, height, width)
                if intensity > 0.1:
                    # Stars are bright (use later colors in cycle)
                    color_idx = int((1 - intensity) * cycle_len * 0.5) % cycle_len
                    # Make stars white/bright
                    bg = self.color_cycle[min(color_idx + cycle_len // 2, cycle_len - 1)]
                else:
                    # Background is dark
                    bg = self.color_cycle[0]
                colors.append((self.fg_color, bg))
            return colors
        
        # Lava lamp pattern
        if self.pattern == "lava":
            self._update_blobs()
            for line in range(height):
                # Sample multiple points per line for smoother blobs
                total_intensity = 0.0
                dominant_color = 0
                samples = 5
                for s in range(samples):
                    col = int((s + 0.5) * width / samples)
                    intensity, color_idx = self._lava_value(line, col, height, width)
                    total_intensity += intensity
                    if intensity > 0:
                        dominant_color = color_idx
                
                avg_intensity = total_intensity / samples
                if avg_intensity > 0.1:
                    # Inside a blob - use blob's color
                    bg = self.color_cycle[dominant_color % cycle_len]
                else:
                    # Background
                    bg = self.color_cycle[0]
                colors.append((self.fg_color, bg))
            return colors
        
        # Spectrum analyzer pattern
        if self.pattern == "spectrum":
            self._update_spectrum()
            for line in range(height):
                # Determine which bars are lit on this line
                lit_bars = 0
                total_bars = self.bar_count
                for bar_idx in range(total_bars):
                    if self._spectrum_value(line, bar_idx, height) > 0:
                        lit_bars += 1
                
                if lit_bars > 0:
                    # Color based on how many bars are active
                    color_idx = int((lit_bars / total_bars) * cycle_len) % cycle_len
                    bg = self.color_cycle[color_idx]
                else:
                    bg = self.color_cycle[0]
                colors.append((self.fg_color, bg))
            return colors
        
        # Heartbeat/breathing pattern
        if self.pattern == "heartbeat":
            for line in range(height):
                intensity = self._heartbeat_value(line, height, width)
                if intensity > 0.1:
                    color_idx = int(intensity * cycle_len) % cycle_len
                    bg = self.color_cycle[color_idx]
                else:
                    bg = self.color_cycle[0]
                colors.append((self.fg_color, bg))
            return colors

        for line in range(height):
            # Calculate base position based on direction
            if self.direction == "horizontal":
                # All lines same, animated horizontally
                base_pos = self.time % 1.0
            elif self.direction == "diagonal":
                # Use diagonal projection
                base_pos = self._diagonal_position(line, width // 2, height, width)
            elif self.pattern == "radial":
                # Radial distance from center
                base_pos = self._radial_distance(line, width // 2, height, width)
            else:
                # Vertical: position based on line
                base_pos = line / max(height, 1)

            # Apply wave pattern
            if self.pattern == "radial":
                # Radial uses distance + time for expanding rings
                wave_pos = (base_pos * self.wave_frequency + self.time) % 1.0
            else:
                # Apply phase shift for cascade effect
                phase_offset = line * self.phase_shift
                wave_pos = self._wave_value(base_pos, phase_offset)

            # Apply color spread
            wave_pos = (wave_pos * self.color_spread) % 1.0

            # Map to color index
            color_idx = int(wave_pos * cycle_len) % cycle_len
            bg = self.color_cycle[color_idx]
            colors.append((self.fg_color, bg))

        return colors

    def advance_frame(self):
        """Advance animation by one frame."""
        self.frame_count += 1
        self.time += self.step_size * 0.1  # Scale step_size

    def get_speed(self) -> float:
        """Get animation speed in seconds."""
        return self.speed

    def reset(self):
        """Reset animation to initial state."""
        self.time = 0.0
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
        # Get terminal width if available
        try:
            width = shutil.get_terminal_size().columns
        except Exception:
            width = 80

        colors = self.renderer.get_line_colors(height, width)

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
        self.pile.contents = [(w, ("pack", None)) for w in widgets]

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
        preset_type: "copper", "rainbow", "fire", "ocean", "plasma"

    Returns:
        Configuration dict for GradientRenderer
    """
    presets = {
        "copper": {
            "name": name,
            "mode": "gradient",
            "pattern": "wave_sine",
            "direction": "vertical",
            "colors": [
                "black",
                "dark blue",
                "dark cyan",
                "light cyan",
                "white",
                "light cyan",
                "dark cyan",
                "dark blue",
            ],
            "speed": 0.12,
            "step_size": 0.8,
            "band_height": 4,
            "wave_amplitude": 1.5,
            "phase_shift": 0.03,
            "fg": "white",
        },
        "rainbow": {
            "name": name,
            "mode": "gradient",
            "pattern": "wave_sine",
            "direction": "vertical",
            "colors": [
                "dark red",
                "brown",
                "yellow",
                "light green",
                "dark cyan",
                "dark blue",
                "dark magenta",
            ],
            "speed": 0.1,
            "step_size": 0.6,
            "band_height": 3,
            "wave_amplitude": 1.2,
            "phase_shift": 0.02,
            "fg": "white",
        },
        "fire": {
            "name": name,
            "mode": "gradient",
            "pattern": "wave_sine",
            "direction": "vertical",
            "colors": ["black", "dark red", "light red", "yellow", "white"],
            "speed": 0.08,
            "step_size": 1.2,
            "band_height": 5,
            "wave_amplitude": 2.0,
            "phase_shift": 0.04,
            "fg": "black",
        },
        "ocean": {
            "name": name,
            "mode": "gradient",
            "pattern": "wave_sine",
            "direction": "vertical",
            "colors": ["black", "dark blue", "dark cyan", "light cyan", "white"],
            "speed": 0.15,
            "step_size": 0.5,
            "band_height": 6,
            "wave_amplitude": 1.0,
            "phase_shift": 0.02,
            "fg": "white",
        },
        "plasma": {
            "name": name,
            "mode": "gradient",
            "pattern": "plasma",
            "direction": "vertical",
            "colors": [
                "dark magenta",
                "dark blue",
                "dark cyan",
                "light cyan",
                "yellow",
                "light red",
                "dark magenta",
            ],
            "speed": 0.08,
            "step_size": 1.0,
            "wave_amplitude": 1.5,
            "wave_frequency": 1.5,
            "phase_shift": 0.08,
            "color_spread": 1.5,
            "fg": "white",
        },
    }

    return presets.get(preset_type, presets["copper"])


if __name__ == "__main__":
    # Quick test
    print("=" * 60)
    print("Gradient Background System Test")
    print("=" * 60)

    for preset_name in ["copper", "plasma", "fire"]:
        config = create_gradient_preset(f"Test {preset_name}", preset_name)
        renderer = GradientRenderer(config)

        print(f"\n{preset_name.upper()} Preset:")
        print(f"  Pattern: {renderer.pattern}")
        print(f"  Speed: {renderer.get_speed()}s")
        print(f"  Step size: {renderer.step_size}")
        print(f"  Color cycle length: {len(renderer.color_cycle)}")

        print("  Colors (first 10 lines):")
        colors = renderer.get_line_colors(10)
        for i, (fg, bg) in enumerate(colors):
            print(f"    Line {i:2d}: {bg}")

        # Advance a few frames
        for _ in range(5):
            renderer.advance_frame()

        print("  After 5 frames (first 5 lines):")
        colors = renderer.get_line_colors(5)
        for i, (fg, bg) in enumerate(colors):
            print(f"    Line {i:2d}: {bg}")
