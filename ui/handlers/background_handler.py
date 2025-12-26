"""
Background Handler Mixin

Handles background colors, gradients, cycling, and demoscene effects.
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui.gradient_background import GradientRenderer
    from ui.background_loader import BackgroundLoader

logger = logging.getLogger(__name__)

# Import PAD_HEIGHT from main constants
PAD_HEIGHT = 88


class BackgroundMixin:
    """
    Mixin providing background-related functionality.
    
    Requires the host class to have:
        - self.loop: urwid MainLoop
        - self.player_view: PlayerView instance
        - self.backgrounds: list of background names
        - self.current_background_idx: int
        - self.current_background_meta: dict or None
        - self.background_loader: BackgroundLoader
        - self._background_palette_name: str
        - self._background_alarm: alarm handle or None
        - self._background_cycle: list
        - self._background_cycle_idx: int
        - self._gradient_active: bool
        - self._gradient_alarm: alarm handle or None
        - self._gradient_renderer: GradientRenderer or None
        - self.status: StatusBar
        - self.log_activity(message, style): method
        - self._normalize_color(value): method
    """
    
    def _set_player_background(self, fg: str, bg: str):
        """Register and apply background palette for the player canvas only."""
        fg = self._normalize_color(fg)
        bg = self._normalize_color(bg)
        try:
            self.loop.screen.register_palette_entry(
                self._background_palette_name, fg, bg
            )
            logger.info(
                f"[BG] Applying palette {self._background_palette_name}: fg={fg} bg={bg}"
            )
            self.player_view.set_background_attr(self._background_palette_name)
            # Force immediate redraw to avoid stale colors
            try:
                self.player_view.force_redraw()
            except Exception:
                pass
            if self.loop:
                try:
                    self.loop.screen.clear()
                    self.loop.draw_screen()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to apply background palette: {e}")
            self.player_view.set_background_attr(None)

    def _cancel_background_cycle(self):
        """Cancel any active background cycling."""
        if self._background_alarm and self.loop:
            try:
                self.loop.remove_alarm(self._background_alarm)
            except Exception:
                pass
        self._background_alarm = None
        self._background_cycle = []
        self._background_cycle_idx = 0

    def _schedule_background_cycle(self, meta: Dict[str, Any]):
        """Schedule background color cycling based on metadata."""
        self._cancel_background_cycle()
        interval = float(meta.get("transition_sec") or 0)
        fg_default = meta.get("fg") or "white"
        colors: List[tuple] = []
        bg_main = meta.get("bg") or "black"
        colors.append((fg_default, bg_main))

        palette_list = meta.get("palette") or []
        if isinstance(palette_list, list):
            for item in palette_list:
                if not isinstance(item, dict):
                    continue
                bg_val = item.get("bg")
                fg_val = item.get("fg") or fg_default
                if bg_val:
                    colors.append((fg_val, bg_val))

        alt_bg = meta.get("alt_bg")
        if alt_bg:
            colors.append((fg_default, alt_bg))

        # Need at least 2 colors to cycle
        if interval <= 0 or len(colors) < 2:
            return

        self._background_cycle = colors
        self._background_cycle_idx = 0

        def advance(loop=None, data=None):
            if not self._background_cycle:
                return
            self._background_cycle_idx = (self._background_cycle_idx + 1) % len(
                self._background_cycle
            )
            fg, bg = self._background_cycle[self._background_cycle_idx]
            self._set_player_background(fg, bg)
            self._background_alarm = self.loop.set_alarm_in(interval, advance)

        self._background_alarm = self.loop.set_alarm_in(interval, advance)

    def _apply_background_by_idx(self, idx: int):
        """Apply background preset by index (safe if none available)."""
        from ui.background_loader import BackgroundLoader
        
        self._cancel_background_cycle()
        self._stop_gradient_animation()  # Stop any active gradient

        if not self.backgrounds:
            self.current_background_meta = None
            self.player_view.set_background_attr(None)
            return
        idx = idx % len(self.backgrounds)
        name = self.backgrounds[idx]
        try:
            meta, _ = self.background_loader.load(name)
        except Exception as e:
            logger.error(f"Failed to load background '{name}': {e}")
            return
        self.current_background_idx = idx
        self.current_background_meta = meta

        # Check if this is a gradient background (demoscene mode)
        if BackgroundLoader.is_gradient(meta):
            self._start_gradient_animation(meta)
            self.log_activity(f"🌈 Gradient: {meta.get('name') or name}", "info")
        else:
            # Standard solid/cycling background
            self._set_player_background(
                meta.get("fg") or "white", meta.get("bg") or "black"
            )
            self._schedule_background_cycle(meta)
            self.log_activity(f"Fondo: {meta.get('name') or name}", "info")

    def _start_gradient_animation(self, meta: Dict[str, Any]):
        """Start demoscene-style gradient animation."""
        from ui.gradient_background import GradientRenderer
        
        logger.info(f"[GRADIENT] Starting animation: {meta.get('name')}")
        self._gradient_renderer = GradientRenderer(meta)
        self._gradient_active = True
        # Start animation loop
        speed = self._gradient_renderer.get_speed()
        logger.info(f"[GRADIENT] Speed: {speed}s, pattern: {meta.get('pattern')}")
        self._gradient_alarm = self.loop.set_alarm_in(
            speed, self._gradient_animate_loop
        )
        # Apply initial gradient
        self._apply_gradient_colors()

    def _stop_gradient_animation(self):
        """Stop gradient animation if active."""
        self._gradient_active = False
        if hasattr(self, "_gradient_alarm") and self._gradient_alarm:
            try:
                self.loop.remove_alarm(self._gradient_alarm)
            except Exception:
                pass
        self._gradient_alarm = None
        self._gradient_renderer = None

    def _gradient_animate_loop(self, loop=None, data=None):
        """Animation loop for gradient backgrounds."""
        if not self._gradient_active or not self._gradient_renderer:
            logger.debug("[GRADIENT] Loop skipped: not active")
            return
        # Advance animation frame
        self._gradient_renderer.advance_frame()
        self._apply_gradient_colors()
        # Schedule next frame
        speed = self._gradient_renderer.get_speed()
        self._gradient_alarm = self.loop.set_alarm_in(
            speed, self._gradient_animate_loop
        )

    def _apply_gradient_colors(self):
        """Apply current gradient colors to the player view."""
        if not self._gradient_renderer:
            logger.warning("[GRADIENT] No renderer in _apply_gradient_colors")
            return
        
        # Get terminal size for proper gradient calculation
        try:
            width, height = self.player_view._compute_canvas_size()
        except Exception:
            width, height = 80, PAD_HEIGHT
        
        # Get colors for each line - this creates the sweep effect
        colors = self._gradient_renderer.get_line_colors(height, width)
        direction = self._gradient_renderer.direction
        logger.debug(f"[GRADIENT] Applying {len(colors)} colors, direction={direction}")
        
        # Use the new per-line gradient rendering for real sweep effect
        self.player_view.set_gradient_colors(colors, self.loop, direction)
        
        # Force redraw
        try:
            self.loop.draw_screen()
        except Exception:
            pass

    def _cycle_background(self, direction: int = 1):
        """Cycle through backgrounds in player mode."""
        if not self.backgrounds:
            self.status.set("No hay fondos disponibles")
            return
        self.current_background_idx = (self.current_background_idx + direction) % len(
            self.backgrounds
        )
        self._apply_background_by_idx(self.current_background_idx)
        name = self.backgrounds[self.current_background_idx]
        self.status.notify(f"Fondo: {name}")
