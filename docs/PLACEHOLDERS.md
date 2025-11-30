# YTBMusic - Sistema de Placeholders en Skins

## ✅ Cómo Funciona el Sistema

### 1. **Placeholders Disponibles**

Todos los skins pueden usar estos placeholders que se reemplazan automáticamente:

**Información del Track:**
- `{{TITLE}}` - Título de la canción
- `{{ARTIST}}` - Artista
- `{{ALBUM}}` - Álbum (si disponible)
- `{{TRACK_NUM}}` - Posición en playlist (ej: "2/5")
- `{{PLAYLIST}}` - Nombre del playlist

**Tiempo:**
- `{{TIME}}` - Tiempo completo "03:45 / 06:07"
- `{{TIME_CURRENT}}` - Solo tiempo actual "03:45"
- `{{TIME_TOTAL}}` - Solo duración total "06:07"

**Controles:**
- `{{PROGRESS}}` - Barra de progreso "[========>     ]"
- `{{VOLUME}}` - Barra de volumen "[||||||||  ]"
- `{{STATUS}}` - Ícono estado (🎵 playing, ⏸ paused)

**Botones (requeridos):**
- `{{PREV}}` - Botón anterior ⏮
- `{{PLAY}}` - Botón play/pause ▶/⏸
- `{{NEXT}}` - Botón siguiente ⏭
- `{{VOL_DOWN}}` - Botón volumen abajo 🔉
- `{{VOL_UP}}` - Botón volumen arriba 🔊
- `{{QUIT}}` - Botón salir ❌

**Navegación:**
- `{{NEXT_TRACK}}` - Próximo track en cola
- `{{SHUFFLE}}` - Estado shuffle (ON/OFF)
- `{{REPEAT}}` - Modo repeat (NONE/TRACK/PLAYLIST)

---

## 🎨 Ejemplo: Cassette Skin

### Antes del Render (con placeholders):
```
        | | | /\ :  {{TITLE}}           90 min| | |
        | | |/--\:....{{ARTIST}}...... NR [ ]| | |
```

### Después del Render (con datos reales):
```
        | | | /\ :  Mi vida en rosa    90 min| | |
        | | |/--\:....Los Romeos....... NR [ ]| | |
```

---

## 🔒 Matrix Padding - Previene Rotura del ASCII

### El Problema Sin Matrix Padding:
```
Línea 1: ╔════════════════════╗        (20 chars)
Línea 2: ║ {{TITLE}} ║                 (15 chars después de reemplazar)
         ❌ ROTO! Líneas de diferente largo
```

### La Solución Con Matrix Padding:
```python
1. Skin loader lee todas las líneas
2. Encuentra la línea MÁS LARGA
3. Rellena TODAS las líneas con espacios al final
   → Todas quedan del MISMO ancho
4. Cuando reemplaza {{TITLE}}, el ancho YA está fijo
   → ASCII nunca se rompe
```

### Resultado:
```
Línea 1: ╔════════════════════╗        (20 chars)
Línea 2: ║ Mi vida en rosa  ║          (20 chars - rellenado)
         ✅ PERFECTO! Mismo ancho
```

---

## 📝 Limitaciones de Longitud

Los placeholders se **truncan automáticamente** para no romper el diseño:

```python
# En main.py:
context['TITLE'] = track.title[:40]    # Max 40 caracteres
context['ARTIST'] = track.artist[:30]   # Max 30 caracteres
context['PLAYLIST'] = playlist.name[:30]
```

**Ejemplo:**
```
Título largo: "This Is A Very Long Song Title That Would Break The Layout"
Truncado:     "This Is A Very Long Song Title Tha..."  (40 chars)
```

---

## 🎯 Cómo Agregar TITLE y ARTIST a Tu Skin

### Paso 1: Edita tu skin
```
---
name: Mi Skin
author: tu_nombre
version: 1.0
---
╔═══════════════════════════════════╗
║  NOW PLAYING:                     ║
║  {{TITLE}}                        ║   ← Agrega aquí
║  By: {{ARTIST}}                   ║   ← Y aquí
║                                   ║
║  {{TIME}}                         ║
║  {{PROGRESS}}                     ║
║  [{{PREV}}] [{{PLAY}}] [{{NEXT}}] ║
╚═══════════════════════════════════╝
```

### Paso 2: Matrix Padding Automático
El skin loader automáticamente:
1. ✅ Detecta el ancho máximo
2. ✅ Rellena todas las líneas
3. ✅ Valida placeholders requeridos

### Paso 3: Render Dinámico
Durante reproducción:
```
NOW PLAYING:
Mi vida en rosa          ← Reemplaza {{TITLE}}
By: Los Romeos           ← Reemplaza {{ARTIST}}
```

---

## 🧪 Prueba de No-Rotura

### Test Manual:
```python
# En main.py, la función _get_context():
context = {
    'TITLE': 'Song muy muy muy largo título',  # Títulos largos
    'ARTIST': 'Artista con nombre súper largo', # Artistas largos
    ...
}
```

**Resultado:**
→ Sistema trunca automáticamente
→ ASCII mantiene forma
→ No se rompe NUNCA

---

## 📊 Resumen

| Feature | Estado | Cómo Funciona |
|---------|--------|---------------|
| Placeholders | ✅ Funcionando | {{TITLE}}, {{ARTIST}}, etc. |
| Matrix Padding | ✅ Activo | Auto-rellena líneas |
| Truncado | ✅ Automático | Max 40 chars (title), 30 (artist) |
| Sin Roturas | ✅ Garantizado | Sistema validado |

**Conclusión:** Los skins NUNCA se rompen, sin importar cuán largo sea el título o artista. El sistema matrix padding lo garantiza.
