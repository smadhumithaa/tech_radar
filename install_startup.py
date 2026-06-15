"""
install_startup.py — registers TechRadar to run on Windows login
using the Windows Task Scheduler (no admin rights needed for current user).

Run once:  python install_startup.py
Remove:    python install_startup.py --remove
"""

import sys
import os
import subprocess
from pathlib import Path

TASK_NAME = "TechRadar_AutoStart"
APP_DIR   = Path(__file__).parent
MAIN_PY   = APP_DIR / "main.py"


def install():
    python_exe = sys.executable
    script     = str(MAIN_PY)

    # Build schtasks command — runs at login for current user, hidden window
    cmd = [
        "schtasks", "/create",
        "/tn",  TASK_NAME,
        "/tr",  f'"{python_exe}" "{script}"',
        "/sc",  "ONLOGON",
        "/ru",  os.environ.get("USERNAME", ""),
        "/rl",  "LIMITED",
        "/f",                          # force overwrite if exists
        "/it",                         # interactive (shows tray icon)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ TechRadar registered to run on every Windows login.")
        print(f"   Task name : {TASK_NAME}")
        print(f"   Script    : {script}")
        print(f"   Python    : {python_exe}")
    else:
        print(f"❌ Failed to register:\n{result.stderr}")
        print("\nAlternative: manually add to Windows Startup folder:")
        startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
        print(f"  Place a .bat file in: {startup}")
        print(f"  Contents: start /min \"\" \"{python_exe}\" \"{script}\"")


def remove():
    result = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"✅ TechRadar removed from startup.")
    else:
        print(f"❌ Could not remove task:\n{result.stderr}")


def create_startup_bat():
    """Alternative: drop a .bat in the Startup folder (always works, no admin)."""
    python_exe = sys.executable
    script     = str(MAIN_PY)
    startup    = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
    bat_path   = startup / "TechRadar.bat"

    bat_content = f'@echo off\nstart /min "" "{python_exe}" "{script}"\n'
    bat_path.write_text(bat_content)
    print(f"✅ Startup .bat created at:\n   {bat_path}")


if __name__ == "__main__":
    if "--remove" in sys.argv:
        remove()
    elif "--bat" in sys.argv:
        create_startup_bat()
    else:
        install()
        print("\nTip: if Task Scheduler fails, run:  python install_startup.py --bat")
