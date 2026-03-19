"""
ANP Setup — Cross-platform installer for the Agent Notification Protocol.

Creates the directory structure, installs the filter script, and sets up
a scheduled task to run the filter every 2 minutes.

Works on Windows (Task Scheduler), macOS (launchd), and Linux (cron).

Usage:
  python setup.py              Install everything
  python setup.py --uninstall  Remove the scheduled task (keeps data)
"""

import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path.home() / ".ai-notifications"
FILTER_SCRIPT = ROOT / "run_filter.py"
FILTER_SOURCE = Path(__file__).parent / "filter" / "run_filter.py"


# --- Directory setup ---

def setup_directories():
    """Create the ANP directory structure."""
    print(f"Creating directory structure at {ROOT}/")
    for d in ["registry", "incoming", "processing", "context", "logs"]:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
        print(f"  [OK] {d}/")


def write_config():
    """Write the global config.json."""
    config = {
        "version": "1.0",
        "pollIntervalSeconds": 120,
        "maxNotificationAgeDays": 2,
        "maxContextEntries": 50,
        "archiveEnabled": True,
        "logLevel": "info",
    }
    config_path = ROOT / "config.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print("  [OK] config.json")
    else:
        print("  [OK] config.json (already exists, kept)")


def install_filter():
    """Copy the filter script to the ANP root."""
    if FILTER_SOURCE.exists():
        shutil.copy2(FILTER_SOURCE, FILTER_SCRIPT)
        print(f"  [OK] Filter installed at {FILTER_SCRIPT}")
    else:
        print(f"  [WARN] Filter source not found at {FILTER_SOURCE}")
        print(f"         Download run_filter.py manually to {FILTER_SCRIPT}")


# --- Scheduler setup (cross-platform) ---

def get_python_path():
    """Get the full path to the Python executable."""
    return sys.executable


def setup_scheduler_windows():
    """Set up Windows Task Scheduler to run the filter every 2 minutes."""
    python = get_python_path()
    task_name = "ANP-Filter"
    command = f'"{python}" "{FILTER_SCRIPT}"'

    try:
        # /F forces overwrite if task already exists
        result = subprocess.run(
            ["schtasks", "/Create", "/SC", "MINUTE", "/MO", "2",
             "/TN", task_name, "/TR", command, "/F"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  [OK] Task Scheduler: '{task_name}' runs every 2 minutes")
        else:
            print(f"  [FAIL] Task Scheduler error: {result.stderr.strip()}")
    except FileNotFoundError:
        print("  [FAIL] schtasks not found. Set up the scheduled task manually.")


def setup_scheduler_macos():
    """Set up macOS launchd to run the filter every 2 minutes."""
    python = get_python_path()
    plist_name = "com.anp.filter"
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{plist_name}.plist"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{FILTER_SCRIPT}</string>
    </array>
    <key>StartInterval</key>
    <integer>120</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{ROOT / "logs" / "launchd.stdout.log"}</string>
    <key>StandardErrorPath</key>
    <string>{ROOT / "logs" / "launchd.stderr.log"}</string>
</dict>
</plist>"""

    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(plist_content, encoding="utf-8")

    # Load the agent
    subprocess.run(["launchctl", "unload", str(plist_path)],
                    capture_output=True)  # unload first if exists
    result = subprocess.run(["launchctl", "load", str(plist_path)],
                            capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  [OK] launchd: '{plist_name}' runs every 2 minutes")
    else:
        print(f"  [FAIL] launchctl error: {result.stderr.strip()}")
        print(f"         Plist written to {plist_path} — load manually with:")
        print(f"         launchctl load {plist_path}")


def setup_scheduler_linux():
    """Set up Linux cron to run the filter every 2 minutes."""
    python = get_python_path()
    cron_line = f"*/2 * * * * {python} {FILTER_SCRIPT}\n"
    marker = "# ANP-Filter"

    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        print("  [FAIL] crontab not found. Set up the scheduled task manually.")
        return

    # Remove old ANP entry if exists
    lines = [l for l in existing.splitlines() if marker not in l]
    lines.append(f"{cron_line.strip()} {marker}")

    new_crontab = "\n".join(lines) + "\n"
    result = subprocess.run(["crontab", "-"], input=new_crontab,
                            capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  [OK] cron: filter runs every 2 minutes")
    else:
        print(f"  [FAIL] crontab error: {result.stderr.strip()}")
        print(f"         Add this line manually with 'crontab -e':")
        print(f"         {cron_line.strip()}")


def setup_scheduler():
    """Detect OS and set up the appropriate scheduler."""
    system = platform.system()
    print(f"\nSetting up scheduler ({system})...")

    if system == "Windows":
        setup_scheduler_windows()
    elif system == "Darwin":
        setup_scheduler_macos()
    elif system == "Linux":
        setup_scheduler_linux()
    else:
        print(f"  [WARN] Unknown OS '{system}'. Set up a scheduled task manually.")
        print(f"         Run every 2 minutes: python {FILTER_SCRIPT}")


# --- Uninstall ---

def uninstall_scheduler():
    """Remove the scheduled task (keeps data and directories)."""
    system = platform.system()
    print(f"Removing scheduler ({system})...")

    if system == "Windows":
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", "ANP-Filter", "/F"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("  [OK] Task 'ANP-Filter' removed")
        else:
            print(f"  [INFO] {result.stderr.strip()}")

    elif system == "Darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.anp.filter.plist"
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink()
            print("  [OK] launchd agent removed")
        else:
            print("  [INFO] No launchd agent found")

    elif system == "Linux":
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if result.returncode == 0:
                lines = [l for l in result.stdout.splitlines() if "# ANP-Filter" not in l]
                subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n",
                                capture_output=True, text=True)
                print("  [OK] Cron entry removed")
        except FileNotFoundError:
            print("  [INFO] crontab not found")

    print("\n  Note: Data in ~/.ai-notifications/ is kept.")
    print("  Delete it manually if you want a full cleanup.")


# --- Main ---

def main():
    if "--uninstall" in sys.argv:
        uninstall_scheduler()
        return

    print("=" * 50)
    print("  ANP Setup — Agent Notification Protocol")
    print("=" * 50)
    print()

    # Step 1: Directories
    setup_directories()
    write_config()

    # Step 2: Install filter
    print("\nInstalling filter script...")
    install_filter()

    # Step 3: Scheduler
    setup_scheduler()

    # Done
    print("\n" + "=" * 50)
    print("  Setup complete!")
    print("=" * 50)
    print()
    print(f"  ANP root:     {ROOT}")
    print(f"  Filter:       {FILTER_SCRIPT}")
    print(f"  Context file: {ROOT / 'context' / 'notifications.md'}")
    print()
    print("  Next steps:")
    print("  1. Register apps with tokens in registry/")
    print("  2. Apps drop JSON notifications into incoming/")
    print("  3. Your AI agent reads context/notifications.md")
    print()


if __name__ == "__main__":
    main()
