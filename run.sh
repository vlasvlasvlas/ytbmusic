#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎵 YTBMusic - Starting (Urwid UI + VLC)..."

if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./install.sh first."
    exit 1
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate

# On macOS/Homebrew, prefer arm64 libvlc and set plugin path
if command -v brew >/dev/null 2>&1; then
    BREW_PREFIX="$(brew --prefix)"
    BREW_LIBVLC="$BREW_PREFIX/lib/libvlc.dylib"
    APP_LIBVLC="/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib"

    if [ -f "$BREW_LIBVLC" ] && file "$BREW_LIBVLC" | grep -qi "arm64"; then
        export PYTHON_VLC_LIB_PATH="$BREW_LIBVLC"
        export VLC_PLUGIN_PATH="$BREW_PREFIX/lib/vlc/plugins"
        export DYLD_LIBRARY_PATH="$BREW_PREFIX/lib:${DYLD_LIBRARY_PATH}"
    elif [ -f "$APP_LIBVLC" ] && file "$APP_LIBVLC" | grep -qi "arm64"; then
        export PYTHON_VLC_LIB_PATH="$APP_LIBVLC"
        export VLC_PLUGIN_PATH="/Applications/VLC.app/Contents/MacOS/plugins"
        export DYLD_LIBRARY_PATH="/Applications/VLC.app/Contents/MacOS/lib:${DYLD_LIBRARY_PATH}"
        export PATH="/Applications/VLC.app/Contents/MacOS:$PATH"
    else
        echo "⚠️  libvlc arm64 not found; python-vlc will try system paths. Run ./install.sh to reinstall VLC arm64."
    fi
fi

python3 main.py
