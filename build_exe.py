import subprocess
import sys


def main():
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "NWN_Log_Analyzer",
        "nwn_gui_frontend.py"
    ])
    print("\n Build complete. Find the executable inside the 'dist' folder.")
    print("Upload that single file to your GitHub Releases page.")


if __name__ == "__main__":
    main()
