"""
NWN Log Analyzer - Installer
-----------------------------
Run this once after downloading the repository. It will:
1. Check for Python (guides the user to install it if missing - only needed
   for building from source; end users running the packaged .exe skip this).
2. Ask the user to confirm/set the folder where their log files live
   (e.g. the NWN client's "logs" folder).
3. Save that folder + default character list into a config file used
   by the GUI app every time it launches.
4. Optionally create a desktop shortcut to the packaged .exe (Windows only).

Usage:
    python install.py
"""

import os
import json
import platform

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"),
    ".nwn_log_analyzer_config.json")

DEFAULT_CHARACTERS = [
    "Rayna Ralien", "Selkie Smoothhand", "Pony (PM)",
    "Merryway Markham", "Crab Apples", "Klanita Brina"
]


def prompt(msg, default=None):
    suffix = " [{}]".format(default) if default else ""
    val = input("{}{}: ".format(msg, suffix)).strip()
    return val if val else default


def main():
    print("=" * 60)
    print(" NWN Combat Log Analyzer - Setup")
    print("=" * 60)

    guessed = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "Neverwinter Nights",
        "logs")
    if not os.path.isdir(guessed):
        guessed = os.getcwd()

    log_dir = prompt(
        "Enter the folder where your log files are stored",
        guessed)
    while not os.path.isdir(log_dir):
        print("That folder does not exist.")
        log_dir = prompt("Enter a valid folder path", guessed)

    use_defaults = prompt("Use the default character roster? (y/n)", "y")
    if use_defaults.lower().startswith("y"):
        characters = DEFAULT_CHARACTERS
    else:
        print("Enter character names one at a time. Leave blank to finish.")
        characters = []
        while True:
            name = input("  Character name: ").strip()
            if not name:
                break
            characters.append(name)
        if not characters:
            characters = DEFAULT_CHARACTERS

    config = {"default_log_dir": log_dir, "characters": characters}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("\nConfiguration saved to: {}".format(CONFIG_PATH))
    print("Default log folder: {}".format(log_dir))
    print("Tracked characters: {}".format(", ".join(characters)))

    if platform.system() == "Windows":
        create_shortcut = prompt(
            "Create a desktop shortcut to the app? (y/n)", "y")
        if create_shortcut.lower().startswith("y"):
            _create_windows_shortcut()

    print("\nSetup complete. You can now launch 'NWN_Log_Analyzer.exe'")
    print("(or run 'python nwn_gui_app.py' if using the source version).")


def _create_windows_shortcut():
    try:
        import winshell
        from win32com.client import Dispatch
        desktop = winshell.desktop()
        exe_path = os.path.join(os.getcwd(), "NWN_Log_Analyzer.exe")
        if not os.path.exists(exe_path):
            print("Note: NWN_Log_Analyzer.exe not found in "
                  "current folder yet.")
            print("Build it first with build_exe.py, then "
                  "re-run this installer.")
            return
        shortcut_path = os.path.join(desktop, "NWN Log Analyzer.lnk")
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = exe_path
        shortcut.WorkingDirectory = os.getcwd()
        shortcut.save()
        print("Desktop shortcut created.")
    except ImportError:
        print("Skipping shortcut creation (optional packages "
              "'winshell'/'pywin32' not installed).")
        print("You can pin the .exe to your taskbar manually instead.")


if __name__ == "__main__":
    main()
