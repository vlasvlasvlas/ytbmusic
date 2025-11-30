# 🎵 YTBMusic - Sistema de Menú y Gestión de Playlists

## 📊 Comité de 3 Expertos - Análisis

### 👨‍💻 **EXPERTO 1: UX/Flujo**

#### **Problema Actual:**
- ❌ No hay menú principal
- ❌ Salta directo a selección de playlist → player
- ❌ No se pueden crear playlists desde la app
- ❌ No se pueden agregar canciones fácilmente
- ❌ Editar playlist = editar JSON manualmente

#### **Propuesta UX:**

**1. Menú Principal (pantalla de inicio):**
```
═══════════════════════════════════════════
  YTBMUSIC - MAIN MENU
═══════════════════════════════════════════
  
  1. Play Music        → Elegir playlist y reproducir
  2. Manage Playlists  → Crear/editar/borrar playlists
  3. Add Songs         → Buscar y agregar desde YouTube
  4. Settings          → Skins, volumen default, etc
  5. Quit
  
───────────────────────────────────────────
Use ↑/↓ and Enter to select
```

**2. Playlist Manager:**
```
═══════════════════════════════════════════
  PLAYLIST MANAGER
═══════════════════════════════════════════
  
  > rock (5 tracks)
    lofi (3 tracks)
    workout (3 tracks)
    vladitest (2 tracks)
    
  [N] New Playlist
  [E] Edit Selected
  [D] Delete Selected
  [Enter] View Tracks
  [Esc] Back
```

**3. YouTube Search & Add:**
```
═══════════════════════════════════════════
  ADD SONGS FROM YOUTUBE
═══════════════════════════════════════════
  
  Search: queen bohemian rhapsody_
  
  Results:
  > 1. Bohemian Rhapsody (Official Video)
       Queen • 5:55 • 1.2B views
       
    2. Bohemian Rhapsody - Lyrics
       LyricsVault • 5:52 • 45M views
       
  [Enter] Add to playlist
  [S] Search again
  [Esc] Cancel
```

**4. In-Player Quick Actions:**
```
Durante reproducción:
  A = Quick add (agregar canción actual a otra playlist)
  E = Edit playlist actual
  M = Volver al menú principal
```

---

### 🏗️ **EXPERTO 2: Arquitectura**

#### **Módulos Nuevos Necesarios:**

**1. `core/menu_system.py`:**
```python
class MenuSystem:
    def show_main_menu(stdscr) -> str
    def show_playlist_manager(stdscr) -> Optional[str]
    def show_settings(stdscr)
```

**2. `core/playlist_editor.py`:**
```python
class PlaylistEditor:
    def create_playlist(name, description) -> Playlist
    def add_track(playlist, track)
    def remove_track(playlist, index)
    def rename_playlist(playlist, new_name)
    def delete_playlist(playlist_name)
    def validate_playlist(playlist) -> bool
```

**3. `core/youtube_search.py`:**
```python
class YouTubeSearch:
    def search(query: str, max_results=10) -> List[SearchResult]
    def get_metadata(url: str) -> TrackMetadata
    
class SearchResult:
    title: str
    uploader: str  # "artist"
    duration: int  # seconds
    url: str
    view_count: int
    thumbnail: str
```

#### **Integración con Código Existente:**

**main.py - Nuevo flujo:**
```python
def main():
    menu = MenuSystem()
    
    while True:
        choice = menu.show_main_menu()
        
        if choice == "play":
            curses.wrapper(YTBMusic().run)
        elif choice == "manage":
            menu.show_playlist_manager()
        elif choice == "add":
            menu.show_add_songs()
        elif choice == "settings":
            menu.show_settings()
        elif choice == "quit":
            break
```

#### **Extracción de Metadatos con yt-dlp:**

```python
# Búsqueda
yt-dlp "ytsearch10:queen bohemian" \
  --print "%(title)s\t%(uploader)s\t%(duration)s\t%(webpage_url)s" \
  --skip-download

# Metadatos de URL específica
yt-dlp "URL" \
  --print "%(title)s\t%(uploader)s\t%(duration)s" \
  --skip-download
```

**Output ejemplo:**
```
Bohemian Rhapsody	Queen	355	https://youtube.com/watch?v=...
```

---

### 📦 **EXPERTO 3: Producto/Implementación**

