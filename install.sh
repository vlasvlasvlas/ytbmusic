#!/usr/bin/env bash

set -e

echo "========================================="
echo "   ytbmusic — Installation Script"
echo "========================================="

OS=$(uname -s)
echo "Detected OS: $OS"
echo

# ---------------------------------------------------------
# Create virtual environment (./venv) and activate it
# ---------------------------------------------------------
if [ ! -d "venv" ]; then
    echo "Creating virtual environment in ./venv ..."
    python3 -m venv venv
else
    echo "Virtual environment already exists at ./venv"
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate
echo "✓ venv active: $(python3 --version)"

echo
# ---------------------------------------------------------
# Install yt-dlp (latest official binary)
# ---------------------------------------------------------
YTDLP_PATH="/usr/local/bin/yt-dlp"
if command -v yt-dlp >/dev/null 2>&1; then
    echo "yt-dlp already present at $(command -v yt-dlp)"
else
    echo "Installing yt-dlp binary..."
    curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
        -o yt-dlp
    chmod +x yt-dlp
    echo "Copying yt-dlp to /usr/local/bin (requires sudo)..."
    sudo mv yt-dlp "$YTDLP_PATH"
    if [ -f "$YTDLP_PATH" ]; then
        echo "✓ yt-dlp installed at $YTDLP_PATH"
    else
        echo "✗ Failed to install yt-dlp"
    fi
fi

echo
# ---------------------------------------------------------
# VLC check (prefer Homebrew arm64)
# ---------------------------------------------------------
detect_vlc_arch() {
    local lib_path="$1"
    if [ -f "$lib_path" ]; then
        file "$lib_path" | grep -qi "arm64" && return 0
    fi
    return 1
}

if command -v brew >/dev/null 2>&1; then
    BREW_PREFIX="$(brew --prefix)"
    BREW_LIBVLC="$BREW_PREFIX/lib/libvlc.dylib"
    APP_LIBVLC="/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib"

    echo "Checking VLC (Homebrew arm64 preferred)..."
    # Try to ensure we have an arm64 VLC; if an old x86 app is present, force-reinstall
    if [ -f "$APP_LIBVLC" ] && ! detect_vlc_arch "$APP_LIBVLC"; then
        echo "⚠️  Detected x86_64 VLC at $APP_LIBVLC; reinstalling arm64 via Homebrew..."
        brew uninstall --cask vlc || true
        brew install --cask vlc || brew reinstall --cask --force vlc || true
    fi

    if [ ! -f "$APP_LIBVLC" ]; then
        echo "Installing VLC via Homebrew..."
        brew install --cask vlc || brew reinstall --cask --force vlc || true
    fi

    # Prefer brew prefix if it ships libvlc
    if detect_vlc_arch "$BREW_LIBVLC"; then
        export PYTHON_VLC_LIB_PATH="$BREW_LIBVLC"
        export VLC_PLUGIN_PATH="$BREW_PREFIX/lib/vlc/plugins"
        export DYLD_LIBRARY_PATH="$BREW_PREFIX/lib:${DYLD_LIBRARY_PATH}"
        echo "✓ Using libvlc at $BREW_LIBVLC"
    elif detect_vlc_arch "$APP_LIBVLC"; then
        export PYTHON_VLC_LIB_PATH="$APP_LIBVLC"
        export VLC_PLUGIN_PATH="/Applications/VLC.app/Contents/MacOS/plugins"
        export DYLD_LIBRARY_PATH="/Applications/VLC.app/Contents/MacOS/lib:${DYLD_LIBRARY_PATH}"
        echo "✓ Using libvlc at $APP_LIBVLC"
    else
        echo "❌ Could not find arm64 libvlc. Please remove /Applications/VLC.app and run: brew install --cask vlc"
        exit 1
    fi
else
    if command -v vlc >/dev/null 2>&1 || [ -d "/Applications/VLC.app" ]; then
        echo "✓ VLC found (non-Homebrew). Ensure it's arm64 on Apple Silicon."
    else
        echo "VLC not found. Please install VLC (sudo apt install vlc / dnf / pacman or download)."
    fi
fi

echo
# ---------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------
echo "Installing Python requirements..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✓ Python deps installed (venv)"
else
    echo "requirements.txt not found — skipping Python deps"
fi

echo
# ---------------------------------------------------------
# Final message
# ---------------------------------------------------------
echo "========================================="
echo " Installation Complete!"
echo " You can now run: ./run.sh"
echo " Next steps:"
echo "   1) source venv/bin/activate"
echo "   2) ./run.sh   # or python3 main.py"
echo "========================================="
