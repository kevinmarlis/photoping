"""
setup_schedule.py

Install or uninstall a macOS launchd job that runs photoping.py on a schedule.
Settings are read from .env (CADENCE, SEND_HOUR, SEND_WEEKDAY).

Usage:
    python setup_schedule.py install     # install and start the launchd job
    python setup_schedule.py uninstall   # stop and remove the launchd job
    python setup_schedule.py status      # show whether the job is loaded
"""

import argparse
import os
import pathlib
import plistlib
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

LABEL = "com.photoping"
PLIST_PATH = pathlib.Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
PROJECT_DIR = pathlib.Path(__file__).parent.resolve()
VENV_PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
SCRIPT = PROJECT_DIR / "photoping.py"
LOG_FILE = PROJECT_DIR / "photoping.log"


def _read_config() -> dict:
    """Read scheduling config from environment."""
    cadence = os.environ.get("CADENCE", "daily").strip().lower()
    if cadence not in ("daily", "weekly"):
        print(f"Error: CADENCE must be 'daily' or 'weekly', got '{cadence}'.", file=sys.stderr)
        sys.exit(1)

    try:
        send_hour = int(os.environ.get("SEND_HOUR", "9"))
        if not 0 <= send_hour <= 23:
            raise ValueError
    except ValueError:
        print("Error: SEND_HOUR must be an integer between 0 and 23.", file=sys.stderr)
        sys.exit(1)

    send_weekday = None
    if cadence == "weekly":
        try:
            send_weekday = int(os.environ.get("SEND_WEEKDAY", "1"))
            if not 0 <= send_weekday <= 6:
                raise ValueError
        except ValueError:
            print(
                "Error: SEND_WEEKDAY must be an integer between 0 (Sunday) and 6 (Saturday).",
                file=sys.stderr,
            )
            sys.exit(1)

    return {"cadence": cadence, "send_hour": send_hour, "send_weekday": send_weekday}


def _build_plist(config: dict) -> dict:
    """Build the launchd plist dictionary."""
    calendar_interval: dict = {"Hour": config["send_hour"], "Minute": 0}
    if config["cadence"] == "weekly":
        calendar_interval["Weekday"] = config["send_weekday"]

    return {
        "Label": LABEL,
        "ProgramArguments": [str(VENV_PYTHON), str(SCRIPT)],
        "StartCalendarInterval": calendar_interval,
        "WorkingDirectory": str(PROJECT_DIR),
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(LOG_FILE),
        # Prevent the job from running while the Mac is on battery (optional, remove if unwanted)
        # "PowerType": "AC",
    }


def _launchctl(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl"] + args, capture_output=True, text=True)


def install() -> None:
    if not VENV_PYTHON.exists():
        print(
            f"Error: Virtual environment not found at {VENV_PYTHON}\n"
            "Run: uv venv --python 3.13 && uv pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    config = _read_config()
    plist_data = _build_plist(config)

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist_data, f)

    # Unload first in case a stale job is registered
    _launchctl(["unload", str(PLIST_PATH)])

    result = _launchctl(["load", "-w", str(PLIST_PATH)])
    if result.returncode != 0:
        print(f"Error loading launchd job: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    weekday_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    if config["cadence"] == "daily":
        schedule_desc = f"daily at {config['send_hour']:02d}:00"
    else:
        day = weekday_names[config["send_weekday"]]
        schedule_desc = f"every {day} at {config['send_hour']:02d}:00"

    print(f"Installed. photoping will run {schedule_desc}.")
    print(f"Plist: {PLIST_PATH}")
    print(f"Logs:  {LOG_FILE}")


def uninstall() -> None:
    if not PLIST_PATH.exists():
        print("No launchd job found — nothing to uninstall.")
        return

    _launchctl(["unload", "-w", str(PLIST_PATH)])
    PLIST_PATH.unlink()
    print(f"Uninstalled. Removed {PLIST_PATH}.")


def status() -> None:
    result = _launchctl(["list", LABEL])
    if result.returncode == 0:
        print(f"Job '{LABEL}' is loaded.")
        print(result.stdout)
    else:
        print(f"Job '{LABEL}' is not loaded.")
    if PLIST_PATH.exists():
        print(f"Plist exists at: {PLIST_PATH}")
    else:
        print("No plist found — run 'install' to set up.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install or uninstall the photoping launchd schedule."
    )
    parser.add_argument(
        "command",
        choices=["install", "uninstall", "status"],
        help="Action to perform.",
    )
    args = parser.parse_args()

    actions = {"install": install, "uninstall": uninstall, "status": status}
    actions[args.command]()


if __name__ == "__main__":
    main()
