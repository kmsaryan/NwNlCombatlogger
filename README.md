# Combat Logger

A tool for parsing Neverwinter Nights (NWN) combat logs and generating
detailed statistics on character performance, monster behavior, saving
throws, damage mitigation, and threat rolls.

---

## 1. Pre-setup (game side)

Before you can analyze anything, NWN needs to actually write combat data
to a log file. By default this is turned off.

- Open this file: `E:\Program Files\NWN Diamond\nwnplayer.ini`
- Under `[Game Options]`, add these two lines (or enable them if already present):

```ini
[Game Options]
ClientEntireChatWindowLogging=1
ClientChatLogging=1
```

- Your game will now log the chat window and server messages to:
  `E:\Program Files\NWN Diamond\logs`

- You'll see files named like this:

```cmd
nwclientLog1.txt
nwclientLog2.txt
nwclientLog3.txt
```

The log files get overwritten/rotated over time. If you want to analyze a
specific session later, copy the relevant file(s) somewhere safe under a
different name before starting a new session.

---

## 2. What this tool does

The analyzer reads one or more of these log files and produces stats on:

- Kills, total damage, and average damage per hit for your tracked
  characters.
- Monster attack bonus, estimated AC range, and average damage dealt, per
  monster type.
- Saving throws and skill checks (e.g. Fortitude Save, Tumble), broken
  down by roll range and DC range, split separately for characters and
  monsters.
- Damage resistance absorbed, damage immunity absorbed, and concealment
  events (how often and by how much attacks were foiled).
- Threat rolls, including count, max, and average per attacker.

---

## 3. Installation options

There are two ways to use this tool, depending on your comfort level.

### Option A: No-install desktop app (recommended for most users)

1. Go to the [Releases](https://github.com/kmsaryan/NwNlCombatlogger/releases) page of this repository.
2. Download `NWN_Log_Analyzer.exe` (Windows) — no Python or pip required.
3. Double-click to run. A desktop window opens with buttons and text
   boxes — no command line needed.
4. (Optional) Run `install.py` once beforehand if you want to pre-set
  your default log folder and character roster so the app opens ready
  to go every time.

### Option B: Run from source (for developers / advanced users)

Requires Python 3.9+ installed.

```cmd
pip install -r requirements.txt
python nwn_gui_frontend.py
```

---

## 4. Using the app

1. Click **Select Log File(s)** to manually pick one or more `.txt` log
   files, or click **Use Default Folder** to auto-load every
   `nwclientLogN.txt` file from your configured logs folder.
2. Edit the **Character Names** box if you want to track different
   characters than the default roster.
3. Click **Analyze**.
4. Browse results across four tabs: Character Stats, Monster Stats,
   Saving Throws, and Mitigation & Threat.

---

## 5. Building the executable (developers only)

If you've made changes to `nwn_gui_frontend.py` and want to rebuild the
distributable `.exe`:

```cmd
pip install pyinstaller
python build_exe.py
```

The output appears in `dist/NWN_Log_Analyzer.exe`. Upload that single
file to GitHub Releases — end users never need Python installed.

---

## 6. Notes

- PyInstaller builds are platform-specific (build on Windows for a
  Windows `.exe`, on macOS for a Mac app, etc.). It does not cross-compile.
- Log parsing logic is based on standard NWN combat log line formats.
  If your server uses a modified logging format, some lines may not be
  captured — check the regex patterns in `nwn_log_logic.py` if stats look
  incomplete.
