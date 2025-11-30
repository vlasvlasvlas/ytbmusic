#!/usr/bin/env python3
"""
Quick test: Does MPV IPC player work?
"""

import sys
import time
sys.path.insert(0, '.')

print("Testing MusicPlayer with IPC...")

from core.player import MusicPlayer

# Test 1: Create player
print("1. Creating player...")
player = MusicPlayer()
time.sleep(1)
print("   ✅ Player created")

# Test 2: Play from cache
print("\n2. Playing from cache...")
cached_file = "cache/tXggyHNwO9A.m4a"
player.play(cached_file)
print(f"   State: {player.state}")
print(f"   ✅ Playing: {cached_file}")

# Test 3: Get time info
print("\n3. Checking time info...")
time.sleep(2)
info = player.get_time_info()
print(f"   Current: {info['current_formatted']}")
print(f"   Total: {info['total_formatted']}")
print(f"   Percentage: {info['percentage']:.1f}%")

if info['current_time'] > 0:
    print("   ✅ TIME IS UPDATING!")
else:
    print("   ❌ Time stuck at 0")

# Test 4: Volume
print("\n4. Testing volume...")
player.set_volume(50)
print(f"   Volume set to: {player.volume}")

# Test 5: Clean up
print("\n5. Cleaning up...")
time.sleep(1)
player.stop()
player.cleanup()
print("   ✅ Done")

print("\n" + "="*50)
print("Si viste 'TIME IS UPDATING' → Player funciona")
print("Si viste 'Time stuck at 0' → Hay problema con IPC")
print("="*50)
