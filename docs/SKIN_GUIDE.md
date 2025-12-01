# YTBMusic Skin Creation Guide

## Overview

YTBMusic supports **two types of skins** for maximum flexibility:

1. **Freestyle Mode**: Use placeholders like `{{TITLE}}` with declared widths
2. **Template Mode**: Define exact coordinates (line, column, width) for content zones

**Both modes guarantee your ASCII art design will NEVER break** because all content widths are explicitly declared.

## Quick Start

### Freestyle Mode (Recommended for Beginners)

Perfect for those who want to design ASCII art with visible placeholders.

**Example**:
```yaml
---
name: My Cool Skin
author: Your Name
version: 1.0
mode: freestyle
placeholders:
  TITLE: 35
  ARTIST: 30
  PROGRESS: 27
  PREV: 2
  PLAY: 2
  NEXT: 2
  VOL_DOWN: 1
  VOL_UP: 1
  QUIT: 1
---
╔════════════════════════════════════════╗
║  ♪  {{TITLE}}                         ║
║      {{ARTIST}}                        ║
║  ────────────────────────────────────  ║
║  {{PROGRESS}}                          ║
║  [ {{PREV}} ] [ {{PLAY}} ] [ {{NEXT}} ]║
╚════════════════════════════════════════╝
```

### Template Mode (For Advanced Users)

Perfect for those who want complete control over exact positioning.

**Example**:
```yaml
---
name: My Template Skin
author: Your Name
version: 1.0
mode: template
zones:
  title: {line: 5, col: 10, width: 35}
  artist: {line: 6, col: 10, width: 30}
  progress: {line: 8, col: 10, width: 27}
  buttons:
    prev: {line: 10, col: 15, width: 2}
    play: {line: 10, col: 25, width: 2}
    next: {line: 10, col: 35, width: 2}
---
╔════════════════════════════════════════╗
║                                        ║
║                                        ║
║                                        ║
║  ♪                                     ║
║                                        ║
║  ────────────────────────────────────  ║
║                                        ║
║                                        ║
║         [ << ] [ ▶ ] [ >> ]           ║
╚════════════════════════════════════════╝
```

The content will be rendered at the exact positions you specify—no placeholders in the ASCII art needed!

## Required Elements

### Freestyle Mode: Required Placeholders

You **MUST** include these placeholders:
- `{{PREV}}` - Previous track button
- `{{PLAY}}` - Play/Pause button
- `{{NEXT}}` - Next track button
- `{{VOL_DOWN}}` - Volume down button
- `{{VOL_UP}}` - Volume up button
- `{{QUIT}}` - Quit button

### Template Mode: Required Zones

You **MUST** define these zones:
- `prev` - Previous button
- `play` - Play button  
- `next` - Next button
- `vol_down` - Volume down button
- `vol_up` - Volume up button
- `quit` - Quit button

## Available Content Fields

### Freestyle Placeholders / Template Zones

| Name | Description | Recommended Width |
|------|-------------|-------------------|
| `TITLE` / `title` | Song title | 30-40 chars |
| `ARTIST` / `artist` | Artist name | 25-35 chars |
| `TIME` / `time` | Current/Total time (00:00/00:00) | 11 chars |
| `TIME_CURRENT` / `time_current` | Current time only | 5 chars |
| `TIME_TOTAL` / `time_total` | Total time only | 5 chars |
| `PROGRESS` / `progress` | Progress bar | 25-30 chars |
| `TRACK_NUM` / `track_num` | Track number (e.g., "1/10") | 7-10 chars |
| `PLAYLIST` / `playlist` | Playlist name | 20-30 chars |
| `NEXT_TRACK` / `next_track` | Next track title | 25-35 chars |
| `VOLUME` / `volume` | Volume percentage | 3-4 chars |
| `STATUS` / `status` | Play/pause indicator | 1 char |
| `CACHE_STATUS` / `cache_status` | Cached indicator (✓/✗) | 1 char |
| `SHUFFLE_STATUS` / `shuffle_status` | Shuffle status (ON/OFF) | 3 chars |
| `REPEAT_STATUS` / `repeat_status` | Repeat mode (ALL/ONE/OFF) | 8 chars |
| `PREV` / `prev` | Previous button | 2 chars |
| `PLAY` / `play` | Play/pause button | 2 chars |
| `NEXT` / `next` | Next button | 2 chars |
| `VOL_DOWN` / `vol_down` | Volume down | 1 char |
| `VOL_UP` / `vol_up` | Volume up | 1 char |
| `QUIT` / `quit` | Quit button | 1 char |

## Technical Requirements

### Canvas Size
- **Width**: 120 characters (fixed)
- **Height**: 88 lines maximum (includes YAML frontmatter)

