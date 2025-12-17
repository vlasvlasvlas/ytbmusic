# 🌊 Guía de Animaciones ASCII

Crea visualizaciones dinámicas que acompañen tu música en el footer del reproductor.

---

## ⚡ Quick Start

1. Crea un archivo en `animations/` (ej: `mypulse.txt`).
2. Pega este contenido:

```yaml
---
name: My Pulse
author: Me
fps: 10
width: 6
height: 3
---
FRAME_1:
• . . 
 . . .
. . • 

FRAME_2:
● • . 
 • . .
. • ● 

FRAME_3:
O ● • 
 ● • .
• ● O 
```
3. Ejecuta `./run.sh`, reproduce música y presiona **'A'**.

---

## 📐 Concepto Clave: "El Azulejo" (Tile)

No necesitas dibujar 120 caracteres de ancho. YTBMusic repetirá tu dibujo horizontalmente para llenar cualquier pantalla automáticamente.

**Tu dibujo (4 columnas):**
```
 / \ 
|   |
 \ / 
```

**Lo que ve el usuario (Pantalla infinita):**
```
 / \  / \  / \  / \  / \  / \ 
|   ||   ||   ||   ||   ||   |
 \ /  \ /  \ /  \ /  \ /  \ / 
```

> **Tip:** Diseña pensando en que "la derecha se conecta con la izquierda".

---

## 📝 Referencia de Formato

### 1. Cabecera (Metadata)
Va al principio del archivo entre `---`.

| Campo | Descripción |
|-------|-------------|
| `name` | Nombre visible en el footer. |
| `fps` | Velocidad (Frames por segundo). 8-12 es fluido. |
| `width` | El ancho exacto de tu dibujo (ej: 4, 8, 12). |
| `height`| **Siempre 3**. Es la altura fija del footer. |

### 2. Frames
Separados por el marcador `FRAME_N:`.
```
FRAME_1:
(dibujo de 3 líneas)

FRAME_2:
(dibujo de 3 líneas)
```

---

## 💡 Ideas y Ejemplos

### Idea 1: Matrix Digital
*Un flujo de datos binarios.*

```yaml
---
name: Binary Flow
fps: 8
width: 6
height: 3
---
FRAME_1:
0 1 0 
1 0 1 
0 1 0 

FRAME_2:
1 0 1 
0 1 0 
1 0 1 
```

### Idea 2: Old School Load
*Barras de carga clásicas.*

```yaml
---
name: Loading
fps: 6
width: 8
height: 3
---
FRAME_1:
 ▒▒▒▒   
 ▒▒▒▒   
 ▒▒▒▒   

FRAME_2:
   ▒▒▒▒ 
   ▒▒▒▒ 
   ▒▒▒▒ 
```

### Idea 3: Equalizer Simple
*Simulación de espectro de audio.*

```yaml
---
name: Mini EQ
fps: 10
width: 4
height: 3
---
FRAME_1:
 ▄  
 █  
 ▀  

FRAME_2:
  ▄ 
 ▄█ 
  ▀ 

FRAME_3:
 ▄▄ 
 ██ 
 ▀▀ 
```

---

## 🎹 Controles

| Tecla | Acción |
|:-----:|--------|
| **`A`** | Activar / Desactivar animación |
| **`V`** | Cambiar visual (`Next`) |

---

## 🛠 Trucos Pro
- Usa caracteres "block element" (`█ ▄ ▀ ▌ ▐ ░ ▒ ▓`) para diseños sólidos.
- Usa Braille (`⡇⣆⣀`) para detalles finos.
- Usa caracteres matemáticos (`∫ ∑ ≈ ≠ ≤`) para ondas abstractas.
- Mantén el `width` par (4, 8, 16) para que los ciclos visuales sean más fáciles de calcular mentalmente.
