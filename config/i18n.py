"""
Internationalization (i18n) module for YTBMusic.

Provides a simple translation system with Spanish and English support.
Set YTBMUSIC_LANG environment variable to change language (default: es).
"""

import os
from typing import Dict

# Default language (can be overridden by YTBMUSIC_LANG env var)
LANG = os.environ.get("YTBMUSIC_LANG", "es")

STRINGS: Dict[str, Dict[str, str]] = {
    # =========================================================================
    # SPANISH (Default)
    # =========================================================================
    "es": {
        # Menu
        "menu.title": "MENÚ PRINCIPAL",
        "menu.select_playlist": "SELECCIONAR PLAYLIST",
        "menu.select_skin": "SELECCIONAR SKIN",
        "menu.import": "Importar de YouTube",
        "menu.search": "Buscar en todas las playlists",
        "menu.random": "🔀 Random All Songs",
        "menu.settings": "Configuración / Herramientas",
        "menu.play": "REPRODUCIR",
        "menu.delete": "BORRAR PLAYLIST",
        "menu.rename": "RENOMBRAR PLAYLIST",
        "menu.download": "DESCARGAR PENDIENTES",
        "menu.return_player": "VOLVER AL REPRODUCTOR",
        "menu.no_playlists": "No hay playlists!",
        "menu.add_playlists": "Agregá archivos .json a playlists/",
        "menu.no_skins": "No hay skins!",
        "menu.add_skins": "Agregá archivos .txt a skins/",
        "menu.selected": "SELECCIONADA",
        "menu.current": "Actual",
        "menu.actions_for": "Acciones para seleccionada:",
        "menu.footer": "↑/↓ Navegar  •  Enter Seleccionar  •  F Buscar  •  O Config  •  Q Salir",
        "menu.downloaded": "descargados",
        "menu.none": "Ninguna",
        "menu.background": "Fondo",
        "menu.select_background": "Seleccionar Fondo",
        "menu.quick_actions": "Acciones rápidas:",
        # Player
        "player.playing": "Reproduciendo",
        "player.paused": "Pausado",
        "player.stopped": "Detenido",
        "player.loading": "Cargando...",
        "player.buffering": "Buffering...",
        "player.track": "Track",
        "player.of": "de",
        # Settings
        "settings.title": "Configuración / Herramientas",
        "settings.diagnostics": "Diagnóstico del Sistema",
        "settings.cache_cleanup": "Limpiar Cache (huérfanos)",
        "settings.refresh_cookies": "Refrescar Cookies",
        "settings.refresh_playlists": "Refrescar Playlists",
        "settings.refresh_env": "Re-evaluar entorno",
        "settings.close": "Cerrar",
        # Streaming
        "stream.title": "🎧 Streaming a Servidor Externo",
        "stream.description": "Transmití tu música para que otros la escuchen en tiempo real.",
        "stream.requirements": "📋 REQUISITOS:",
        "stream.req_icecast": "1. Servidor Icecast corriendo (local o remoto)",
        "stream.req_ffmpeg": "2. FFmpeg instalado (brew install ffmpeg)",
        "stream.req_cache": "3. Track descargado en cache (no streaming directo)",
        "stream.not_configured": "📡 No configurado",
        "stream.active": "✅ Activo",
        "stream.share_link": "🔗 LINK PARA COMPARTIR",
        "stream.share_hint": "↑ Compartí este link! Otros pueden abrir en VLC, browser, etc.",
        "stream.config_hint": "💡 Configurá URL/user/pass de tu servidor Icecast abajo.",
        "stream.example_url": "Ejemplo URL: http://tu-servidor:8000/stream",
        "stream.current_config": "Config actual",
        "stream.no_user": "sin user",
        "stream.warning": "⚠️ Compartir música puede violar TOS. Usalo bajo tu responsabilidad.",
        "stream.start": "▶️ INICIAR STREAM (requiere FFmpeg)",
        "stream.stop": "🛑 DETENER STREAM",
        "stream.edit": "⚙️ Editar Streaming (URL/usuario/password/bitrate)",
        "stream.ffmpeg_missing": "❌ FFmpeg no encontrado. Instalalo para streaming.",
        "stream.config_missing": "❌ Configurá URL y password primero",
        "stream.no_playlist": "❌ No hay playlist cargada",
        "stream.no_track": "❌ No hay track actual",
        "stream.not_cached": "❌ Track no en cache. Descargalo primero (D).",
        "stream.started": "📡 Streaming",
        "stream.stopped": "🛑 Stream detenido",
        "stream.no_active": "No hay stream activo",
        # Dialogs
        "dialog.confirm": "Confirmar",
        "dialog.cancel": "Cancelar",
        "dialog.yes": "Sí",
        "dialog.no": "No",
        "dialog.ok": "OK",
        "dialog.error": "Error",
        "dialog.success": "Éxito",
        "dialog.close_hint": "Enter: confirmar  •  Esc: cancelar",
        # Import
        "import.title": "Importar Playlist",
        "import.url_prompt": "URL de YouTube (playlist o video)",
        "import.processing": "Procesando...",
        "import.success": "Playlist importada",
        "import.error": "Error al importar",
        # Search
        "search.title": "Buscar en Playlists",
        "search.prompt": "Buscar:",
        "search.no_results": "Sin resultados",
        "search.hint": "Enter: buscar  •  Esc: cerrar",
        # Download
        "download.starting": "Iniciando descarga...",
        "download.complete": "Descarga completada",
        "download.error": "Error de descarga",
        "download.queued": "En cola",
        "download.progress": "Descargando",
        # Cache
        "cache.clean": "Cache limpia ✓ (sin huérfanos)",
        "cache.orphans_found": "Se encontraron archivos huérfanos",
        "cache.delete_confirm": "¿Borrarlos?",
        "cache.deleted": "Cache limpiada",
        # Errors
        "error.generic": "Ocurrió un error",
        "error.network": "Error de red",
        "error.file_not_found": "Archivo no encontrado",
        # Status
        "status.ready": "Listo",
        "status.loading": "Cargando...",
        "status.saving": "Guardando...",
        "status.precheck_updated": "Pre-check actualizado",
        "status.cleaning_cache": "Limpiando cache...",
        "status.background": "Fondo",
        "status.animation": "Animación",
        "status.no_animations": "No se encontraron animaciones en animations/",
        "status.error_select_playlist": "Error al seleccionar playlist",
        "status.error_unknown": "Error desconocido",
        "status.error_refresh_cookies": "Error al refrescar cookies",
        # Modals
        "modal.search_playlists": "Buscar en playlists",
        "modal.diagnostics": "Diagnóstico rápido",
        "modal.settings": "Settings / Herramientas",
        "modal.select_playlist": "Seleccionar Playlist",
        "modal.select_skin": "Seleccionar Skin",
        "modal.select_background": "Seleccionar Fondo",
        "modal.playlist_name": "Nombre de Playlist (Opcional)",
        "modal.name": "Nombre",
        "modal.rename": "Renombrar",
        "modal.new_name": "Nuevo Nombre",
        "modal.search_text": "Texto",
        "modal.search_all": "Buscar en todas las playlists",
        # Streaming dialogs
        "stream.dialog.url": "Streaming URL",
        "stream.dialog.url_hint": "URL (icecast/shout/http)",
        "stream.dialog.user": "Usuario",
        "stream.dialog.password": "Password",
        "stream.dialog.bitrate": "Bitrate (kbps)",
        "stream.dialog.format": "Formato (mp3/ogg)",
    },
    # =========================================================================
    # ENGLISH
    # =========================================================================
    "en": {
        # Menu
        "menu.title": "MAIN MENU",
        "menu.select_playlist": "SELECT PLAYLIST",
        "menu.select_skin": "SELECT SKIN",
        "menu.import": "Import from YouTube",
        "menu.search": "Search all playlists",
        "menu.random": "🔀 Random All Songs",
        "menu.settings": "Settings / Tools",
        "menu.play": "PLAY",
        "menu.delete": "DELETE PLAYLIST",
        "menu.rename": "RENAME PLAYLIST",
        "menu.download": "DOWNLOAD MISSING",
        "menu.return_player": "RETURN TO PLAYER",
        "menu.no_playlists": "No playlists found!",
        "menu.add_playlists": "Add .json files to playlists/",
        "menu.no_skins": "No skins found!",
        "menu.add_skins": "Add .txt files to skins/",
        "menu.selected": "SELECTED",
        "menu.current": "Current",
        "menu.actions_for": "Actions for selected:",
        "menu.footer": "↑/↓ Navigate  •  Enter Select  •  F Search  •  O Settings  •  Q Quit",
        "menu.downloaded": "downloaded",
        "menu.none": "None",
        "menu.background": "Background",
        "menu.select_background": "Select Background",
        "menu.quick_actions": "Quick actions:",
        # Player
        "player.playing": "Playing",
        "player.paused": "Paused",
        "player.stopped": "Stopped",
        "player.loading": "Loading...",
        "player.buffering": "Buffering...",
        "player.track": "Track",
        "player.of": "of",
        # Settings
        "settings.title": "Settings / Tools",
        "settings.diagnostics": "System Diagnostics",
        "settings.cache_cleanup": "Clean Cache (orphans)",
        "settings.refresh_cookies": "Refresh Cookies",
        "settings.refresh_playlists": "Refresh Playlists",
        "settings.refresh_env": "Re-evaluate environment",
        "settings.close": "Close",
        # Streaming
        "stream.title": "🎧 Streaming to External Server",
        "stream.description": "Stream your music so others can listen in real-time.",
        "stream.requirements": "📋 REQUIREMENTS:",
        "stream.req_icecast": "1. Icecast server running (local or remote)",
        "stream.req_ffmpeg": "2. FFmpeg installed (brew install ffmpeg)",
        "stream.req_cache": "3. Track downloaded to cache (no direct streaming)",
        "stream.not_configured": "📡 Not configured",
        "stream.active": "✅ Active",
        "stream.share_link": "🔗 SHARE LINK",
        "stream.share_hint": "↑ Share this link! Others can open in VLC, browser, etc.",
        "stream.config_hint": "💡 Configure URL/user/pass of your Icecast server below.",
        "stream.example_url": "Example URL: http://your-server:8000/stream",
        "stream.current_config": "Current config",
        "stream.no_user": "no user",
        "stream.warning": "⚠️ Sharing music may violate TOS. Use at your own risk.",
        "stream.start": "▶️ START STREAM (requires FFmpeg)",
        "stream.stop": "🛑 STOP STREAM",
        "stream.edit": "⚙️ Edit Streaming (URL/user/password/bitrate)",
        "stream.ffmpeg_missing": "❌ FFmpeg not found. Install it for streaming.",
        "stream.config_missing": "❌ Configure URL and password first",
        "stream.no_playlist": "❌ No playlist loaded",
        "stream.no_track": "❌ No current track",
        "stream.not_cached": "❌ Track not cached. Download first (D).",
        "stream.started": "📡 Streaming",
        "stream.stopped": "🛑 Stream stopped",
        "stream.no_active": "No active stream",
        # Dialogs
        "dialog.confirm": "Confirm",
        "dialog.cancel": "Cancel",
        "dialog.yes": "Yes",
        "dialog.no": "No",
        "dialog.ok": "OK",
        "dialog.error": "Error",
        "dialog.success": "Success",
        "dialog.close_hint": "Enter: confirm  •  Esc: cancel",
        # Import
        "import.title": "Import Playlist",
        "import.url_prompt": "YouTube URL (playlist or video)",
        "import.processing": "Processing...",
        "import.success": "Playlist imported",
        "import.error": "Import error",
        # Search
        "search.title": "Search Playlists",
        "search.prompt": "Search:",
        "search.no_results": "No results",
        "search.hint": "Enter: search  •  Esc: close",
        # Download
        "download.starting": "Starting download...",
        "download.complete": "Download complete",
        "download.error": "Download error",
        "download.queued": "Queued",
        "download.progress": "Downloading",
        # Cache
        "cache.clean": "Cache clean ✓ (no orphans)",
        "cache.orphans_found": "Orphan files found",
        "cache.delete_confirm": "Delete them?",
        "cache.deleted": "Cache cleaned",
        # Errors
        "error.generic": "An error occurred",
        "error.network": "Network error",
        "error.file_not_found": "File not found",
        # Status
        "status.ready": "Ready",
        "status.loading": "Loading...",
        "status.saving": "Saving...",
        "status.precheck_updated": "Pre-check updated",
        "status.cleaning_cache": "Cleaning cache...",
        "status.background": "Background",
        "status.animation": "Animation",
        "status.no_animations": "No animations found in animations/",
        "status.error_select_playlist": "Error selecting playlist",
        "status.error_unknown": "Unknown error",
        "status.error_refresh_cookies": "Error refreshing cookies",
        # Modals
        "modal.search_playlists": "Search playlists",
        "modal.diagnostics": "Quick Diagnostics",
        "modal.settings": "Settings / Tools",
        "modal.select_playlist": "Select Playlist",
        "modal.select_skin": "Select Skin",
        "modal.select_background": "Select Background",
        "modal.playlist_name": "Playlist Name (Optional)",
        "modal.name": "Name",
        "modal.rename": "Rename",
        "modal.new_name": "New Name",
        "modal.search_text": "Text",
        "modal.search_all": "Search all playlists",
        # Streaming dialogs
        "stream.dialog.url": "Streaming URL",
        "stream.dialog.url_hint": "URL (icecast/shout/http)",
        "stream.dialog.user": "User",
        "stream.dialog.password": "Password",
        "stream.dialog.bitrate": "Bitrate (kbps)",
        "stream.dialog.format": "Format (mp3/ogg)",
    },
}


def t(key: str, **kwargs) -> str:
    """
    Translate a string key to the current language.

    Args:
        key: The translation key (e.g., "menu.import")
        **kwargs: Optional format arguments

    Returns:
        Translated string, or the key itself if not found

    Example:
        t("menu.import")  # Returns "Importar de YouTube" in Spanish
        t("download.progress", file="song.mp3")  # With formatting
    """
    lang_strings = STRINGS.get(LANG, STRINGS.get("es", {}))
    text = lang_strings.get(key, key)

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return text


def set_language(lang: str):
    """Set the current language (es or en)."""
    global LANG
    if lang in STRINGS:
        LANG = lang
    else:
        LANG = "es"


def get_language() -> str:
    """Get the current language code."""
    return LANG


def get_available_languages() -> list:
    """Get list of available language codes."""
    return list(STRINGS.keys())
