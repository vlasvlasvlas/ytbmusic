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
- **Smart Import**: Detección inteligente de capítulos y metadatos antes de la creación de la playlist.

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
      "url": "https://www.youtube.com/watch?v=…#chapter_1",
      "duration": 180,
      "tags": [],
      "is_playable": true,
      "error_msg": null,
      "start_time": 0.0,
      "end_time": 180.0
    }
  ]
}
```

**Nuevos Campos (Track Model):**
- `start_time` (float): Tiempo de inicio en segundos. Usado para **Chapter Splitting**.
- `end_time` (float, optional): Tiempo de fin en segundos. Si es `None`, reproduce hasta el final del archivo.

**Chapter Splitting (Virtual Tracks):**
Cuando se importa un video con capítulos, el sistema crea múltiples entradas `Track` que apuntan a la **misma URL base**. Para diferenciarlas lógicamente (y evitar conflictos de caché mal gestionados), se añade un fragmento único `#chapter_N` a la URL. El backend de descarga (`core/downloader.py`) ignora estos fragmentos para identificar el archivo físico, pero el `Track` mantiene su identidad única y sus tiempos de corte.

Notas:
- `is_playable=false` + `error_msg` se usan para “recordar” videos privados/eliminados y saltarlos permanentemente.
- Borrar una playlist elimina el JSON, pero **no** borra los audios en `cache/`.

## 3) Threading / Concurrencia (reglas)

- **Main thread**: `urwid.MainLoop` + render de UI + manejo de teclado.
- **Background threads**:
  - `DownloadManager` (1 worker): descarga tracks sin bloquear UI.
  - **Import Pipeline**:
    - **Step 1 (Metadata Fetch)**: Obtiene título/capítulos rápidamente (`extract_flat` o `dump_json`).
    - **UI Interruption**: Pide confirmación de nombre al usuario (main thread).
    - **Step 2 (Playlist Build)**: Construye la estructura completa y guarda el JSON.
  - Stream URL fetch: thread que obtiene la URL de streaming cuando un tema no está cacheado.

Regla de oro:
- Cualquier cambio de UI debe ocurrir en el main loop (p.ej. usando `loop.set_alarm_in(0, ...)` o pasando eventos por una cola).

## 4) Módulos principales

### `main.py` (UI + orquestación)

Responsabilidad:
- Construye el menú principal y el reproductor (skins).
- Maneja estados: `MENU`, `LOADING`, `PLAYER`, `EDIT`.
- **MVC Pattern (Partial)**: Delega la construcción de UI a `ui/views/menu_view.py` y `ui/views/player_view.py`.
- **Dependency Injection**: `YTBMusicUI` recibe sus componentes Core (`player`, `downloader`, etc.) por constructor, facilitando testing y desacople.
- Administra overlays (input dialogs, confirm dialogs, track picker).
- **Import Flow**: Orquesta la obtención asíncrona de metadatos para pre-llenar los diálogos.
- **ConfirmDialog**: Implementación custom (`WidgetWrap` con `keypress`) para asegurar que los eventos de teclado no se "filtren" al fondo (fix reciente).
- **Pre-check / Settings**: Corre un chequeo rápido de entorno (VLC, cookies, versiones) al inicio y expone un modal de Settings (flechas + Enter) con acciones de mantenimiento: diagnóstico rápido, limpieza de cache huérfana y refresco manual de cookies.
- **Panel Diagnóstico**: Overlay read-only con estado de cola, último error, cache y versiones (yt-dlp/VLC).
- **Búsqueda global (`F`)**: Indexa todas las playlists (título/autor) para un buscador cross-playlist que carga la playlist y reproduce el track seleccionado.
- **Fondos (backgrounds/)**: Presets en JSON (`bg`, `fg`, `alt_bg`, `transition_sec`, `palette` opcional) aplicados solo al canvas del player; selector modal con disclaimer; se registran como palette entries en runtime.

