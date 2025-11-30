# 🎵 YTBMusic vs Winamp - Gap Analysis

## 🏆 Winamp Features Comparison

### ✅ **Lo Que YA Tenemos (Winamp-like)**

| Feature | YTBMusic | Winamp | Estado |
|---------|----------|--------|--------|
| Play/Pause/Stop | ✅ Space | ✅ | Completo |
| Next/Previous | ✅ N/P | ✅ | Completo |
| Volume Control | ✅ +/- | ✅ | Completo |
| Seek | ✅ ←/→ | ✅ | Completo |
| Shuffle | ✅ Z | ✅ | Completo |
| Repeat Modes | ✅ R | ✅ | Completo |
| Playlist Support | ✅ JSON | ✅ M3U/PLS | Completo |
| Skins | ✅ ASCII | ✅ WSZ | Completo |
| Progress Bar | ✅ | ✅ | Completo |
| Time Display | ✅ | ✅ | Completo |
| Track Info | ✅ | ✅ | Completo |

---

### ❌ **Lo Que FALTA (Winamp tenía)**

#### 🔴 **CRÍTICO (Muy útil para usuarios):**

1. **Queue System (Cola de Reproducción)**
   - Winamp: Podías agregar tracks a "queue" sin interrumpir reproducción
   - YTBMusic: ❌ No existe
   - **Utilidad:** 9/10 - Súper útil para "quiero escuchar esto después"
   - **Implementación:** Media complejidad

2. **Search in Playlist**
   - Winamp: `Ctrl+F` busca en playlist actual
   - YTBMusic: ❌ Tienes que scroll manual en track list
   - **Utilidad:** 8/10 - Crítico para playlists grandes
   - **Implementación:** Fácil

3. **Jump to Current Track**
   - Winamp: `Ctrl+J` centra la vista en track actual
   - YTBMusic: ❌ No existe
   - **Utilidad:** 7/10 - Útil cuando playlist es larga
   - **Implementación:** Fácil

4. **Add to Favorites/Bookmarks**
   - Winamp: Podías marcar tracks favoritos
   - YTBMusic: ❌ No existe
   - **Utilidad:** 8/10 - Para crear "best of" fácilmente
   - **Implementación:** Media

5. **Recent/History View**
   - Winamp: Veías últimos tracks reproducidos
   - YTBMusic: ✅ Logs existen, ❌ pero sin UI
   - **Utilidad:** 7/10 - "¿Cómo se llamaba esa canción?"
   - **Implementación:** Fácil (solo UI, data ya existe)

---

#### 🟡 **MEDIO (Nice to have):**

6. **Sort Playlist**
   - Winamp: Ordenar por título, artista, duración, etc.
   - YTBMusic: ❌ Orden fijo del JSON
   - **Utilidad:** 6/10 - Útil ocasionalmente
   - **Implementación:** Fácil

7. **Mini Mode**
   - Winamp: Vista compacta solo con controles esenciales
   - YTBMusic: ❌ Siempre full skin
   - **Utilidad:** 6/10 - Para ahorrar espacio en terminal
   - **Implementación:** Media

8. **Speed Control**
   - Winamp: Cambiar velocidad (0.5x - 2x)
   - YTBMusic: ❌ No existe
   - **Utilidad:** 5/10 - Útil para podcasts/audiobooks
   - **Implementación:** Fácil (mpv lo soporta)

9. **Crossfade**
   - Winamp: Transición suave entre tracks
   - YTBMusic: ❌ No existe
   - **Utilidad:** 5/10 - Experiencia más fluida
   - **Implementación:** Compleja

10. **Tag Editor**
    - Winamp: Editar metadatos (título, artista, etc.)
    - YTBMusic: ❌ No existe
    - **Utilidad:** 4/10 - Menos útil con YouTube
    - **Implementación:** Media

---

#### 🟢 **BAJA PRIORIDAD (Lujo):**

11. **Visualizer**
    - Winamp: Visualizador de audio (barras, ondas)
    - YTBMusic: ❌ No existe
    - **Utilidad:** 3/10 - Eye candy, no funcional
    - **Implementación:** Compleja (ASCII visualization)

