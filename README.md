```
  ________  ________  ________  _______   ________  ________   ________  ________ 
 ╱    ╱   ╲╱        ╲╱       ╱ ╱       ╲╲╱    ╱   ╲╱        ╲ ╱        ╲╱        ╲
╱         ╱        _╱        ╲╱        ╱╱         ╱        _╱_╱       ╱╱         ╱
╲__     ╱╱╱       ╱╱         ╱         ╱         ╱-        ╱╱         ╱       --╱ 
  ╲____╱╱ ╲______╱ ╲________╱╲__╱__╱__╱╲________╱╲________╱ ╲________╱╲________╱  
```

# YTBMusic

**Terminal YouTube Music Player** con playlists, skins ASCII y descarga automática.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![Screenshot](screenshot.png)

---

## ✨ Features

| Feature | Descripción |
|---------|-------------|
| 🎵 **Streaming + Cache** | Reproduce desde YouTube, cachea para offline |
| ⬇️ **Auto-descarga** | Descarga automática en background al iniciar |
| 📥 **Import YouTube** | Importá playlists completas con `I` |
| 🎨 **Skins ASCII** | 9+ skins retro intercambiables |
| 🔀 **Shuffle/Repeat** | Modos de reproducción |
| 📊 **Footer 3 líneas** | Notificaciones + contexto + shortcuts |

---

## 🚀 Instalación

```bash
git clone https://github.com/yourusername/ytbmusic.git
cd ytbmusic
./install.sh    # macOS/Linux
./run.sh        # Ejecutar
```

**Requisitos**: Python 3.8+, VLC, yt-dlp

---

## ⌨️ Controles

### Menú
| Tecla | Acción |
|:-----:|--------|
| `1-9` | Seleccionar playlist |
| `P` | Reproducir |
| `X` | Borrar playlist |
| `I` | Importar de YouTube |
| `A-J` | Cambiar skin |
| `Q` | Salir |

### Reproductor
| Tecla | Acción |
|:-----:|--------|
| `Space` | Play/Pause |
| `N/P` | Next/Prev |
| `←/→` | Seek ±10s |
| `↑/↓` | Volumen |
| `S` | Cambiar skin |
| `Z` | Shuffle |
| `R` | Repeat |
| `M` | Menú |
| `Q` | Salir |

---

## 📁 Estructura

```
ytbmusic/
├── playlists/     # Playlists JSON
├── skins/         # Skins ASCII (80x40 max)
├── cache/         # Audio cacheado
├── logs/          # Logs de la app
└── config/        # Configuración
```

---

## 📝 Playlists

Formato JSON en `playlists/`:
```json
{
  "metadata": { "name": "My Mix" },
  "tracks": [
    { "title": "Song", "artist": "Artist", "url": "https://youtube.com/watch?v=..." }
  ]
}
```

O importá desde YouTube con la tecla `I`.

---

## 🎨 Skins

Skins ASCII en `skins/` (máx 80x40). Placeholders:
- Requeridos: `{{PREV}} {{PLAY}} {{NEXT}} {{VOL_DOWN}} {{VOL_UP}} {{QUIT}}`
- Opcionales: `{{TITLE}} {{ARTIST}} {{TIME}} {{PROGRESS}} {{VOLUME}}`

---

## 🐛 Problemas comunes

| Problema | Solución |
|----------|----------|
| VLC no encontrado | `brew reinstall --cask vlc` |
| yt-dlp desactualizado | `pip install --upgrade yt-dlp` |
| ASCII roto | Terminal ≥ 80x40, fuente mono |

---

## 📄 Licencia

MIT
