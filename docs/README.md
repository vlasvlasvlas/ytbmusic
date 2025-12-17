# YTBMusic — Arquitectura y Comportamiento (módulo por módulo)

Este documento describe cómo funciona `ytbmusic` por dentro: arquitectura, módulos, flujos y reglas de comportamiento (UI/UX, descargas, persistencia).

## 1) Visión general

`ytbmusic` es un player TUI (terminal) con:
- UI en `urwid` (event loop en el hilo principal)
- reproducción con `python-vlc` (archivos cacheados o stream URL)
- descarga/cache con `yt-dlp`
- playlists en JSON dentro de `playlists/`
- skins ASCII en `skins/`

Puntos clave del diseño:
- Un único sistema de descargas centralizado (`DownloadManager`) con **prioridades**, **dedupe**, **cancelación** y **eventos** hacia UI.
- UI siempre se actualiza desde el **main loop** (thread-safe) y el progreso se **throttlea** para no generar flicker.
- Operaciones sobre playlists con **lock** + **escritura atómica** (temp → `os.replace`) para evitar corrupción de JSON.

## 2) Modelo de datos (playlists JSON)

Ubicación: `playlists/<nombre>.json`

Estructura típica:
```json
{
  "version": "1.0",
  "metadata": {
    "name": "Mi Playlist",
    "description": "…",
    "author": "ytbmusic",
    "tags": []
  },
  "settings": {
    "shuffle": false,
    "repeat": "playlist"
  },
  "tracks": [
    {
      "title": "Song",
      "artist": "Artist",
      "url": "https://www.youtube.com/watch?v=…",
      "duration": 0,
      "tags": [],
      "is_playable": true,
      "error_msg": null
    }
  ]
}
```

Notas:
- `is_playable=false` + `error_msg` se usan para “recordar” videos privados/eliminados y saltarlos permanentemente.
- Borrar una playlist elimina el JSON, pero **no** borra los audios en `cache/`.

## 3) Threading / Concurrencia (reglas)

- **Main thread**: `urwid.MainLoop` + render de UI + manejo de teclado.
- **Background threads**:
  - `DownloadManager` (1 worker): descarga tracks sin bloquear UI.
  - Import: thread que consulta a YouTube y arma metadata de playlist.
  - Stream URL fetch: thread que obtiene la URL de streaming cuando un tema no está cacheado.

Regla de oro:
- Cualquier cambio de UI debe ocurrir en el main loop (p.ej. usando `loop.set_alarm_in(0, ...)` o pasando eventos por una cola).

## 4) Módulos principales

### `main.py` (UI + orquestación)

Responsabilidad:
- Construye el menú principal y el reproductor (skins).
- Maneja estados: `MENU`, `LOADING`, `PLAYER`, `EDIT`.
- Administra overlays (input dialogs, confirm dialogs, track picker).
- Integra descargas (recibe eventos del `DownloadManager` y actualiza la status bar + activity log).

UX/Atajos relevantes:
- **Menu**: `I` importar, `E` rename, `X` delete (con confirm), `P` play, `R` random all.
- **Player**: `Space` play/pause, `N/P` next/prev, `Z` shuffle, `R` repeat, `T` track picker, `D` download missing, `M` menú.

Detalles de diseño:
- El popup de rename se abre de forma “defer” para que el overlay no se cierre por el mismo ciclo de input.
- El foco del menú se preserva al recrear el menú (no vuelve a la primera fila).
- El Track Picker usa un overlay con `Frame` para evitar problemas de sizing en Urwid.

### `core/download_manager.py` (cola única de descargas)

Responsabilidad:
- Cola prioritaria (heap) + 1 worker thread.
- Dedupe por URL y skip de tracks ya cacheados.
- Cancelación best-effort (incluye cancel in-progress vía `yt_dlp.utils.DownloadCancelled`).
- Progreso throttleado (por defecto ~4 updates/seg).
- Emite eventos a UI: `queue`, `start`, `progress`, `complete`, `error`, `canceled`, `idle`, `cancel_all`, `cancel_playlist`.

