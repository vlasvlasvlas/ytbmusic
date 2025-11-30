# YTBMusic - Guía de Uso Completa

## 🚀 Flujo Completo de Uso

### Paso 1: Instalación

```bash
cd /Users/vladimirobellini/Documents/REPOS/ytbmusic

# Opción A: Instalación automática
./install.sh

# Opción B: Manual
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
brew install mpv ffmpeg  # o sudo apt install mpv ffmpeg
```

---

### Paso 2: Ejecutar la App

```bash
./run.sh
```

**¿Qué hace run.sh?**

1. ✅ Activa el venv automáticamente
2. ✅ Detecta si MPV funciona
3. ✅ Si MPV falla → Usa VLC (old_play.py) automáticamente
4. ✅ Si MPV funciona → Usa main.py (nueva versión)

**Variables de entorno opcionales:**
```bash
USE_VLC=1 ./run.sh    # Forzar VLC
USE_MPV=1 ./run.sh    # Forzar MPV (ignorar fallback)
```

---

### Paso 3: Selección de Playlist (MENÚ INICIAL)

Al arrancar, ves este menú:

```
═══════════════════════════════════════════════════════════
  SELECT PLAYLIST
═══════════════════════════════════════════════════════════
  > lofi                    ← Cursor acá
    rock
    vladitest
    workout
────────────────────────────────────────────────────────────
[↑/↓] Navigate  [Enter] Select  [Q] Quit
```

**Controles:**
- `↑` / `↓` - Mover cursor arriba/abajo
- `Enter` - Seleccionar playlist resaltada
- `Q` - Salir

**¿Qué pasa cuando presionás Enter?**

1. Carga la playlist seleccionada
2. Empieza a reproducir **automáticamente** el primer track
3. Te lleva a la **pantalla principal** con el skin

---

### Paso 4: Pantalla Principal (Reproducción)

Una vez que elegiste playlist, ves el skin:

```
         ___________________________________________
        |  _______________________________________  |
        | / .-----------------------------------. \ |
        | | | /\ :  Mi vida en rosa     90 min| | |
        | | |/--\:....Los Romeos....... NR [ ]| | |
        | | `-----------------------------------' | |
        | |      //-\   |         |   //-\      | |
        | |     ||( )||  |_________|  ||( )||     | |  ← Cintas girando!
        | |      \-//   :....:....:   \-//      | |
        | |                                       | |
        | |  03:45 / 06:07        🎵  2/2        | |
        | |  [========>          ]                | |
        | |                                       | |
        | |   [ ⏮ ]  [ ⏸ ]  [ ⏭ ]              | |
        | |    [ 🔉 ] [||||||||  ] [ 🔊 ]       | |
        | |                              [ ❌ ]  | |
        !______/_____________________________\______!
────────────────────────────────────────────────────
▶ Mi vida en rosa (streaming)
```

**Efectos visuales activos:**
- 🎬 Si es `cassette_animated`: Las cintas `||( )||` ↔ `||(_)||` giran a 2 FPS
- ⏸ Si pausás: El tiempo parpadea (on/off cada 500ms)
- 🎯 Cuando presionás botones: Se resaltan por 200ms

---

### Paso 5: Controles Durante Reproducción

#### **Playback:**
- `Space` - Play / Pause
- `N` - Next track
- `P` - Previous track
- `→` - Seek adelante 10s
- `←` - Seek atrás 10s

#### **Volumen:**
- `+` o `=` - Subir volumen
- `-` - Bajar volumen

#### **Modos:**
- `Z` - Toggle shuffle (ON/OFF)
- `R` - Cycle repeat (NONE → TRACK → PLAYLIST)

#### **UI:**
- `S` - Cambiar skin (cycles entre todos los skins)
- `Q` - Salir

---

## 🎨 Skins Disponibles

Presioná `S` para iterar entre:

1. **cassette** - Cassette deck estático
2. **cassette_animated** - Cassette con cintas girando ⭐
3. **boombox** - Boombox retro
4. **radio** - Radio compacto
5. **minimal** - Diseño minimalista
6. **cyberpunk** - Estilo neon
7. **classic** - Vintage (del old_play.py)

El **cassette_animated** es el único con animación (2 frames).

---

## 📝 Playlists Actuales

### **lofi** (3 tracks)
- Lo-fi beats para programar
- Shuffle: OFF
- Repeat: PLAYLIST

### **rock** (5 tracks)
- Clásicos legendarios (Queen, Led Zeppelin, etc.)
- Shuffle: OFF
- Repeat: PLAYLIST

### **workout** (3 tracks)
- Energía para entrenar
- Shuffle: ON (por defecto)
- Repeat: PLAYLIST

### **vladitest** (2 tracks) ⭐
- "Mi vida en rosa" - Los Romeos
- "Si mal no me equivoco" - (Artist 1)
- Shuffle: OFF
- Repeat: PLAYLIST

---

## 🔄 Flujo de Datos

### Cuando seleccionás una playlist:

```
1. run.sh ejecuta main.py
   ↓
