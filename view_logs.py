#!/usr/bin/env python3
"""
View YTBMusic logs in real-time or tail
"""

import sys
from pathlib import Path

log_dir = Path(__file__).parent / "logs"


def view_logs(log_file="player.log", lines=50):
    """View last N lines of log file."""
    log_path = log_dir / log_file

    if not log_path.exists():
        print(f"❌ Log file not found: {log_path}")
        return

    print(f"📋 Last {lines} lines of {log_file}:")
    print("=" * 70)

    with open(log_path, "r") as f:
        all_lines = f.readlines()
        for line in all_lines[-lines:]:
            print(line.rstrip())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        lines = int(sys.argv[1])
    else:
        lines = 50

    print("\n🎵 YTBMusic - Log Viewer\n")
    view_logs("player.log", lines)

    print("\n" + "=" * 70)
    print("Para ver más: python3 view_logs.py 100")
    print("Para seguir en tiempo real: tail -f logs/player.log")