UX/Atajos relevantes:
- **Menu**: `I` importar, `E` rename, `X` delete, `P` play, `R` random all.
- **Player**: `Space` play/pause, `N/P` next/prev, `Z` shuffle, `R` repeat, `T` track picker, `D` download missing, `M` menú.

### `core/download_manager.py` (cola única de descargas)

Responsabilidad:
- Cola prioritaria (heap) + 1 worker thread.
- Dedupe por URL (ignora fragmentos `#`) y skip de tracks ya cacheados.
- Cancelación best-effort (incluye cancel in-progress vía `yt_dlp.utils.DownloadCancelled`).
- Progreso throttleado (por defecto ~4 updates/seg).
- Reintentos con backoff suave para errores transitorios (429/timeouts), emitiendo evento `retry` para la UI.

Prioridades (modelo típico en UI):
- Import / focus: prioridad más alta, puede reemplazar/cancelar lo actual.
- Prefetch de playlist en reproducción: prioridad alta.
- Auto-download: prioridad baja.

### `core/downloader.py` (yt-dlp + cache)

Responsabilidad:
- Extrae metadata (`extract_metadata` / playlist items).
- **Chapter Detection**: En `extract_playlist_items`, si detecta `chapters` en un video único, expande la entrada en múltiples items con `start_time` y `end_time`.
- **Id Extraction**: Modificado `_extract_video_id` para limpiar fragmentos (`#chapter_N`) y mapear múltiples tracks virtuales a un solo archivo físico en caché.
- Obtiene stream URL (`get_stream_url`).
- Descarga audio a `cache/` (`download`).
- **Anti-Bot (Cookies)**:
  - En el arranque aplica una estrategia jerárquica: `YTBMUSIC_COOKIES_FILE` → `cookies.txt` → `YTBMUSIC_COOKIES_BROWSER` → barrido por navegadores populares (Chrome/Brave/Edge/Vivaldi/Opera/Chromium/Firefox/Safari).
  - Se puede desactivar con `YTBMUSIC_DISABLE_COOKIES`, aunque no se recomienda porque YouTube suele exigir sesión.
  - Expone `refresh_cookies_from_browser()` que ejecuta `yt_dlp --simulate --cookies-from-browser <browser> --cookies <file>` usando el intérprete actual, permitiendo regenerar `cookies.txt` desde la UI cuando aparece el challenge.

### Flujo de verificación anti-bot (UI)

1. `DownloadManager` emite eventos `error` con el texto original de yt-dlp.
2. `YTBMusicUI._handle_download_event` detecta cadenas como “Sign in to confirm you’re not a bot”, HTTP 429, etc., y llama a `_handle_auth_challenge`.
3. `_handle_auth_challenge`:
   - Cancela la cola (`DownloadManager.cancel_all`).
   - Muestra `ConfirmDialog` con instrucciones para abrir el navegador configurado y loguearse.
   - Si el usuario confirma, `_start_cookie_refresh` llama a `YouTubeDownloader.refresh_cookies_from_browser` en un thread, mostrando el estado en pantalla.
   - Al finalizar, `_cookie_refresh_result` notifica (éxito/fracaso) y vuelve al menú.
4. Una vez actualizado el `cookiefile`, las descargas/streams usan la sesión nueva sin reiniciar la app.

### `core/playlist.py` (modelo Playlist + manager)

Responsabilidad:
- `Track` (dataclass): Ahora soporta `start/end_time`.
- `PlaylistManager`: carga playlists desde `playlists/`, rename seguro, y persistencia.

### `core/playlist_editor.py` (utilidades sobre JSON)

Responsabilidad:
- Crear/borrar playlists, importar desde YouTube.
- Logica pura de manipulación de JSON.

### `core/playlist_store.py` (persistencia atómica)

Responsabilidad:
- `PLAYLIST_LOCK`: lock global.
- `write_json_atomic`: write temp + fsync + `os.replace`.

### `core/player.py` (VLC wrapper)

