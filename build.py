import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path


def get_os_string():
    system = platform.system().lower()
    if system == "darwin":
        return "mac"
    elif system == "windows":
        return "windows"
    else:
        return "linux"


def clean_build():
    """Remove build artifacts."""
    for d in ["build", "dist"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    for f in Path(".").glob("*.spec"):
        os.remove(f)


def build():
    os_name = get_os_string()
    print(f"🏗️  Building for {os_name}...")

    # Define executable name
    exe_name = "ytbmusic"
    if os_name == "windows":
        exe_name += ".exe"

    # PyInstaller command
    # --onefile: Create a single executable
    # --name: Name of the executable
    # --clean: Clean PyInstaller cache
    cmd = [
        "pyinstaller",
        "main.py",
        "--name",
        "ytbmusic",
        "--onefile",
        "--clean",
        "--log-level",
        "WARN",
    ]

    # OS-specific adjustments
    if os_name == "windows":
        # Check for icon if exists (optional)
        if os.path.exists("icon.ico"):
            cmd.extend(["--icon", "icon.ico"])
    elif os_name == "mac":
        # Make it a windowed app? No, it's a TUI, so console is needed.
        # But we might want to ensure it runs in terminal.
        pass

    # Run PyInstaller
    subprocess.check_call(cmd)

    # Post-build: Organize File Structure
    dist_dir = Path("dist")
    final_dir = dist_dir / f"ytbmusic-{os_name}"

    # Create final directory
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir(parents=True)

    # Move executable
    src_exe = dist_dir / exe_name
    dst_exe = final_dir / exe_name
    if src_exe.exists():
        shutil.move(str(src_exe), str(dst_exe))
        print(f"✅ Executable created: {dst_exe}")
    else:
        print("❌ Build failed: Executable not found.")
        return

    # Copy external resources (skins, config template, playlists folder)
    print("📂 Copying resources...")

    # Skins
    shutil.copytree("skins", final_dir / "skins", dirs_exist_ok=True)

    # Empty Playlists folder (so user has it ready)
    (final_dir / "playlists").mkdir(exist_ok=True)

    # Cache folder (empty)
    (final_dir / "cache").mkdir(exist_ok=True)

    # Create zip archive
    archive_name = shutil.make_archive(
        str(dist_dir / f"ytbmusic-{os_name}"), "zip", str(final_dir)
    )
    print(f"📦 Archive created: {archive_name}")


if __name__ == "__main__":
    clean_build()
    build()
