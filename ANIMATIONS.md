# Cómo crear animaciones para YTBMusic

Guía para crear visualizaciones ASCII personalizadas que se muestran en el footer del reproductor.

---

## Ubicación

Tus archivos de animación deben guardarse en la carpeta `animations/` con extensión `.txt`.

---

## Estructura del Archivo

Cada archivo consta de dos partes:
1. **Metadata (Frontmatter)**: Configuración en formato YAML.
2. **Frames**: Los cuadros de la animación separados por marcadores `FRAME_N:`.

### Ejemplo Básico (`simple_wave.txt`)

```yaml
---
name: Simple Wave
author: Tu Nombre
fps: 5
width: 4
height: 3
---
FRAME_1:
 ∿ ∿
∿ ∿ 
 ∿ ∿

FRAME_2:
∿ ∿ 
 ∿ ∿
∿ ∿ 
```

---

## Explicación de Campos

### Metadata
- `name`: Nombre que aparecerá en la interfaz.
- `author`: Tu nombre.
- `fps`: Cuadros por segundo (velocidad). Recomendado: 5-10.
- `width`: Ancho del patrón de tu animación (ver Dynamic Tiling abajo).
- `height`: **Debe ser 3**. El footer tiene una altura fija de 3 líneas.

### Frames
- Usa `FRAME_1:`, `FRAME_2:`, etc.
- Deja una línea en blanco entre el marcador y el dibujo si lo deseas, pero el contenido debe ser consecutivo.
- El sistema rotará entre los frames definidos.

---

## Dynamic Tiling (Repetición Automática)

Para asegurar que tu animación llene pantallas de cualquier tamaño (desde laptops hasta monitores ultrawide), el sistema usa **Dynamic Tiling**.

### Cómo funciona
1. Creas un **patrón pequeño** (ej: 4, 8 o 10 caracteres de ancho).
2. El sistema repetirá ese patrón horizontalmente hasta llenar todo el ancho de la terminal.

### Recomendación
Diseña patrones que sean "tileables" (que el final conincida con el principio) para que no se noten los cortes.

#### Buen ejemplo (Tileable):
```
 █▄  ▄█ 
 ██  ██ 
 ██  ██ 
```
Si lo repites (` █▄  ▄█  █▄  ▄█ ...`) se ve continuo.

#### Mal ejemplo (No tileable):
```
[ ---- ]
```
Al repetirlo quedaría `[ ---- ][ ---- ]`, lo cual puede ser intencional o no.

---

## Controles en la App

- **`A`**: Activar / Desactivar animaciones (Toggle).
- **`V`**: Cambiar a la siguiente animación disponible (Cycle).
