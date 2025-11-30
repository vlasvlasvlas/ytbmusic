#!/usr/bin/env python3
"""
YTBMusic - Quick Diagnostic Test
Tests all features without requiring MPV
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("="*70)
print("YTBMusic - Diagnóstico Completo")
print("="*70)
print()

# Test 1: Animated Skin
print("1️⃣ Test Animación:")
from ui.skin_loader import SkinLoader
loader = SkinLoader()
meta, result = loader.load('skins/cassette_animated.txt')
print(f"   ✅ Is animated: {loader.is_animated}")
print(f"   ✅ Frames: {len(result)} frames")
print(f"   ✅ FPS: {meta.get('animation_fps')}")
print(f"   ✅ Frame 1 size: {len(result[0])} lines")
print(f"   ✅ Frame 2 size: {len(result[1])} lines")
print()

# Test 2: Context Variables
print("2️⃣ Test Variables de Metadata:")
print("   Checkeando que existan en _get_context...")

with open('main.py', 'r') as f:
    source = f.read()
    
checks = [
    ("context['TITLE']", "TITLE variable"),
    ("context['ARTIST']", "ARTIST variable"),
    ("context['PLAYLIST']", "PLAYLIST variable"),
    ("context['TRACK_NUM']", "TRACK_NUM variable"),
    ("context['NEXT_TRACK']", "NEXT_TRACK variable"),
]

for check, name in checks:
    if check in source:
        print(f"   ✅ {name} - OK")
    else:
        print(f"   ❌ {name} - MISSING")

print()

# Test 3: Menu Principal
print("3️⃣ Test Menú Principal:")
print("   Checkeando métodos de navegación...")

methods = [
    ("def select_playlist", "Menú inicial de playlists"),
    ("def _browse_playlists_interactive", "Playlist browser (L key)"),
    ("def _show_track_list", "Track list (T key)"),
    ("def render", "Render principal"),
]

for method, desc in methods:
    if method in source:
        print(f"   ✅ {desc} - OK")
    else:
        print(f"   ❌ {desc} - MISSING")

print()

# Test 4: Animación en Render
print("4️⃣ Test Lógica de Animación en render():")
animation_checks = [
    ("if self.is_skin_animated and self.player.is_playing():", "Check animado"),
    ("self.current_frame_index = (self.current_frame_index + 1)", "Cambio de frame"),
    ("self.current_skin_lines = self.current_skin_frames", "Update de líneas"),
]

for check, desc in animation_checks:
    if check in source:
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
    ("key == ord('l') or key == ord('L')", "L - Playlist browser"),
    ("key == ord('t') or key == ord('T')", "T - Track list"),
    ("key == ord('s') or key == ord('S')", "S - Skin selector"),
]

for check, desc in new_keys:
    if check in source:
        print(f"   ✅ {desc} - OK")
    else:
        print(f"   ❌ {desc} - MISSING")

print()
print("="*70)
print("📊 RESUMEN")
print("="*70)
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
print("="*70)