Responsabilidad:
- Reproducción de archivos cacheados o stream URLs.
- **Partial Playback**: Método `play(source, start_time, end_time)` modificado para pasar opciones `start-time` y `stop-time` a la instancia de `libvlc`. Esto permite reproducir segmentos específicos de un archivo grande sin cortarlo físicamente.

### `ui/skin_loader.py` (skins)
- Carga y valida skins ASCII.

### ui/dialogs.py (reusable UI)
- `InputDialog`: Diálogo de entrada de texto (ASCII style).
- `ConfirmDialog`: Diálogo modal de confirmación (Yes/No).

### ui/views/ (UI Views)
- `menu_view.py`: `MenuView`. Construye el listado de playlists y maneja la visualización del menú.
- `player_view.py`: `PlayerView`. Renderiza el skin ASCII con el contexto de reproducción (tiempo, barra, metadatos).

### `core/logger.py` (logging)
- Configura logs rotativos en `logs/ytbmusic.log`.

## 5) Flujos importantes (comportamiento esperado)

### A) Startup
- Carga playlists + skins.
- Arranca `DownloadManager`.
- Programa auto-download (baja prioridad).

### B) Import de playlist / Smart Import (`I`)
1.  **Input URL**: Usuario ingresa URL.
2.  **Metadata Fetch**: App muestra "Fetching metadata..." y consulta `yt-dlp` (fase flat).
3.  **Name Dialog**: Se presenta el diálogo con el **título pre-cargado** (obtenido en paso 2).
4.  **Confirm**: Usuario acepta/edita nombre.
5.  **Build**: Se procesa la lista.
    *   Si es Playlist: se agregan los videos.
    *   Si es Video Único + Capítulos: se aplica **Chapter Splitting** y se agregan N tracks.
    *   Si es Video Único: se agrega 1 track.
6.  **Queue**: Se encolan descargas.

### C) Play / Prefetch
- Al reproducir, se respetan `start_time` y `end_time`. Si es un capítulo, VLC se detendrá o saltará al siguiente (manejado por lógica "Next Track" en `main.py`).

### D) Delete playlist (`X`)
- Muestra confirm dialog (modal real, captura input).
- Cancela descargas asociadas.
- Borra JSON.

### E) Rename playlist (`E`)
- Muestra input dialog. Persistencia atómica.

### F) Track Picker (`T`)
- Abre overlay con lista, permite búsqueda y selección.

### G) Settings / Diagnóstico (`O` en menú)
- Modal navegable con flechas/Enter. Muestra estado de entorno (VLC, cookies, versiones), cache total y huérfanos. Acciones: re-evaluar entorno (con feedback), refrescar cookies, limpiar cache huérfana y abrir panel de diagnóstico.
- Panel de diagnóstico: overlay read-only con cola de descargas, último error, cache, cookies y versiones.

### H) Limpieza de cache
- Detección de huérfanos: compara stems esperados (URL/filename normalizado) vs archivos en `cache/`. Ignora capítulos compartidos gracias a la limpieza de fragmentos `#chapter` en `_extract_video_id`.
- Confirmación antes de borrar; ejecución en background con notificación final (archivos y bytes liberados).

### I) Búsqueda global (`F`)
- Input dialog para texto (case-insensitive). Construye índice simple de todas las playlists (se invalida tras import/rename/delete).
- Muestra overlay con hasta 200 resultados (playlist :: título — artista); Enter carga la playlist, mapea índice respetando shuffle y reproduce el track.

### J) Fondos
- Carpeta `backgrounds/` con presets JSON. Se cargan en arranque y se seleccionan desde un modal (con disclaimer). Solo afectan el canvas del player; footer/menú permanecen con la paleta fija. Transiciones opcionales (`transition_sec`) ciclan entre `bg`/`alt_bg`/`palette`.

## 6) Debugging rápido

- Logs: `logs/ytbmusic.log`
- Si la división de capítulos falla: verificar si `yt-dlp` retorna campo `chapters` para ese video.
- Si VLC no corta el tema: verificar que `end_time` se esté pasando correctamente en `player.play()`.
