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

YTBMusic soporta **dos modos** de fondos:

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

### 3. Gradiente Animado (Demoscene)
Efecto "copper bar" con barrido de colores animado.

```json
{
  "name": "Demoscene Copper",
  "mode": "gradient",
  "direction": "vertical",
  "colors": [
    "black",
    "dark blue",
    "dark cyan",
    "light cyan",
    "white",
    "light cyan",
    "dark cyan",
    "dark blue"
  ],
  "speed": 0.12,
  "band_height": 4,
  "fg": "white"
}
```

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

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `mode` | string | `"gradient"` para activar modo demoscene |
| `direction` | string | `"vertical"` o `"horizontal"` |
| `colors` | array | Lista de colores para el gradiente |
| `speed` | number | Segundos entre frames de animación (0.08-0.5) |
| `band_height` | number | Líneas por banda de color (2-8) |

---

## 🎨 Colores Disponibles

urwid soporta estos colores básicos:

| Color | Visualización |
|-------|--------------|
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

## 💡 Ejemplos Predefinidos

### Classic Black (Sólido)
```json
{
  "name": "Classic Black",
  "bg": "black",
  "fg": "white"
}
```

### Ocean Cycle (Transición)
```json
{
  "name": "Ocean Cycle",
  "bg": "dark blue",
  "fg": "light cyan",
  "palette": [
    {"bg": "dark cyan", "fg": "white"},
    {"bg": "light blue", "fg": "black"}
  ],
  "transition_sec": 6
}
```

### Demoscene Fire (Gradiente)
```json
{
  "name": "Demoscene Fire",
  "mode": "gradient",
  "direction": "vertical",
  "colors": [
    "black",
    "dark red",
    "light red",
    "yellow",
    "white",
    "yellow",
    "light red"
  ],
  "speed": 0.08,
  "band_height": 5,
  "fg": "black"
}
```

---

## 🎹 Controles

| Tecla | Acción |
|:-----:|--------|
| **`B`** | Ciclar al siguiente fondo (en player) |
| **Menú → Seleccionar Fondo** | Elegir fondo desde modal |

---

## 🛠 Tips

- **Contraste**: Usá `fg` claro con `bg` oscuro (o viceversa)
- **Transiciones suaves**: `transition_sec` entre 5-15 segundos
- **Gradientes fluidos**: `speed` entre 0.1-0.2, `band_height` 3-5
- **Paleta ping-pong**: Para gradientes, repetí colores en reversa para loops suaves:
  ```json
  "colors": ["A", "B", "C", "B", "A"]  // en vez de ["A", "B", "C"]
  ```

---

## 📂 Fondos Incluidos

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `classic_black.json` | Sólido | Negro clásico |
| `terminal_green.json` | Sólido | Verde terminal retro |
| `soft_blue.json` | Transición | Azul suave con cyan |
| `dusk_orange.json` | Transición | Atardecer naranja |
| `ocean_cycle.json` | Transición | Océano multi-color |
| `sunset_cycle.json` | Transición | Puesta de sol |
| `demoscene_copper.json` | Gradiente | Copper bar azul/cyan |
| `demoscene_fire.json` | Gradiente | Llamas rojo/amarillo |

---

## 🎮 Inspiración Demoscene

Los gradientes están inspirados en los efectos "raster bar" y "copper bar" de las demos de **Commodore 64** y **Amiga**. Estos efectos creaban barridos de color animados manipulando la paleta durante el escaneo de video.

```
┌──────────────────────────────┐
│  ████████████████████████████│  ← dark blue
│  ████████████████████████████│  ← dark cyan
│  ████████████████████████████│  ← light cyan
│  ████████████████████████████│  ← white (centro)
│  ████████████████████████████│  ← light cyan
│  ████████████████████████████│  ← dark cyan
│  ████████████████████████████│  ← dark blue
└──────────────────────────────┘
       ↓ animación ↓
```

---

## ✨ Compartí tu fondo

¿Creaste un fondo genial? Hacé un PR al repo para agregarlo!
