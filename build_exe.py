"""
Build a standalone Windows executable for HaruxSky GUI.

Usage:
    pip install -e ".[build]"
    python build_exe.py

This will produce dist/HaruxSky/HaruxSky.exe (and supporting files).
The resulting folder can be zipped and distributed as a "real program".
"""

import PyInstaller.__main__
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.resolve()

def build():
    print("Building HaruxSky standalone executable...")

    # Clean old spec to avoid stale entry point (e.g. old gui.py)
    spec_file = PROJECT_ROOT / "HaruxSky.spec"
    if spec_file.exists():
        spec_file.unlink()

    # Use a clean launcher to avoid relative import issues in the bundle
    entry_script = str(PROJECT_ROOT / "haruxsky_launcher.py")

    PyInstaller.__main__.run([
        entry_script,
        "--name", "HaruxSky",
        "--onefile",          # single exe (easier for users)
        "--windowed",         # no console window (pure GUI app)
        "--clean",
        "--noconfirm",
        f"--distpath={PROJECT_ROOT / 'dist'}",
        f"--workpath={PROJECT_ROOT / 'build'}",
        f"--specpath={PROJECT_ROOT}",
        f"--paths={PROJECT_ROOT / 'src'}",   # so it finds the haruxsky package
        # Include data files if needed (icons, etc.)
        # "--add-data", f"{PROJECT_ROOT / 'examples'}:examples",
        # Hidden imports that PyInstaller sometimes misses
        "--hidden-import", "customtkinter",
        "--hidden-import", "yaml",
        "--hidden-import", "pydantic",
        "--hidden-import", "openai",
        "--hidden-import", "atproto",
        "--hidden-import", "haruxsky",
        "--hidden-import", "haruxsky.gui",
        "--hidden-import", "haruxsky.config",
        "--hidden-import", "haruxsky.llm",
        "--hidden-import", "haruxsky.bsky",
        "--hidden-import", "haruxsky.poster",
        "--hidden-import", "haruxsky.engager",
        "--hidden-import", "haruxsky.utils",
    ])

    print("\nBuild complete!")
    print(f"Executable is in: {PROJECT_ROOT / 'dist' / 'HaruxSky.exe'}")
    print("You can zip the dist folder and distribute it.")


if __name__ == "__main__":
    build()
