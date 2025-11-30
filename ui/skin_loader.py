"""
YTBMusic Skin Loader with Matrix-Based Rendering

Loads ASCII art skins with YAML frontmatter and ensures proper
alignment by padding all lines to the same width.
"""

import yaml
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


CANVAS_WIDTH = 80
CANVAS_HEIGHT = 40


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
        '{{REPEAT}}'
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
        """Ensure all required placeholders are present."""
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
    
    def render(self, lines: List[str], context: Dict[str, str], pad_width: int = 120, pad_height: int = 60) -> List[str]:
        """
        Replace placeholders with fixed-width text and pad to a fixed canvas size.
        Each placeholder is replaced with a string truncated/padded to the exact placeholder length
        to avoid deforming the ASCII art (layered rendering).
        """
        rendered = []
        placeholders = self.REQUIRED_PLACEHOLDERS + self.OPTIONAL_PLACEHOLDERS
        for line in lines:
            rendered_line = line
            for placeholder in placeholders:
                key = placeholder.strip("{}")
                rep = str(context.get(key, ""))
                # ensure fixed width equal to placeholder length
                fixed = rep[: len(placeholder)].ljust(len(placeholder))
                rendered_line = rendered_line.replace(placeholder, fixed)
            if len(rendered_line) < pad_width:
                rendered_line = rendered_line + (" " * (pad_width - len(rendered_line)))
            rendered.append(rendered_line[:pad_width])
        # pad height
        while len(rendered) < pad_height:
            rendered.append(" " * pad_width)
        return rendered[:pad_height]
    
    @staticmethod
    def list_available_skins(skins_dir: str = 'skins') -> List[str]:
        """List all available .txt skin files in the skins directory."""
        skins_path = Path(skins_dir)
        
        if not skins_path.exists():
            return []
        
        return [f.stem for f in skins_path.glob('*.txt')]
    
    @staticmethod
    def validate_skin(skin_path: str) -> Tuple[bool, str]:
        """
        Validate a skin file without loading it completely.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            loader = SkinLoader()
            loader.load(skin_path)
            return True, "Skin is valid!"
        except Exception as e:
            return False, str(e)


if __name__ == '__main__':
    # Test the skin loader
    import sys
    
    if len(sys.argv) > 1:
        skin_path = sys.argv[1]
        is_valid, message = SkinLoader.validate_skin(skin_path)
        
        if is_valid:
            print(f"✅ {message}")
            loader = SkinLoader()
            metadata, lines = loader.load(skin_path)
            print(f"\nSkin: {metadata.get('name', 'Unknown')}")
            print(f"Author: {metadata.get('author', 'Unknown')}")
            print(f"Size: {loader.max_width}x{loader.max_height}")
        else:
            print(f"❌ {message}")
            sys.exit(1)
    else:
        print("Usage: python skin_loader.py <skin_path>")
        print("\nAvailable skins:")
        for skin in SkinLoader.list_available_skins():
            print(f"  - {skin}")
