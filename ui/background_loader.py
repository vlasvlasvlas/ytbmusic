"""
Background Loader with Gradient Support

Loads background presets from backgrounds/ (JSON files).
Supports both solid color backgrounds and animated gradient effects.
Supports JSONC (JSON with Comments) - use // for line comments.
"""

import json
import re
from pathlib import Path
from typing import Dict, Tuple, List, Any

BACKGROUND_DIR = Path("backgrounds")


def strip_json_comments(text: str) -> str:
    """
    Remove // comments from JSONC text.
    Handles comments at end of lines and full-line comments.
    Does NOT remove comments inside strings.
    """
    result = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        char = text[i]
        
        if escape:
            result.append(char)
            escape = False
            i += 1
            continue
        
        if char == '\\' and in_string:
            result.append(char)
            escape = True
            i += 1
            continue
        
        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue
        
        # Check for // comment (only outside strings)
        if not in_string and char == '/' and i + 1 < len(text) and text[i + 1] == '/':
            # Skip until end of line
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        
        result.append(char)
        i += 1
    
    return ''.join(result)


class BackgroundLoader:
    """Load background presets from backgrounds/ (JSON/JSONC files)."""

    @staticmethod
    def list_available_backgrounds() -> List[str]:
        BACKGROUND_DIR.mkdir(exist_ok=True)
        names = []
        for path in BACKGROUND_DIR.glob("*.json"):
            names.append(path.stem)
        return sorted(names)

    @staticmethod
    def load(name: str) -> Tuple[Dict, Dict]:
        BACKGROUND_DIR.mkdir(exist_ok=True)
        path = BACKGROUND_DIR / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Background '{name}' not found")
        with path.open("r", encoding="utf-8") as f:
            raw_text = f.read()
        
        # Strip // comments before parsing
        clean_json = strip_json_comments(raw_text)
        meta = json.loads(clean_json)

        # Check if this is a gradient background
        mode = meta.get("mode", "solid")

        if mode == "gradient":
            # Return gradient-specific config with all demoscene parameters
            data = {
                "name": meta.get("name") or name,
                "mode": "gradient",
                "pattern": meta.get("pattern", "wave_sine"),
                "direction": meta.get("direction", "vertical"),
                "angle": meta.get("angle", 45),
                "colors": meta.get("colors", ["dark blue", "light cyan", "white"]),
                "speed": meta.get("speed", 0.12),
                "step_size": meta.get("step_size", 1.0),
                "band_height": meta.get("band_height", 3),
                "wave_amplitude": meta.get("wave_amplitude", 1.5),
                "wave_frequency": meta.get("wave_frequency", 1.0),
                "phase_shift": meta.get("phase_shift", 0.05),
                "color_spread": meta.get("color_spread", 1.0),
                "smoothness": meta.get("smoothness", 1),
                "fg": meta.get("fg", "white"),
            }
        else:
            # Standard solid/cycling background
            data = {
                "name": meta.get("name") or name,
                "mode": "solid",
                "bg": meta.get("bg") or "black",
                "fg": meta.get("fg") or "white",
                "alt_bg": meta.get("alt_bg"),
                "transition_sec": meta.get("transition_sec") or 0,
                "palette": meta.get("palette") or [],
            }
        return data, meta

    @staticmethod
    def is_gradient(meta: Dict[str, Any]) -> bool:
        """Check if background config is gradient mode."""
        return meta.get("mode") == "gradient"
