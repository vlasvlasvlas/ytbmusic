"""
Skin Loader - Optimized for 80x40 terminals
"""

import yaml
import re
from pathlib import Path
from typing import Dict, List, Tuple


# Fixed canvas size for small screens
CANVAS_WIDTH = 78
CANVAS_HEIGHT = 38


class SkinLoader:
    """Loads and renders ASCII skins safely for small terminals."""

    REQUIRED_PLACEHOLDERS = [
        "{{PREV}}",
        "{{PLAY}}",
        "{{NEXT}}",
        "{{VOL_DOWN}}",
        "{{VOL_UP}}",
        "{{QUIT}}",
    ]

    OPTIONAL_PLACEHOLDERS = [
        "{{TITLE}}",
        "{{ARTIST}}",
        "{{ALBUM}}",
        "{{TIME}}",
        "{{TIME_CURRENT}}",
        "{{TIME_TOTAL}}",
        "{{PROGRESS}}",
        "{{VOLUME}}",
        "{{STATUS}}",
        "{{NEXT_TRACK}}",
        "{{PLAYLIST}}",
        "{{TRACK_NUM}}",
        "{{SHUFFLE}}",
        "{{REPEAT}}",
    ]

    def __init__(self):
        self.metadata = {}
        self.content = ""
        self.lines = []
        self.is_animated = False

    def load(self, skin_path: str) -> Tuple[Dict, List[str]]:
        """Load and fit skin to 78x38 canvas."""
        path = Path(skin_path)
        if not path.exists():
            raise FileNotFoundError(f"Skin not found: {skin_path}")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        self.metadata, self.content = self._parse_frontmatter(content)
        self.is_animated = self.metadata.get("animated", False)

        # For now, ignore animation to keep it simple
        self.lines = self.content.split("\n")

        # Validate
        self._validate_placeholders()

        # Fit to canvas
        fitted = self._fit_to_canvas(self.lines, CANVAS_WIDTH, CANVAS_HEIGHT)

        return self.metadata, fitted

    def _parse_frontmatter(self, content: str) -> Tuple[Dict, str]:
        """Extract YAML frontmatter."""
        pattern = r"^---\n(.*?)\n---\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if match:
            frontmatter_str = match.group(1)
            body = match.group(2)
            try:
                metadata = yaml.safe_load(frontmatter_str) or {}
                return metadata, body
            except:
                return {}, body

        return {"name": "Unknown", "author": "Unknown"}, content

    def _validate_placeholders(self):
        """Check required placeholders exist."""
        content_str = "\n".join(self.lines)
        missing = [p for p in self.REQUIRED_PLACEHOLDERS if p not in content_str]
        if missing:
            raise ValueError(f"Missing placeholders: {', '.join(missing)}")

    def _fit_to_canvas(self, lines: List[str], width: int, height: int) -> List[str]:
        """Fit lines to exact canvas size."""
        fitted = []

        for line in lines[:height]:  # Take only first 'height' lines
            # Remove trailing newlines
            line = line.rstrip("\n")

            # Truncate if too long
            if len(line) > width:
                line = line[:width]

            # Pad if too short
            if len(line) < width:
                line = line + (" " * (width - len(line)))

            fitted.append(line)

        # Add empty lines if needed
        while len(fitted) < height:
            fitted.append(" " * width)

        return fitted

    def render(
        self,
        lines: List[str],
        context: Dict[str, str],
        pad_width: int = CANVAS_WIDTH,
        pad_height: int = CANVAS_HEIGHT,
    ) -> List[str]:
        """Replace placeholders and ensure fixed size."""
        rendered = []
        all_placeholders = self.REQUIRED_PLACEHOLDERS + self.OPTIONAL_PLACEHOLDERS

        for line in lines:
            rendered_line = line

            # Replace each placeholder
            for placeholder in all_placeholders:
                if placeholder in rendered_line:
                    key = placeholder.strip("{}")
                    value = str(context.get(key, ""))

                    # Fit value to placeholder length to avoid breaking layout
                    if len(value) > len(placeholder):
                        value = value[: len(placeholder)]
                    else:
                        value = value.ljust(len(placeholder))

                    rendered_line = rendered_line.replace(placeholder, value)

            # Ensure line is exact width
            if len(rendered_line) > pad_width:
                rendered_line = rendered_line[:pad_width]
            elif len(rendered_line) < pad_width:
                rendered_line = rendered_line + (" " * (pad_width - len(rendered_line)))

            rendered.append(rendered_line)

        # Ensure exact height
        while len(rendered) < pad_height:
            rendered.append(" " * pad_width)

        return rendered[:pad_height]

    @staticmethod
    def list_available_skins(skins_dir: str = "skins") -> List[str]:
        """List all .txt skins."""
        skins_path = Path(skins_dir)
        if not skins_path.exists():
            return []
        return [f.stem for f in skins_path.glob("*.txt")]


if __name__ == "__main__":
    # Test
    loader = SkinLoader()
    skins = loader.list_available_skins()
    print(f"Found {len(skins)} skins:")
    for s in skins:
        print(f"  - {s}")
