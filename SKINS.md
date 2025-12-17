# Cómo crear skins para YTBMusic

Guía para crear tus propios skins ASCII para el reproductor.

---

## Sistema de coordenadas

El skin usa un sistema de **columnas y filas** basado en caracteres:

```
         1         2         3         4         5         6         7         8
12345678901234567890123456789012345678901234567890123456789012345678901234567890
┌──────────────────────────────────────────────────────────────────────────────┐  ← Fila 1
│                                                                              │  ← Fila 2
│   Columna 4 empieza acá                                                      │  ← Fila 3
│   ↓                                                                          │  ← Fila 4
│   {{TITLE}}                                                                  │  ← Fila 5
│                                                                              │  ← Fila 6
└──────────────────────────────────────────────────────────────────────────────┘  ← Fila 7
```

### Cómo contar

- **Columnas**: De izquierda a derecha, empezando en 1
- **Filas**: De arriba a abajo, empezando en 1
- **Cada carácter** (incluyendo espacios) ocupa 1 columna
- **Máximo**: 80 columnas × 40 filas

### Ejemplo de posicionamiento

```
Columna:    1    5    10   15   20   25   30
            ↓    ↓    ↓    ↓    ↓    ↓    ↓
Fila 1:     ╔════════════════════════════════╗
Fila 2:     ║   {{TITLE}}                    ║
            ↑   ↑
            │   └── El placeholder empieza en columna 5
            └────── El borde empieza en columna 1
```

---

## Cómo funcionan los placeholders

Los placeholders son textos que se **reemplazan en tiempo real** con datos del reproductor.

### Antes (en tu archivo .txt):
```
║   {{TITLE}}                    ║
```

### Después (en pantalla):
```
║   Never Gonna Give You Up      ║
```

### Importante: Los placeholders se expanden

El placeholder `{{TITLE}}` ocupa 9 caracteres en tu archivo:
```
{{TITLE}}
123456789
```

Pero el título real puede ser más largo:
```
Never Gonna Give You Up
12345678901234567890123
       (23 caracteres)
```

**Regla**: Dejá suficiente espacio después de cada placeholder para que el texto expandido no rompa tu diseño.

### Ejemplo práctico

```
MALO (sin espacio):
║{{TITLE}}║            → ║Never Gonna Give You Up║   ← Se sale del borde!

BUENO (con espacio):
║{{TITLE}}                    ║   → ║Never Gonna Give You Up      ║   ← OK
         ^^^^^^^^^^^^^^^^^^^^
         20 espacios de reserva
```

---

## Estructura del archivo

```
---
name: Mi Skin
author: Tu Nombre
version: 1.0
---
[ASCII ART AQUÍ - máximo 80 columnas × 40 filas]
```

El header YAML (entre `---`) **no cuenta** para el límite de filas.

---

## Límites

| Límite | Valor | Qué pasa si lo excedés |
|--------|-------|------------------------|
| Columnas | 80 máx | El skin no aparece en el menú |
| Filas | 40 máx | El skin no aparece en el menú |
| Placeholders requeridos | 6 | Error al cargar |

---

## Placeholders requeridos

Tu skin **debe** incluir estos 6 placeholders (al menos una vez):

| Placeholder | Caracteres | Se reemplaza por |
|-------------|------------|------------------|
| `{{PREV}}` | 8 | `◀◀` (2 chars) |
| `{{PLAY}}` | 8 | `▶` o `⏸` (1 char) |
| `{{NEXT}}` | 8 | `▶▶` (2 chars) |
| `{{VOL_DOWN}}` | 12 | `🔉` (1-2 chars) |
| `{{VOL_UP}}` | 10 | `🔊` (1-2 chars) |
| `{{QUIT}}` | 8 | `✕` (1 char) |

---

## Placeholders opcionales

| Placeholder | Caracteres | Longitud típica del reemplazo |
|-------------|------------|-------------------------------|
| `{{TITLE}}` | 9 | 5-40 chars |
| `{{ARTIST}}` | 10 | 5-30 chars |
| `{{TIME}}` | 8 | 13 chars (`02:34 / 03:32`) |
| `{{PROGRESS}}` | 12 | 16-30 chars (`████████░░░░`) |
| `{{VOLUME}}` | 10 | 10 chars (`████████░░`) |
| `{{STATUS}}` | 10 | 7 chars (`Playing`) |
| `{{PLAYLIST}}` | 12 | 5-20 chars |
| `{{TRACK_NUM}}` | 13 | 5 chars (`3/15`) |

---

## Ejemplo paso a paso

### Paso 1: Crear el archivo

Creá un archivo en `skins/mi_skin.txt`

### Paso 2: Agregar el header

```
---
name: Mi Primer Skin
author: Tu Nombre
version: 1.0
---
```

### Paso 3: Dibujar el marco (máx 80 cols)

```
123456789012345678901234567890123456789012345678901234567890  ← Usá esta regla
╔════════════════════════════════════════════════════════╗
║                                                        ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
```

### Paso 4: Agregar placeholders con espacio

```
╔════════════════════════════════════════════════════════╗
║  {{TITLE}}                                             ║  ← 40 espacios después
║  {{ARTIST}}                                            ║
║                                                        ║
║  {{TIME}}    {{PROGRESS}}                              ║
║                                                        ║
║     [ {{PREV}} ]  [ {{PLAY}} ]  [ {{NEXT}} ]           ║
║                                                        ║
║     [ {{VOL_DOWN}} ] {{VOLUME}} [ {{VOL_UP}} ]         ║
║                                             {{QUIT}}   ║
╚════════════════════════════════════════════════════════╝
```

### Paso 5: Probar

```bash
./run.sh
# Seleccioná tu skin con A-J
```

---

## Tips

1. **Usá una regla**: Poné números `12345678901234567890...` arriba mientras diseñas
2. **Copiá template_example.txt**: Es más fácil modificar que empezar de cero
3. **Dejá 20+ espacios** después de `{{TITLE}}` y `{{ARTIST}}`
4. **Probá con títulos largos**: Algunos tracks tienen nombres de 40+ caracteres

---

## Validación automática

El loader hace esto por vos:
- ❌ Ignora skins > 80 columnas
- ❌ Ignora skins > 40 filas
- ✅ Rellena líneas cortas con espacios
- ⚠️ Muestra error si faltan placeholders requeridos

---

## Compartí tu skin

¿Creaste un skin? Hacé un PR al repo para agregarlo!.