#### **Fase 1: Menú Principal + CRUD Básico (30-45 min)**

**Features:**
- ✅ Menú principal con 5 opciones
- ✅ Listar playlists existentes
- ✅ Crear playlist nueva (vacía)
- ✅ Borrar playlist
- ✅ Agregar link manual (pide URL, título, artista)

**NO incluye:**
- ❌ Búsqueda YouTube (Fase 2)
- ❌ Metadatos auto (Fase 2)
- ❌ Quick actions in-player (Fase 3)

**Archivos a crear:**
- `core/menu_system.py`
- `core/playlist_editor.py`

**Archivos a modificar:**
- `main.py` (nuevo entry point)

---

#### **Fase 2: Búsqueda YouTube + Metadatos Auto (45-60 min)**

**Features:**
- ✅ Buscar en YouTube desde la app
- ✅ Ver resultados con título/artista/duración
- ✅ Elegir resultado y agregar a playlist
- ✅ Metadatos extraídos automáticamente
- ✅ Opción de editar metadatos antes de agregar

**Archivos a crear:**
- `core/youtube_search.py`

**Dependencias:**
- yt-dlp ya instalado ✅

---

#### **Fase 3: Quick Actions In-Player (20-30 min)**

**Features:**
- ✅ Atajo `A` para agregar canción a otra playlist
- ✅ Atajo `E` para editar playlist actual
- ✅ Atajo `M` para volver al menú
- ✅ Previsualización de cambios

**Archivos a modificar:**
- `main.py` (agregar atajos)

---

## 🎯 **Propuesta Final**

### **Implementación Incremental:**

**AHORA (Fase 1):**
```bash
1. Menú principal al inicio
2. Opciones: Play | Manage | Add Manual | Quit
3. Manage: listar, crear nueva (vacía), borrar
4. Add Manual: pedir URL + título + artista
```

**Tiempo estimado:** 30-45 minutos  
**Complejidad:** Media  
**Beneficio:** Alto - UX completa

**DESPUÉS (Fase 2):**
```bash
5. Búsqueda YouTube integrada
6. Metadatos automáticos
7. Preview de resultados
```

**Tiempo estimado:** 45-60 minutos  
**Complejidad:** Media-Alta  
**Beneficio:** Muy Alto - experiencia premium

**MÁS ADELANTE (Fase 3):**
```bash
8. Quick add in-player (atajo A)
9. Edit playlist in-player (atajo E)
10. Volver a menú (atajo M)
```

**Tiempo estimado:** 20-30 minutos  
**Complejidad:** Baja  
**Beneficio:** Alto - conveniencia

---

## 💡 **Recomendación del Comité**

### **✅ APROBAR Fase 1 AHORA**

**Por qué:**
1. Resuelve el problema principal (falta de menú)
2. Permite crear/gestionar playlists básicamente
3. No requiere complejidad de búsqueda
4. Base sólida para Fases 2 y 3
5. Rápido de implementar (30-45 min)

**Flujo nuevo:**
```
./run.sh
  ↓
[Menú Principal]
  ↓
Elegís "Play Music"
  ↓
[Selección Playlist] (como antes)
  ↓
[Player] (como antes)
```

**Nuevo además:**
```
[Menú Principal]
  ↓
Elegís "Manage Playlists"
  ↓
[CRUD Playlists]
  - Crear nueva
  - Borrar existente
  - Agregar link manual
```

---

## 📋 **Checklist de Implementación Fase 1**

- [ ] Crear `core/menu_system.py`
  - [ ] `show_main_menu()` con 4 opciones
  - [ ] `show_playlist_manager()` con CRUD
  - [ ] `add_manual_track()` con inputs
- [ ] Crear `core/playlist_editor.py`
  - [ ] `create_playlist(name, desc)`
  - [ ] `delete_playlist(name)`
  - [ ] `add_track_manual(playlist, url, title, artist)`
  - [ ] `save_playlist(playlist)` con validación
- [ ] Modificar `main.py`
  - [ ] Mover player a método `run_player()`
  - [ ] Nuevo `main()` con loop de menú
  - [ ] Entry point llama a `main()`
- [ ] Testing
  - [ ] Crear playlist nueva
  - [ ] Agregar 2 tracks manuales
  - [ ] Borrar playlist
  - [ ] Play desde menú

---

**¿Procedo con Fase 1?**
