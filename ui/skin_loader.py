"""
YTBMusic Skin Loader with Matrix-Based Rendering

Loads ASCII art skins with YAML frontmatter and ensures proper
alignment by padding all lines to the same width.
"""

import yaml
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


CANVAS_WIDTH = 120
CANVAS_HEIGHT = 88


class SkinLoader:
    """Loads and validates ASCII art skins with placeholder support."""
    
    # Required placeholders that every skin must have
    REQUIRED_PLACEHOLDERS = [
        '{{PREV}}',
        '{{PLAY}}',
        '{{NEXT}}',
        '{{VOL_DOWN}}',
        '{{VOL_UP}}',
        '{{QUIT}}'
    ]
    
    # Optional placeholders
    OPTIONAL_PLACEHOLDERS = [
        '{{TITLE}}',
        '{{ARTIST}}',
        '{{ALBUM}}',
        '{{TIME}}',
        '{{TIME_CURRENT}}',
        '{{TIME_TOTAL}}',
        '{{PROGRESS}}',
        '{{VOLUME}}',
        '{{STATUS}}',
        '{{NEXT_TRACK}}',
        '{{PLAYLIST}}',
        '{{TRACK_NUM}}',
        '{{SHUFFLE}}',
        '{{REPEAT}}',
        '{{CACHE_STATUS}}',
        '{{SHUFFLE_STATUS}}',
        '{{REPEAT_STATUS}}'
    ]
    
    def __init__(self):
        self.metadata = {}
        self.content = ""
        self.lines = []
        self.frames = []  # For animated skins
        self.is_animated = False
        self.max_width = 0
        self.max_height = 0
        self.current_frame = 0
        
        # Dual-mode system
        self.mode = 'freestyle'  # 'freestyle' or 'template'
        self.placeholder_widths = {}  # For freestyle mode: {"TITLE": 35, ...}
        self.zones = {}  # For template mode: {"title": {"line": 10, "col": 5, "width": 35}, ...}
        
    def load(self, skin_path: str) -> Tuple[Dict, List[str]]:
        """
        Load a skin file and return metadata and padded lines.
        
        Args:
            skin_path: Path to the skin .txt file
            
        Returns:
            Tuple of (metadata dict, list of padded lines)
            
        Raises:
            ValueError: If skin is invalid or missing required placeholders
        """
        path = Path(skin_path)
        if not path.exists():
            raise FileNotFoundError(f"Skin not found: {skin_path}")
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse YAML frontmatter
        self.metadata, self.content = self._parse_frontmatter(content)
        
        # Detect mode (freestyle or template)
        self.mode = self.metadata.get('mode', 'freestyle')
        if self.mode not in ['freestyle', 'template']:
            raise ValueError(f"Invalid mode '{self.mode}'. Must be 'freestyle' or 'template'")
        
        # Parse mode-specific configuration
        if self.mode == 'freestyle':
            self.placeholder_widths = self.metadata.get('placeholders', {})
        else:  # template mode
            self.zones = self.metadata.get('zones', {})
        
        # Check if animated
        self.is_animated = self.metadata.get('animated', False)
        
        if self.is_animated:
            # Parse frames
            self.frames = self._parse_frames(self.content)
            if not self.frames:
                raise ValueError("Animated skin has no frames")
            # Use first frame as default lines
            self.lines = self.frames[0]
        else:
            # Split into lines
            self.lines = self.content.split('\n')
        
        # Validate required placeholders and ASCII
        self._validate_placeholders()
        self._validate_ascii()
        
        # Apply matrix padding and fit to canvas (fixed size)
        if self.is_animated:
            padded_frames = []
            for frame in self.frames:
                padded = self._apply_matrix_padding_to_lines(frame)
                fitted = self._fit_to_canvas(padded)
                padded_frames.append(fitted)
            self.frames = padded_frames
            padded_lines = self.frames[0]
        else:
            padded_lines = self._apply_matrix_padding()
            padded_lines = self._fit_to_canvas(padded_lines)
        
        # Calculate dimensions
        self.max_width = len(padded_lines[0]) if padded_lines else 0
        self.max_height = len(padded_lines)
        
        # Return metadata and frames (or single frame list)
        if self.is_animated:
            return self.metadata, self.frames
        else:
            return self.metadata, padded_lines
    
    def _parse_frontmatter(self, content: str) -> Tuple[Dict, str]:
        """Extract YAML frontmatter from skin content."""
        # Match YAML frontmatter between --- markers
        pattern = r'^---\n(.*?)\n---\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)
        
        if match:
            frontmatter_str = match.group(1)
            body = match.group(2)
            
            try:
                metadata = yaml.safe_load(frontmatter_str)
                return metadata or {}, body
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML frontmatter: {e}")
        else:
            # No frontmatter, use defaults
            return {
                'name': 'Unnamed Skin',
                'author': 'Unknown',
                'version': '1.0',
                'min_width': 80,
                'min_height': 24,
                'supports_color': False
            }, content
    
    def _validate_placeholders(self):
        """Ensure all required placeholders are present (freestyle mode only)."""
        # Template mode doesn't use placeholders
        if self.mode == 'template':
            return
        
        content_str = '\n'.join(self.lines)
        
        missing = []
        for placeholder in self.REQUIRED_PLACEHOLDERS:
            if placeholder not in content_str:
                missing.append(placeholder)
        
        if missing:
            raise ValueError(
                f"Skin is missing required placeholders: {', '.join(missing)}\n"
                f"Required: {', '.join(self.REQUIRED_PLACEHOLDERS)}"
            )

    def _validate_ascii(self):
        """Allow UTF-8 characters (no restriction). Kept for future checks."""
        return

    def _fit_to_canvas(self, lines: List[str], width: int = CANVAS_WIDTH, height: int = CANVAS_HEIGHT) -> List[str]:
        """
        Fit lines into the target canvas (crop/pad) while keeping alignment.
        Oversized skins are trimmed; undersized are padded with spaces.
        """
        trimmed = []
        for line in lines:
            line = line.rstrip("\n")
            if len(line) > width:
                line = line[:width]
            trimmed.append(line)
        if len(trimmed) > height:
            trimmed = trimmed[:height]
        # pad width/height
        padded = []
        for line in trimmed:
            if len(line) < width:
                line = line + (" " * (width - len(line)))
            padded.append(line)
        while len(padded) < height:
            padded.append(" " * width)
        return padded[:height]
    
    def _apply_matrix_padding(self) -> List[str]:
        """
        Pad all lines to the same width to prevent broken ASCII art.
        
        This is critical for maintaining visual integrity of the skins.
        """
        if not self.lines:
            return []
        
        max_width = max(len(line) for line in self.lines)
        padded_lines = []
        for line in self.lines:
            padding_needed = max_width - len(line)
            padded_line = line + (' ' * padding_needed)
            padded_lines.append(padded_line)
        
        return padded_lines
    
    def _calculate_visual_width(self, line: str) -> int:
        """
        Calculate the visual width of a line.
        
        We need to account for the fact that placeholders will be replaced
        with actual content of different widths.
        """
        # For now, just use the actual line length
        # In the future, we could estimate based on typical replacement sizes
        return len(line)
    
    def _parse_frames(self, content: str) -> List[List[str]]:
        """
        Parse animated skin frames.
        
        Frames are separated by FRAME_1:, FRAME_2:, etc.
        """
        frames = []
        
        # Split by FRAME_ markers
        frame_pattern = r'FRAME_\d+:(.*?)(?=FRAME_\d+:|$)'
        matches = re.findall(frame_pattern, content, re.DOTALL)
        
        if not matches:
            # Try simpler split
            parts = content.split('FRAME_')
            for part in parts[1:]:  # Skip first empty part
                # Remove frame number and colon
                frame_content = re.sub(r'^\d+:\s*', '', part, count=1)
                if frame_content.strip():
                    frames.append(frame_content.strip().split('\n'))
        else:
            for frame_content in matches:
                if frame_content.strip():
                    frames.append(frame_content.strip().split('\n'))
        
        return frames
    
    def _apply_matrix_padding_to_lines(self, lines: List[str]) -> List[str]:
        """
        Apply matrix padding to a specific list of lines.
        Used for padding individual frames.
        """
        if not lines:
            return []
        
        # Find max width
        max_width = max(len(line) for line in lines)
        
        # Pad all lines
        padded = []
        for line in lines:
            padding_needed = max_width - len(line)
            padded.append(line + (' ' * padding_needed))
        
        return padded
    
    def render(self, lines: List[str], context: Dict[str, str], pad_width: int = 120, pad_height: int = 68) -> List[str]:
        """
        Render skin with content based on mode (freestyle or template).
        
        Both modes ensure content widths are EXACT to prevent breaking ASCII art.
        
        Freestyle: Replaces placeholders with fixed-width content
        Template: Renders content at exact coordinates
        """
        if self.mode == 'freestyle':
            return self._render_freestyle(lines, context, pad_width, pad_height)
        else:  # template
            return self._render_template(lines, context, pad_width, pad_height)
    
    def _render_freestyle(self, lines: List[str], context: Dict[str, str], 
                          pad_width: int, pad_height: int) -> List[str]:
        """
        Freestyle mode: Replace placeholders with fixed-width content.
        Width for each placeholder is declared in metadata.
        """
        rendered = []
        placeholders = self.REQUIRED_PLACEHOLDERS + self.OPTIONAL_PLACEHOLDERS
        
        for line in lines:
            rendered_line = line
            
            # Replace each placeholder with EXACT width from declaration
            for placeholder in placeholders:
                if placeholder in rendered_line:
                    key = placeholder.strip("{}")
                    value = str(context.get(key, ""))
                    
                    # Get declared width for this placeholder
                    if key in self.placeholder_widths:
                        width = self.placeholder_widths[key]
                    else:
                        # Fallback to default widths if not declared
                        default_widths = {
                            "TITLE": 35, "ARTIST": 30, "NEXT_TRACK": 30,
                            "PLAYLIST": 25, "TIME": 15, "TIME_CURRENT": 5,
                            "TIME_TOTAL": 5, "PROGRESS": 27, "TRACK_NUM": 10,
                            "VOLUME": 4, "STATUS": 1, "CACHE_STATUS": 1,
                            "SHUFFLE_STATUS": 3, "REPEAT_STATUS": 8,
                            "PREV": 2, "PLAY": 2, "NEXT": 2,
                            "VOL_DOWN": 1, "VOL_UP": 1, "QUIT": 1,
                        }
                        width = default_widths.get(key, len(value))
                    
                    # CRITICAL: Fixed-width replacement
                    # Truncate if too long, pad if too short
                    fixed_value = value[:width].ljust(width)
                    rendered_line = rendered_line.replace(placeholder, fixed_value)
            
            # Pad entire line to canvas width
            if len(rendered_line) > pad_width:
                rendered_line = rendered_line[:pad_width]
            elif len(rendered_line) < pad_width:
                rendered_line = rendered_line.ljust(pad_width)
            
            rendered.append(rendered_line)
        
        # Pad height
        while len(rendered) < pad_height:
            rendered.append(" " * pad_width)
        
        return rendered[:pad_height]
    
    def _render_template(self, lines: List[str], context: Dict[str, str],
                        pad_width: int, pad_height: int) -> List[str]:
        """
        Template mode: Render content at exact coordinates.
        Zones define line, column, and width for each element.
        """
        # Start with base lines (pure decorative art, no placeholders)
        # Convert to list of lists for character-by-character manipulation
        rendered = []
        for line in lines:
            if len(line) > pad_width:
                line = line[:pad_width]
            rendered.append(list(line.ljust(pad_width)))
        
        # Pad height
        while len(rendered) < pad_height:
            rendered.append(list(" " * pad_width))
        
        # Render each zone at its exact coordinates
        for zone_name, zone_config in self.zones.items():
            if isinstance(zone_config, dict) and 'line' in zone_config:
                # Simple zone (e.g., title, artist)
                self._render_zone(rendered, zone_name, zone_config, context, pad_width, pad_height)
            else:
                # Nested zones (e.g., buttons: {prev: {...}, play: {...}, next: {...}})
                for sub_name, sub_config in zone_config.items():
                    if isinstance(sub_config, dict) and 'line' in sub_config:
                        self._render_zone(rendered, sub_name, sub_config, context, pad_width, pad_height)
        
        # Convert back to strings
        return [''.join(line) for line in rendered][:pad_height]
    
    def _render_zone(self, rendered: List[List[str]], zone_name: str,
                     config: Dict, context: Dict[str, str], 
                     pad_width: int, pad_height: int):
        """
        Render a single zone at exact coordinates.
        """
        line_num = config.get('line', 0)
        col = config.get('col', 0)
        width = config.get('width', 10)
        
        # Bounds check
        if line_num < 0 or line_num >= pad_height:
            return
        if col < 0 or col >= pad_width:
            return
        
        # Get content for this zone
        # Map zone names to context keys
        key = zone_name.upper()
        value = str(context.get(key, ""))
        
        # Fixed-width content
        fixed_value = value[:width].ljust(width)
        
        # Write at exact position
        for i, char in enumerate(fixed_value):
            pos = col + i
            if pos < len(rendered[line_num]) and pos < pad_width:
                rendered[line_num][pos] = char
    
    @staticmethod
    def list_available_skins(skins_dir: str = 'skins') -> List[str]:
        """List all available .txt skin files in the skins directory."""
        skins_path = Path(skins_dir)
        
        if not skins_path.exists():
            return []

        valid = []
        for f in skins_path.glob('*.txt'):
            ok, _ = SkinLoader.validate_skin(str(f))
            if ok:
                valid.append(f.stem)
        return valid
    
    @staticmethod
    def validate_skin(skin_path: str) -> Tuple[bool, List[str]]:
        """
        Validate a skin file and return specific errors.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        try:
            with open(skin_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 1. Frontmatter check
            mode = 'freestyle'  # default
            try:
                # Simple check for --- markers
                if content.startswith("---\n"):
                    loader = SkinLoader()
                    metadata, body = loader._parse_frontmatter(content)
                    mode = metadata.get('mode', 'freestyle')
                else:
                    body = content
            except Exception as e:
                errors.append(f"YAML Error: {str(e)}")
                body = content

            # 2. Dimensions check
            lines = body.splitlines()
            for i, line in enumerate(lines):
                 # Visual width check (approximate due to unicode)
                 if len(line) > CANVAS_WIDTH:
                     errors.append(f"Line {i+1} too long: {len(line)} chars (max {CANVAS_WIDTH})")
            
            if len(lines) > CANVAS_HEIGHT:
                errors.append(f"Too many lines: {len(lines)} (max {CANVAS_HEIGHT})")

            # 3. Placeholder check (only for freestyle mode)
            if mode == 'freestyle':
                missing = []
                for p in SkinLoader.REQUIRED_PLACEHOLDERS:
                    if p not in body:
                        missing.append(p)
                if missing:
                    errors.append(f"Missing required placeholders: {', '.join(missing)}")

            return len(errors) == 0, errors

        except Exception as e:
            return False, [f"File error: {str(e)}"]

    def create_error_skin(self, errors: List[str]) -> List[str]:
        """Generate a skin that displays the errors to the user."""
        lines = []
        lines.append("╔════════════════════════════════════════════════════════════════════════════╗")
        lines.append("║                           SKIN ERROR REPORT                                ║")
        lines.append("║                                                                            ║")
        lines.append("║  The selected skin could not be loaded. Please fix the following issues:   ║")
        lines.append("║                                                                            ║")
        
        for err in errors[:15]:  # Limit to 15 errors to fit
            # Truncate to fit width
            msg = f" • {err}"[:74]
            lines.append(f"║ {msg:<74} ║")
            
        if len(errors) > 15:
            lines.append(f"║  ... and {len(errors)-15} more errors.                                     ║")
            
        lines.append("║                                                                            ║")
        lines.append("║  Press 'S' to switch skins, or edit the file to fix it.                    ║")
        lines.append("╚════════════════════════════════════════════════════════════════════════════╝")
        
        return self._fit_to_canvas(lines)


if __name__ == '__main__':
    # Test the skin loader
    import sys
    
    if len(sys.argv) > 1:
        skin_path = sys.argv[1]
        is_valid, errors = SkinLoader.validate_skin(skin_path)
        
        if is_valid:
            print(f"✅ Skin is valid!")
            loader = SkinLoader()
            metadata, lines = loader.load(skin_path)
            print(f"\nSkin: {metadata.get('name', 'Unknown')}")
            print(f"Author: {metadata.get('author', 'Unknown')}")
            print(f"Size: {loader.max_width}x{loader.max_height}")
        else:
            print("❌ Skin has errors:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
    else:
        print("Usage: python skin_loader.py <skin_path>")
        print("\nAvailable skins:")
        for skin in SkinLoader.list_available_skins():
            print(f"  - {skin}")