Prioridades (modelo típico en UI):
- Import / focus: prioridad más alta, puede reemplazar/cancelar lo actual.
- Prefetch de playlist en reproducción: prioridad alta.
- Auto-download: prioridad baja.

### `core/downloader.py` (yt-dlp + cache)

Responsabilidad:
- Extrae metadata (`extract_metadata` / playlist items).
- Obtiene stream URL (`get_stream_url`).
- Descarga audio a `cache/` (`download`), con callback de progreso.

Notas:
- Propaga cancelación (`DownloadCancelled`) para que `DownloadManager` pueda cortar.

### `core/playlist.py` (modelo Playlist + manager)

Responsabilidad:
- `Track` (dataclass) y `Playlist` (shuffle/repeat/posición).
- `PlaylistManager`: carga playlists desde `playlists/`, rename seguro, y persistencia de tracks no reproducibles.

Funciones clave:
- `Playlist.get_current_track()` salta tracks `is_playable=false`.
- `Playlist.set_position_by_original_index()` permite seleccionar por índice real (útil en Track Picker incluso con shuffle).
- `PlaylistManager.mark_track_unplayable(...)` persiste `is_playable=false`.

### `core/playlist_editor.py` (utilidades sobre JSON)

Responsabilidad:
- Crear/borrar playlists, importar desde YouTube, agregar/borrar tracks, detectar tracks faltantes (no cacheados).
- Todas las escrituras usan lock + atomic write.

### `core/playlist_store.py` (persistencia atómica)

Responsabilidad:
- `PLAYLIST_LOCK`: lock global para operaciones de playlists.
- `write_json_atomic`: write temp + fsync + `os.replace`.
- `read_json`: lectura JSON.

### `core/player.py` (VLC wrapper)

Responsabilidad:
- Reproducción de archivos cacheados o stream URLs.
- Controles: play/pause/stop, seek, volumen, time info.
- Callback de fin de track para disparar “next” desde el main loop.

### `ui/skin_loader.py` (skins)

Responsabilidad:
- Carga y valida skins ASCII (`skins/*.txt`) y metadata YAML.
- Renderiza placeholders (ej: `{{TITLE}}`, `{{TIME}}`, etc.) con contexto actual.

Referencias:
- `SKINS.md` (guía práctica para crear/modificar skins).

### `core/logger.py` (logging)

Responsabilidad:
- Configura logs rotativos en `logs/ytbmusic.log`.
- Evita stdout para no romper la UI (Urwid).

## 5) Flujos importantes (comportamiento esperado)

### A) Startup
- Carga playlists + skins.
- Arranca `DownloadManager`.
- Programa auto-download (baja prioridad) para tracks faltantes.

### B) Import de playlist (`I`)
- Pide URL y nombre (opcional).
- Import corre en thread (no bloquea).
- UI entra en `LOADING` con mensajes claros.
- Se encolan descargas con prioridad alta (focus), y al completar el primer track se inicia reproducción automáticamente.

### C) Play / Prefetch
- Al reproducir una playlist, se puede encolar prefetch de faltantes con prioridad alta (sin pisar un import activo).

### D) Delete playlist (`X`)
- Muestra confirm dialog (“¿estás seguro?”).
- Cancela descargas de esa playlist en cola y en progreso (best-effort).
- Borra el JSON de `playlists/`.
- Opcional: ofrece borrar archivos en `cache/` que parecen no estar usados por otras playlists (conservador).

### E) Rename playlist (`E`)
- Muestra input dialog.
- Rename es atómico y protegido por lock para evitar corrupción.

### F) Track Picker (`T`)
- Abre overlay con la lista de tracks.
- `/` activa búsqueda/filtro por `artist`/`title`.
- Al seleccionar un track, ajusta posición de playlist y reproduce ese tema.

## 6) Debugging rápido

- Logs: `logs/ytbmusic.log`
- Si algo “descarga lo que no espero”, mirar los eventos de `DownloadManager` (request id + label).
