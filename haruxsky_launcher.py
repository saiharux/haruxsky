"""
Launcher for the packaged HaruxSky GUI.
This allows PyInstaller to bundle it cleanly without relative import issues.
"""

import sys
from pathlib import Path

# Ensure we can import the haruxsky package when run from the bundle
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    bundle_dir = Path(sys._MEIPASS)
    sys.path.insert(0, str(bundle_dir))

from haruxsky.gui import main

if __name__ == "__main__":
    main()