12. **Equalizer**
    - Winamp: EQ gráfico con presets
    - YTBMusic: ❌ No existe
    - **Utilidad:** 6/10 - Útil para audiophiles
    - **Implementación:** Compleja (mpv af)

13. **Global Hotkeys**
    - Winamp: Atajos funcionan fuera de la ventana
    - YTBMusic: ❌ Solo cuando tiene focus
    - **Utilidad:** 7/10 - Conveniente
    - **Implementación:** Compleja (OS hooks)

14. **Scrobbling**
    - Winamp: Last.fm integration
    - YTBMusic: ❌ No existe
    - **Utilidad:** 5/10 - Para usuarios de Last.fm
    - **Implementación:** Media

15. **DSP Effects**
    - Winamp: Plugins de efectos (reverb, etc.)
    - YTBMusic: ❌ No existe
    - **Utilidad:** 3/10 - Nicho
    - **Implementación:** Compleja

---

## 🎯 **TOP 5 Features a Implementar (Por Impacto/Utilidad)**

### 1. 🥇 **Queue System** (Utilidad: 9/10)
```
Presionas 'A' en track list → "Add to queue"
Cola independiente de playlist
Reproduce cola primero, luego continúa playlist
```

**Por qué es crítico:**
- "Quiero escuchar X ahora pero sin cambiar mi playlist"
- Winamp's killer feature
- Flujo natural de uso

---

### 2. 🥈 **Search in Playlist** (Utilidad: 8/10)
```
Presionar '/' → Abre buscador
Tipeas "love" → Filtra a tracks con "love"
Enter → Salta a ese track
```

**Por qué es crítico:**
- Playlists grandes imposibles de navegar
- Encontrar track específico sin scroll

---

### 3. 🥉 **Favorites/Bookmarks** (Utilidad: 8/10)
```
Presionar 'F' → Mark as favorite
Ver favoritos → Tecla 'V'
Auto-genera playlist "favorites.json"
```

**Por qué es útil:**
- Descubrir nueva música y guardar las mejores
- Crear "Best Of" dinámico

---

### 4. **History View** (Utilidad: 7/10)
```
Presionar 'H' → Ver últimos 50 tracks
Seleccionar uno → Reproduce
```

**Por qué es útil:**
- "¿Cómo se llamaba esa canción que sonó hace 20 min?"
- Data ya existe en logs

---

### 5. **Speed Control** (Utilidad: 5/10 para música, 9/10 para podcasts)
```
Presionar '[' → Slower (0.75x)
Presionar ']' → Faster (1.25x)
Presionar '\\' → Reset (1.0x)
```

**Por qué es útil:**
- Podcasts a 1.5x para ahorrar tiempo
- Aprender idiomas a 0.75x
- MPV ya lo soporta nativamente

---

## 💡 **Propuesta de Implementación**

### **Fase Inmediata (1-2 horas):**
1. ✅ Speed Control - Fácil, mpv built-in
2. ✅ History View - UI para logs existentes
3. ✅ Search in Playlist - Agregar filtro a track list

### **Fase Corto Plazo (3-5 horas):**
4. ✅ Favorites System - Marcar tracks, JSON generado
5. ✅ Jump to Current - Centrar vista en track actual

### **Fase Medio Plazo (1-2 días):**
6. ✅ Queue System - Cola independiente
7. ✅ Sort Playlist - Ordenamiento temporal

### **Fase Largo Plazo (Futuro):**
8. ⏳ Equalizer - mpv audio filters
9. ⏳ Global Hotkeys - OS integration
10. ⏳ Visualizer ASCII - Análisis FFT

---

## 🎯 **Recomendación Final**

**IMPLEMENTAR AHORA (Máximo impacto, baja complejidad):**

1. **Speed Control** `[` `]` - 15 minutos
2. **History View** `H` - 30 minutos
3. **Search in Playlist** `/` - 45 minutos

**Total: 90 minutos para 3 features muy útiles de Winamp**

¿Procedemos con estas 3?
