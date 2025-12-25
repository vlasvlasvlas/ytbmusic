# 🖼️ Guía de Fondos Personalizados

Crea fondos de color y efectos visuales para el canvas del reproductor.

---

## ⚡ Quick Start

1. Crea un archivo en `backgrounds/` (ej: `myfondo.json`)
2. Pega este contenido:

```json
{
  "name": "Mi Fondo",
  "bg": "dark blue",
  "fg": "white",
  "alt_bg": "dark cyan",
  "transition_sec": 8
}
```

3. Ejecuta `./run.sh`, entra al player y presiona **'B'** para ciclar fondos.

---

## 📐 Tipos de Fondos

YTBMusic soporta **tres modos** de fondos:

### 1. Fondo Sólido (Simple)
Un color de fondo estático.

```json
{
  "name": "Terminal Green",
  "bg": "dark green",
  "fg": "light green"
}
```

### 2. Fondo con Transición (Cycling)
Alterna entre colores cada N segundos.

```json
{
  "name": "Soft Blue",
  "bg": "dark blue",
  "fg": "white",
  "alt_bg": "dark cyan",
  "transition_sec": 8
}
```

### 3. 🌈 Gradiente Animado (Demoscene)

Efectos estilo **copper bar** de Commodore/Amiga con patrones de onda y transiciones suaves.

```json
{
  "name": "Demoscene Copper",
  "mode": "gradient",
  "pattern": "wave_sine",
  "direction": "vertical",
  "colors": [
    "black", "dark blue", "dark cyan", "light cyan",
    "white", "light cyan", "dark cyan", "dark blue"
  ],
  "speed": 0.10,
  "step_size": 0.7,
  "wave_amplitude": 1.8,
  "wave_frequency": 0.8,
  "phase_shift": 0.04,
  "color_spread": 1.2,
  "smoothness": 2,
  "fg": "white"
}
```

---

## 🎨 Patrones de Onda (Demoscene)

| Patrón | Descripción | Uso recomendado |
|--------|-------------|-----------------|
| `wave_sine` | Onda senoidal suave | Copper bars clásicos, océano |
| `wave_triangle` | Ping-pong lineal | Neon, strobo controlado |
| `wave_sawtooth` | Barrido + reset | Matrix, cascadas |
| `plasma` | Ondas superpuestas | Psicodélico, aurora, lava |
| `radial` | Anillos desde centro | Túnel, hipnótico |

---

## 📝 Referencia de Campos

### Campos comunes

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | string | Nombre visible en el selector |
| `fg` | string | Color de texto (foreground) |
| `bg` | string | Color de fondo principal (background) |

### Campos para transiciones

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `alt_bg` | string | Color alternativo para transición |
| `transition_sec` | number | Segundos entre cambios de color |
| `palette` | array | Lista de colores adicionales (opcional) |

### Campos para gradientes (mode: "gradient")

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `mode` | string | - | `"gradient"` para activar modo demoscene |
| `pattern` | string | `wave_sine` | Tipo de patrón: `wave_sine`, `wave_triangle`, `wave_sawtooth`, `plasma`, `radial` |
| `direction` | string | `vertical` | Dirección: `vertical`, `horizontal`, `diagonal` |
| `angle` | number | `45` | Ángulo para dirección diagonal (0-360°) |
| `colors` | array | - | Lista de colores para el gradiente |
| `speed` | number | `0.12` | Segundos entre frames (menor = más rápido) |
| `step_size` | number | `1.0` | Cuánto avanza por frame (0.5-3.0) |
| `band_height` | number | `3` | Líneas por banda de color |
| `wave_amplitude` | number | `1.5` | Intensidad de la onda (0.5-5.0) |
| `wave_frequency` | number | `1.0` | Períodos por pantalla (0.5-3.0) |
| `phase_shift` | number | `0.05` | Desfase por línea - crea efecto cascada (0-0.5) |
| `color_spread` | number | `1.0` | Cuánto "estira" los colores (0.5-3.0) |
| `smoothness` | number | `1` | Pasos de interpolación entre colores (1-5) |

---

## 🎹 Controles

| Tecla | Acción |
|:-----:|--------|
| **`B`** | Ciclar al siguiente fondo (en player) |
| **Menú → Seleccionar Fondo** | Elegir fondo desde modal |

---

## 🎮 Fondos Demoscene Incluidos

| Archivo | Patrón | Descripción |
|---------|--------|-------------|
| `demoscene_copper.json` | `wave_sine` | Copper bar azul/cyan clásico |
| `demoscene_fire.json` | `wave_sine` | Llamas orgánicas |
| `demoscene_plasma.json` | `plasma` | Plasma psicodélico multicolor |
| `demoscene_rainbow.json` | `wave_sine` | Arcoíris ondulante |
| `demoscene_tunnel.json` | `radial` | Anillos expandiéndose |
| `demoscene_aurora.json` | `plasma` | Aurora boreal |
| `demoscene_neon.json` | `wave_triangle` | Neon rápido magenta/cyan |
| `demoscene_lava.json` | `plasma` | Lava lamp orgánico |
| `demoscene_matrix.json` | `wave_sawtooth` | Cascada verde estilo Matrix |
| `demoscene_subtle.json` | `wave_sine` | Suave, baja intensidad |

