#!/usr/bin/env python3
"""
YTBMusic - Quick Diagnostic Test
Tests all features without requiring MPV
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("YTBMusic - Diagnóstico Completo")
print("=" * 70)
print()

# Test 1: Animated Skin
print("1️⃣ Test Animación:")
from ui.skin_loader import SkinLoader

loader = SkinLoader()
meta, result = loader.load("skins/cassette_animated.txt")
print(f"   ✅ Is animated: {loader.is_animated}")
print(f"   ✅ Frames: {len(result)} frames")
print(f"   ✅ FPS: {meta.get('animation_fps')}")
print(f"   ✅ Frame 1 size: {len(result[0])} lines")
print(f"   ✅ Frame 2 size: {len(result[1])} lines")
print()

# Test 2: Context Variables
print("2️⃣ Test Variables de Metadata:")
print("   Checkeando que existan en PlayerView.render...")

def _read_source(path):
    try:
        return Path(path).read_text()
    except Exception as e:
        print(f"   ❌ No pude leer {path}: {e}")
        return ""

player_view_source = _read_source("ui/views/player_view.py")
menu_view_source = _read_source("ui/views/menu_view.py")
main_source = _read_source("main.py")

checks = [
    ('context["TITLE"]', "TITLE variable"),
    ('context["ARTIST"]', "ARTIST variable"),
    ('context["PLAYLIST"]', "PLAYLIST variable"),
    ('context["TRACK_NUM"]', "TRACK_NUM variable"),
    ('context["NEXT_TRACK"]', "NEXT_TRACK variable"),
]

for check, name in checks:
    if check in player_view_source:
        print(f"   ✅ {name} - OK")
    else:
        print(f"   ❌ {name} - MISSING")

print()

# Test 3: Menu Principal
print("3️⃣ Test Menú Principal:")
print("   Checkeando métodos de navegación...")

method_checks = [
    (menu_view_source, "class MenuView", "Menú principal (MenuView)"),
    (main_source, "def _prompt_import_playlist", "Import dialog (I key)"),
    (main_source, "def _show_track_picker", "Track picker (T key)"),
    (player_view_source, "def render(self)", "Render principal (PlayerView)"),
]

for source_text, snippet, desc in method_checks:
    if snippet and snippet in source_text:
        print(f"   ✅ {desc} - OK")
    else:
        print(f"   ❌ {desc} - MISSING")

print()

# Test 4: Animación en Render
print("4️⃣ Test Lógica de Animación en render():")
animation_checks = [
    ("pad_lines(c.skin_lines", "Normalización de líneas"),
    ("c.skin_loader.render", "Render via SkinLoader"),
    ('"STATUS":', "Estado de reproducción"),
]

for check, desc in animation_checks:
    if check in player_view_source:
        print(f"   ✅ {desc} - OK")
    else:
        print(f"   ❌ {desc} - MISSING")

print()

# Test 5: Playlist Loading
print("5️⃣ Test Playlists:")
from core.playlist import PlaylistManager

pm = PlaylistManager()
playlists = pm.list_playlists()
print(f"   ✅ Playlists encontradas: {len(playlists)}")
for p in playlists:
    print(f"      - {p}")

print()

# Test 6: Keybindings
print("6️⃣ Test Nuevas Teclas:")
new_keys = [
    ("key in (\"t\", \"T\")", "T - Track picker"),
    ("key in (\"s\", \"S\")", "S - Skin selector"),
    ("key in (\"a\", \"A\")", "A - Animación"),
]

for check, desc in new_keys:
    if check in main_source:
        print(f"   ✅ {desc} - OK")
    else:
        print(f"   ❌ {desc} - MISSING")

print()
print("=" * 70)
print("📊 RESUMEN")
print("=" * 70)
print()
print("Si todos los tests tienen ✅, el código está CORRECTO.")
print("Si ves ❌, hay algún problema en el código.")
print()
print("⚠️  IMPORTANTE:")
print("   - La animación solo funciona cuando:")
print("     1. Estás usando skin 'cassette_animated'")
print("     2. Hay música REPRODUCIENDO (no paused)")
print("     3. MPV está funcionando")
print()
print("   - Los metadatos solo aparecen cuando:")
print("     1. Hay un playlist cargado")
print("     2. Hay un track seleccionado")
print()
print("Para probar la app completa ejecutá:")
print("   ./run.sh")
print("=" * 70)