### Character Encoding
- UTF-8 encoding required
- Box-drawing characters supported: `╔ ╗ ╚ ╝ ║ ═ ─ │ ├ ┤ ┬ ┴ ┼`
- Emoji and special characters supported

### Width Declaration Rules

**CRITICAL**: Every content field **MUST** have a declared width.

#### Freestyle Mode
```yaml
placeholders:
  TITLE: 35      # Content will be truncated/padded to EXACTLY 35 chars
  ARTIST: 30     # Content will be truncated/padded to EXACTLY 30 chars
```

#### Template Mode
```yaml
zones:
  title: {line: 10, col: 5, width: 35}   # EXACTLY 35 chars at position (10, 5)
  artist: {line: 11, col: 5, width: 30}  # EXACTLY 30 chars at position (11, 5)
```

**Why?** If content is longer than the width, it's truncated. If shorter, it's padded with spaces. This ensures your ASCII art **never breaks**.

## Step-by-Step Tutorial

### Creating a Freestyle Skin

1. **Start with the YAML frontmatter**:
   ```yaml
   ---
   name: My Awesome Skin
   author: Your Name
   version: 1.0
   mode: freestyle
   placeholders:
     # List all placeholders with widths
   ---
   ```

2. **Design your ASCII art**:
   - Use any text editor
   - Keep lines under 120 characters
   - Use placeholders where you want dynamic content
   
3. **Add placeholder width declarations**:
   - For each `{{PLACEHOLDER}}` in your art, add it to the YAML:
   ```yaml
   placeholders:
     TITLE: 35
     ARTIST: 30
     # ... etc
   ```

4. **Validate your skin**:
   ```bash
   python3 ui/skin_loader.py skins/your_skin.txt
   ```

### Creating a Template Skin

1. **Start with YAML frontmatter**:
   ```yaml
   ---
   name: My Template Skin
   author: Your Name
   version: 1.0
   mode: template
   zones:
     # Define zones with coordinates
   ---
   ```

2. **Design your ASCII art** (pure decorative, NO placeholders):
   ```
   ╔════════════════════╗
   ║                    ║
   ║  [Decorative Art]  ║
   ║                    ║
   ╚════════════════════╝
   ```

3. **Define zones for content**:
   - Count the line number (starting from 0 after the `---`)
   - Count the column (starting from 0)
   - Determine how wide the content should be
   
   ```yaml
   zones:
     title: {line: 5, col: 10, width: 35}
     # Line 5, starting at column 10, 35 chars wide
   ```

4. **For nested zones (like buttons)**:
   ```yaml
   zones:
     buttons:
       prev: {line: 10, col: 5, width: 2}
       play: {line: 10, col: 15, width: 2}
       next: {line: 10, col: 25, width: 2}
   ```

5. **Validate your skin**:
   ```bash
   python3 ui/skin_loader.py skins/your_skin.txt
   ```

## Examples

See these included skins for reference:

- **Freestyle**: `skins/simple.txt`, `skins/compact.txt`, `skins/boombox.txt`
- **Template**: `skins/template_example.txt`

## Common Issues

### "Skin exceeds canvas"
- Your skin (including YAML) is taller than 88 lines
- Solution: Reduce ASCII art height or compress YAML

### "Missing required placeholders" (Freestyle)
- You forgot a required placeholder
- Solution: Add all required placeholders: `{{PREV}}`, `{{PLAY}}`, `{{NEXT}}`, `{{VOL_DOWN}}`, `{{VOL_UP}}`, `{{QUIT}}`

### "ASCII art looks broken"
- Content width doesn't match declared width
- Solution: Double-check your width declarations match the available space in your design

### UTF-8 Characters Not  Rendering
- Your terminal doesn't support UTF-8
- Solution: Use ASCII-only characters or upgrade your terminal

## Tips & Best Practices

1. **Start Simple**: Begin with a basic design and add complexity gradually
2. **Use a Grid**: Count columns carefully with a monospace font editor
3. **Test Early**: Validate your skin frequently as you build it
4. **Width Padding**: Leave a few extra characters of width to prevent truncation
5. **Visual Alignment**: Use box-drawing characters for professional looks
6. **Compress YAML**: Use inline format for zones to save lines:
   ```yaml
   # Good (1 line)
   title: {line: 10, col: 5, width: 35}
   
   # Avoid (4 lines)
   title:
     line: 10
     col: 5
     width: 35
   ```

## Testing Your Skin

```bash
# Validate skin format
python3 ui/skin_loader.py skins/your_skin.txt

# Test in the player
python3 main.py
# Press 'S' to cycle through skins
```

## Sharing Your Skin

Once you've created an amazing skin:
1. Test it thoroughly with different song titles and playlists
2. Share the `.txt` file
3. Include a screenshot!
4. Consider contributing to the project

---

**Happy Skinning! 🎨**