### Fondos estáticos/cycling

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `classic_black.json` | Sólido | Negro clásico |
| `terminal_green.json` | Sólido | Verde terminal retro |
| `soft_blue.json` | Transición | Azul suave con cyan |
| `dusk_orange.json` | Transición | Atardecer naranja |
| `ocean_cycle.json` | Transición | Océano multi-color |
| `sunset_cycle.json` | Transición | Puesta de sol |

---

## 💡 Tips para Efectos Psicodélicos

### 🌀 Plasma intenso
```json
{
  "pattern": "plasma",
  "wave_amplitude": 2.5,
  "phase_shift": 0.08,
  "color_spread": 1.8,
  "colors": ["dark magenta", "dark blue", "light cyan", "yellow", "light red"]
}
```

### 🌊 Ondas suaves tipo océano
```json
{
  "pattern": "wave_sine",
  "speed": 0.15,
  "step_size": 0.5,
  "wave_amplitude": 1.0,
  "phase_shift": 0.02
}
```

### ⚡ Strobo/Neon rápido
```json
{
  "pattern": "wave_triangle",
  "speed": 0.05,
  "step_size": 2.0,
  "smoothness": 1
}
```

### 💫 Cascada tipo Matrix
```json
{
  "pattern": "wave_sawtooth",
  "phase_shift": 0.12,
  "step_size": 2.0,
  "wave_frequency": 2.0
}
```

### 🎯 Túnel hipnótico
```json
{
  "pattern": "radial",
  "wave_frequency": 2.0,
  "step_size": 1.5
}
```

---

## 🛠 Guía de Parámetros

### Velocidad y movimiento
- **`speed`**: Tiempo entre frames. Menor = más rápido. Rango típico: `0.05` (rápido) a `0.20` (lento)
- **`step_size`**: Cuánto avanza cada frame. Mayor = movimiento más notorio

### Forma de la onda
- **`wave_amplitude`**: Altura de la onda. Mayor = más dramático
- **`wave_frequency`**: Cuántas ondas por pantalla. Mayor = más repeticiones

### Efecto cascada
- **`phase_shift`**: Desfase entre líneas. Mayor = efecto de "ola bajando". Valores típicos: `0.02` (sutil) a `0.12` (intenso)

### Colores
- **`color_spread`**: Cuánto "estira" cada color. Mayor = transiciones más largas
- **`smoothness`**: Duplica colores para transiciones más suaves. `1` = original, `3` = muy suave

### Paleta ping-pong
Para loops seamless, incluí colores en reversa:
```json
"colors": ["A", "B", "C", "D", "C", "B"]  // D en el centro
```

---

## 🎨 Colores Disponibles

urwid soporta 16 colores básicos:

| Color | Visualización |
|-------|--------------:|
| `black` | ██ Negro |
| `dark red` | ██ Rojo oscuro |
| `dark green` | ██ Verde oscuro |
| `brown` | ██ Marrón/Naranja |
| `dark blue` | ██ Azul oscuro |
| `dark magenta` | ██ Magenta oscuro |
| `dark cyan` | ██ Cyan oscuro |
| `light gray` | ██ Gris claro |
| `dark gray` | ██ Gris oscuro |
| `light red` | ██ Rojo claro |
| `light green` | ██ Verde claro |
| `yellow` | ██ Amarillo |
| `light blue` | ██ Azul claro |
| `light magenta` | ██ Magenta claro |
| `light cyan` | ██ Cyan claro |
| `white` | ██ Blanco |

---

## 🎬 Inspiración Demoscene

Los gradientes están inspirados en los efectos **raster bar** y **copper bar** de las demos de **Commodore 64** y **Amiga**. Estos efectos creaban barridos de color animados manipulando la paleta durante el escaneo de video.

```
┌──────────────────────────────┐
│  ████████████████████████████│  ← dark blue     ↑
│  ████████████████████████████│  ← dark cyan     │
│  ████████████████████████████│  ← light cyan    │ animación
│  ████████████████████████████│  ← white (pico)  │
│  ████████████████████████████│  ← light cyan    │
│  ████████████████████████████│  ← dark cyan     ↓
│  ████████████████████████████│  ← dark blue
└──────────────────────────────┘
```

El patrón **plasma** emula el efecto clásico de demos usando múltiples ondas senoidales superpuestas:

```
plasma = sin(x) + sin(y) + sin(x + y + time)
```

---

## ✨ Compartí tu fondo

¿Creaste un fondo genial? Hacé un PR al repo para agregarlo!
