"""
Background Loader with Gradient Support

Loads background presets from backgrounds/ (JSON files).
Supports both solid color backgrounds and animated gradient effects.
"""

import json
from pathlib import Path
from typing import Dict, Tuple, List, Any

BACKGROUND_DIR = Path("backgrounds")


class BackgroundLoader:
    """Load background presets from backgrounds/ (JSON key/value files)."""

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
            meta = json.load(f)

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