2. main.py muestra menú select_playlist()
   ↓
3. Usuario presiona ↑/↓ y Enter
   ↓
4. Se carga playlist desde playlists/nombre.json
   ↓  
5. Se reproduce primer track automáticamente
   ↓
6. Downloader:
   - Chequea cache
   - Si no está: get_stream_url() → mpv.play()
   - Background: download() para cache
   ↓
7. Pantalla principal con skin
   - Render loop cada 100ms
   - Animación si skin animado + playing
   - Parpadeo si paused
```

### Cuando presionás Next/Previous:

```
1. handle_input() detecta 'N' o 'P'
   ↓
2. current_playlist.next() o .previous()
   ↓
3. _play_track(nuevo_track)
   ↓
4. Mismo flujo de streaming/caching
   ↓
5. Logger registra el cambio
```

---

## 💾 Persistencia

### Estado que se guarda automáticamente (cada 10s):

- **Última playlist** usada
- **Última skin** usada
- **Último volumen**
- **Índice del track** actual
- **Total de sesiones**
- **Total playtime**

### Logs creados:

- `logs/playback.log` - Historial completo
- `logs/errors.log` - Errores
- `logs/statistics.json` - Estadísticas de uso

### Cache:

- `cache/*.m4a` - Tracks descargados
- Se reutilizan en próximas reproducciones
- No se re-descargan

---

## ❓ Preguntas Frecuentes

### ¿Cómo cambio de playlist después de iniciar?

**Opción 1:** Presioná `Q` y ejecutá `./run.sh` de nuevo

**Opción 2:** (Futuro) `L` para abrir playlist browser mid-session

### ¿Cómo sé si está usando MPV o VLC?

Mirá el output de `./run.sh`:

```bash
✓ mpv ready              ← Usando MPV (main.py)
Starting YTBMusic (mpv)...

# O:

❌ mpv check failed...    ← Fallback a VLC
Falling back to VLC (old_play.py)
```

### ¿Por qué no veo la animación del cassette?

1. Verificá que estás usando skin `cassette_animated` (`S` para cambiar)
2. La música debe estar **playing** (no paused)
3. Presioná `Space` para play

### ¿Cómo creo mi propia playlist?

```bash
cd playlists
cp lofi.json miplaylist.json
# Editá miplaylist.json
```

Estructura:
```json
{
  "metadata": {
    "name": "Mi Playlist",
    "author": "tu_nombre"
  },
  "settings": {
    "shuffle": false,
    "repeat": "playlist"
  },
  "tracks": [
    {
      "title": "Título",
      "artist": "Artista",
      "url": "https://www.youtube.com/watch?v=VIDEO_ID"
    }
  ]
}
```

Próxima ejecución de `./run.sh` → aparece en el menú!

---

## 🎯 Tips

1. **Usa cassette_animated** para ver la animación en acción
2. **Pausá con Space** para ver el parpadeo del tiempo
3. **Presioná botones rápido** para ver el highlighting
4. **Shuffle en workout** está ON por defecto - ideal para entrenar
5. **Logs en logs/playback.log** - Revisá tu historial

---

## 🐛 Troubleshooting

**"No playlists found"**
→ Revisá que existan .json en `playlists/`

**"mpv check failed"**
→ Automáticamente usa VLC, no problem

**"Broken ASCII art"**
→ No debería pasar (matrix padding), pero asegurate terminal >= 80x24

**"No sound"**
→ Chequeá volumen del sistema y que mpv/vlc tengan acceso a audio

---

**¡Disfrutá! 🎵**
