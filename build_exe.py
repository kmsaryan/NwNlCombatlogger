"""
Build script - creates a single-file Windows/Mac/Linux executable
using PyInstaller. Run this ONCE as the developer before publishing
to GitHub Releases. End users never need to run this or have Python
installed at all - they just download the built .exe/.app/binary.

Usage:
    pip install pyinstaller
    python build_exe.py
"""

import subprocess
import sys


def main():
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "NWN_Log_Analyzer",
        "nwn_gui_app.py"
    ])
    print("\nBuild complete. Find the executable inside the 'dist' folder.")
    print("Upload that single file to your GitHub Releases page.")


if __name__ == "__main__":
    main()
