"""
YTBMusic Animation Loader

Loads ASCII art animations from the animations/ folder.
Animations have YAML frontmatter (fps, dimensions) and FRAME_N: sections.
"""

import yaml
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import urwid


import shutil

class AnimationLoader:
    """Loads and plays ASCII animations."""

    def __init__(self, animations_dir: str = "animations"):
        self.animations_dir = Path(animations_dir)
        self.metadata: Dict = {}
        self.frames: List[List[str]] = []
        self.current_frame: int = 0
        self.fps: int = 8

    def load(self, animation_path: str) -> Tuple[Dict, List[List[str]]]:
        """
        Load an animation file.

        Args:
            animation_path: Path to animation .txt file

        Returns:
            Tuple of (metadata dict, list of frames where each frame is a list of lines)
        """
        path = Path(animation_path)
        content = path.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        self.metadata = self._parse_frontmatter(content)
        self.fps = self.metadata.get("fps", 8)

        # Parse frames
        self.frames = self._parse_frames(content)

        # Ensure all frames have consistent dimensions (height only)
        # We don't pad width anymore, we let the widget tile it.
        target_height = self.metadata.get("height", 3)
        self.frames = [
            self._normalize_frame(frame, target_height)
            for frame in self.frames
        ]

        return self.metadata, self.frames

    def _parse_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from animation content."""
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(pattern, content, re.DOTALL)

        if match:
            try:
                return yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                return {}
        return {}

    def _parse_frames(self, content: str) -> List[List[str]]:
        """Parse animation frames from content."""
        frames = []

        # Remove frontmatter
        content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)

        # Split by FRAME_ markers
        frame_pattern = r"FRAME_\d+:\s*\n(.*?)(?=FRAME_\d+:|$)"
        matches = re.findall(frame_pattern, content, re.DOTALL)

        for frame_content in matches:
            lines = frame_content.rstrip().split("\n")
            if lines and any(line.strip() for line in lines):
                frames.append(lines)

        return frames

    def _normalize_frame(self, frame: List[str], height: int) -> List[str]:
        """Normalize frame height (no width padding)."""
        # Pad or trim lines to target width
        normalized = []
        for line in frame[:height]:
            normalized.append(line.rstrip())

        # Add empty lines if frame is shorter than target height
        while len(normalized) < height:
            normalized.append("")

        return normalized

    def get_frame(self, index: int) -> List[str]:
        """Get a specific frame by index."""
        if not self.frames:
            return []
        return self.frames[index % len(self.frames)]

    def next_frame(self) -> List[str]:
        """Get the next frame and advance the counter."""
        if not self.frames:
            return []
        frame = self.frames[self.current_frame % len(self.frames)]
        self.current_frame += 1
        return frame

    def reset(self):
        """Reset animation to first frame."""
        self.current_frame = 0

    def get_frame_interval(self) -> float:
        """Get the time interval between frames in seconds."""
        return 1.0 / self.fps

    @staticmethod
    def list_available_animations(animations_dir: str = "animations") -> List[str]:
        """List all available animation files."""
        path = Path(animations_dir)
        if not path.exists():
            return []

        animations = []
        for file in sorted(path.glob("*.txt")):
            animations.append(file.stem)
        return animations

    def get_metadata(self, animation_name: str) -> Optional[Dict]:
        """Get metadata for an animation without fully loading it."""
        path = self.animations_dir / f"{animation_name}.txt"
        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            return self._parse_frontmatter(content)
        except Exception:
            return None


class AnimationWidget(urwid.WidgetWrap):
    """Widget that displays animated ASCII art."""

    def __init__(self, height: int = 3):
        self.height = height
        self.loader = AnimationLoader()
        self.lines: List[urwid.Text] = [urwid.Text("", align="left", wrap="clip") for _ in range(height)]
        self.pile = urwid.Pile(self.lines)
        self.box = urwid.LineBox(self.pile, title="♪ Animation")
        super().__init__(self.box)

        self._animation_loaded = False
        self._current_animation = None

    def load_animation(self, animation_name: str) -> bool:
        """Load an animation by name."""
        path = Path("animations") / f"{animation_name}.txt"
        if not path.exists():
            return False

        try:
            self.loader.load(str(path))
            self._animation_loaded = True
            self._current_animation = animation_name
            self._update_title()
            return True
        except Exception:
            return False

    def _update_title(self):
        """Update the box title with animation name."""
        name = self.loader.metadata.get("name", self._current_animation or "Animation")
        self.box.set_title(f"♪ {name}")

    def advance_frame(self):
        """Advance to the next frame and tile it to fill width."""
        if not self._animation_loaded:
            return

        frame = self.loader.next_frame()
        cols, _ = shutil.get_terminal_size()
        # Adjust for LineBox borders (2 chars)
        width = max(1, cols - 2)

        for i, line in enumerate(frame[: self.height]):
            if i < len(self.lines):
                # Tile the line to fill the width
                if not line:
                    tiled_line = " " * width
                else:
                    repeats = (width // len(line)) + 1
                    tiled_line = (line * repeats)[:width]
                
                self.lines[i].set_text(tiled_line)

    def get_interval(self) -> float:
        """Get the animation frame interval."""
        return self.loader.get_frame_interval()

    def is_loaded(self) -> bool:
        """Check if an animation is currently loaded."""
        return self._animation_loaded

    def get_current_animation(self) -> Optional[str]:
        """Get the name of the currently loaded animation."""
        return self._current_animation


if __name__ == "__main__":
    # Test the animation loader
    import sys

    print("Available animations:")
    for anim in AnimationLoader.list_available_animations():
        print(f"  - {anim}")

    if len(sys.argv) > 1:
        anim_name = sys.argv[1]
        loader = AnimationLoader()
        path = Path("animations") / f"{anim_name}.txt"

        if path.exists():
            meta, frames = loader.load(str(path))
            print(f"\nLoaded: {meta.get('name', anim_name)}")
            print(f"FPS: {meta.get('fps', 8)}")
            print(f"Frames: {len(frames)}")
            print(f"Dimensions: {meta.get('width', '?')}x{meta.get('height', '?')}")

            print("\nFrame 1:")
            for line in frames[0]:
                print(f"  {line}")
        else:
            print(f"\nAnimation not found: {anim_name}")
