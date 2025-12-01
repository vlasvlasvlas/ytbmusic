# 🎵 YTBMusic - Terminal YouTube Music Player

ASCII-first YouTube audio player with playlists and swappable skins (VLC backend, urwid UI). Optimized for 80x40 terminals; skins que exceden ese tamaño se filtran automáticamente.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Qué hay
- 🎨 **Skins ASCII** con placeholders, validadas para 80x40.
- 📝 **Playlists JSON** autodetectadas desde `playlists/`.
- 🎮 **Menú retro**: números 1-9 para playlist, letras A-J para skin.
- 💾 **Streaming + cache** vía yt-dlp + VLC; muestra progreso de descarga al bajar un tema.
- 📊 **Overlay** con progreso, volumen, siguiente track, shuffle/repeat.

## 🚀 Instalación rápida
```bash
git clone https://github.com/yourusername/ytbmusic.git
cd ytbmusic

# macOS (recomendado)
./install.sh

# Linux (si no usas install.sh)
sudo apt install vlc   # o tu gestor
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```
Luego:
```bash
./run.sh   # o: source venv/bin/activate && python3 main.py
```
Notas macOS: `install.sh` intenta usar VLC arm64 (Homebrew). Si tienes VLC x86, desinstala `/Applications/VLC.app` y reinstala con Homebrew.

## 🎮 Controles
- **Menú**: `1-9` elige playlist, `A-J` elige skin, `Q` salir.
- **Player**: `Space` play/pause, `N/P` next/prev, `←/→` seek ±10s, `↑/↓` volumen, `S` siguiente skin, `M` volver al menú, `Z` shuffle, `R` repeat, `Q` salir.
- Descarga: cuando no hay cache, verás “Downloading XX.X%” hasta completar; si falla, hace streaming.

## 📝 Playlists
Coloca archivos `.json` en `playlists/`:
```json
{
  "version": "1.0",
  "metadata": { "name": "My Mix", "description": "Favorite tracks", "author": "me" },
  "settings": { "shuffle": false, "repeat": "playlist" },
  "tracks": [
    { "title": "Song Title", "artist": "Artist Name", "url": "https://www.youtube.com/watch?v=VIDEO_ID" }
  ]
}
```
Opcional por track: `tags`, `duration`. Opcional en settings: `repeat` = `none` | `track` | `playlist`.

## 🎨 Skins (80x40)
Solo se listan los skins que no superan 80 columnas x 40 filas. Ejemplos incluidos: `compact`, `clean`, `modern`, `retro`, `minimal_dark`, `compact_info`, `template_example`, `cassette`, `cassette_animated`.

Formato de un skin (`skins/myskin.txt`):
```
---
name: My Custom Skin
author: you
version: 1.0
---
... ASCII ...
```
Placeholders requeridos (al menos una vez):  
`{{PREV}} {{PLAY}} {{NEXT}} {{VOL_DOWN}} {{VOL_UP}} {{QUIT}}`

Placeholders opcionales admitidos:  
`{{TITLE}} {{ARTIST}} {{ALBUM}} {{TIME}} {{TIME_CURRENT}} {{TIME_TOTAL}} {{PROGRESS}} {{VOLUME}} {{STATUS}} {{NEXT_TRACK}} {{PLAYLIST}} {{TRACK_NUM}} {{SHUFFLE}} {{REPEAT}} {{CACHE_STATUS}} {{SHUFFLE_STATUS}} {{REPEAT_STATUS}}`

Reglas:
- Máx 80 cols x 40 filas. Si es mayor, no se mostrará.
- Usa fuente monoespaciada. El loader recorta/padrea; evita que el arte quede demasiado grande.
- Puedes usar `skins/template_example.txt` como guía.

## 🔧 Config
- `config/default_config.json` – playback/cache/ui.
- `config/keybindings.json` – atajos por acción.
- `config/state.json` – estado persistente (último skin, volumen, etc.).

## 🐛 Problemas comunes
- **VLC no encontrado / x86 en macOS**: `brew reinstall --cask vlc` y borra el VLC x86.  
- **python-vlc/libvlc**: asegúrate de usar arm64 en Apple Silicon.  
- **yt-dlp**: `pip install --upgrade yt-dlp`.  
- **ASCII roto**: terminal monoespaciada; tamaño ≥ 80x40; usa skins validados.

## 📜 Licencia
MIT
