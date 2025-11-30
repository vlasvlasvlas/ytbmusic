# 🎵 YTBMusic - Terminal YouTube Music Player

ASCII-first YouTube audio player with playlists and swappable skins (VLC backend, urwid UI).

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features
- 🎨 **ASCII skins** with placeholder-based templating
- 📝 **JSON playlists** auto-discovered from `playlists/`
- 🎮 **Keyboard controls** for play/pause, seek, volume, next/prev
- 💾 **Streaming + cache** via yt-dlp + VLC backend
- 📊 **Now playing overlay** with progress, volume, next track

## 🚀 Quick Start
```bash
git clone https://github.com/yourusername/ytbmusic.git
cd ytbmusic

brew install --cask vlc   # or: sudo apt install vlc
pip install -r requirements.txt

./run.sh                  # or: python3 main.py
```

On first run you'll pick a playlist and a skin; playback starts immediately.

> Legacy script: `old_play.py` (demo) no longer used by default.

## 🎮 Controls (urwid UI)
- Playback: `Space` play/pause, `N` next, `P` previous
- Seek: `→` +10s, `←` -10s
- Volume: `↑` subir, `↓` bajar
- UI: `S` cambiar skin, `L` siguiente playlist (sin auto-play), `M` recargar playlists (sin auto-play), `Enter` reproducir pista, `Q` salir

## 📝 Playlists
Playlists live in `playlists/` and are auto-detected.

Creating one (steps):
1) Copy this template to `playlists/mymix.json`:
```json
{
  "version": "1.0",
  "metadata": {
    "name": "My Mix",
    "description": "Favorite tracks",
    "author": "me"
  },
  "settings": { "shuffle": false, "repeat": "playlist" },
  "tracks": [
    {
      "title": "Song Title",
      "artist": "Artist Name",
      "url": "https://www.youtube.com/watch?v=VIDEO_ID"
    }
  ]
}
```
2) Fill each track with `title`, `artist`, and a YouTube `url`.
3) Optional: `tags`, `duration`, tweak `shuffle` or `repeat` (`none`, `track`, `playlist`).

Included: `lofi.json`, `rock.json`, `workout.json` as examples.

## 🎨 Skins
Skins are text files in `skins/` with YAML frontmatter and placeholders.

Required placeholders (must appear at least once):
- `{{PREV}}` `{{PLAY}}` `{{NEXT}}`
- `{{VOL_DOWN}}` `{{VOL_UP}}`
- `{{QUIT}}`

Optional placeholders supported:
- `{{TITLE}}` `{{ARTIST}}` `{{ALBUM}}`
- `{{TIME}}` `{{TIME_CURRENT}}` `{{TIME_TOTAL}}`
- `{{PROGRESS}}` `{{VOLUME}}` `{{STATUS}}`
- `{{NEXT_TRACK}}` `{{PLAYLIST}}` `{{TRACK_NUM}}`
- `{{SHUFFLE}}` `{{REPEAT}}`

Create a skin (`skins/myskin.txt`):
```
---
name: My Custom Skin
author: yourname
version: 1.0
min_width: 60
min_height: 18
supports_color: false
---
╔═══════════════════════════════════╗
║ {{TITLE}}                         ║
║ {{ARTIST}}                        ║
╠═══════════════════════════════════╣
║ {{TIME}}                          ║
║ {{PROGRESS}}                      ║
╠═══════════════════════════════════╣
║ [{{PREV}}] [{{PLAY}}] [{{NEXT}}]       ║
║ [{{VOL_DOWN}}] {{VOLUME}} [{{VOL_UP}}] ║
║                 [{{QUIT}}]        ║
╚═══════════════════════════════════╝
```
The loader pads all lines to a uniform width to keep the ASCII aligned.

Bundled skins: `cassette.txt`, `classic.txt`, `minimal.txt`, `radio.txt`.

## 🔧 Config
`config/default_config.json` — playback/cache/ui defaults.  
`config/keybindings.json` — keys per action.  
`config/state.json` — persisted state (last skin/volume/etc.).

## 🐛 Troubleshooting
- **VLC not found**: `brew install --cask vlc` or `sudo apt install vlc`
- **python-vlc errors**: Ensure VLC is installed and in your PATH. On macOS, the script tries to auto-detect `/Applications/VLC.app`.
- **yt-dlp errors**: `pip install --upgrade yt-dlp`
- **ASCII misaligned**: use a terminal >= 120x60, monospace font; ensure skins include required placeholders.

## 📜 License
MIT
