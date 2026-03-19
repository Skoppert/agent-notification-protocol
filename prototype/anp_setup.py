"""
ANP Setup — Creates the directory structure and test registrations.
Part of the Agent Notification Protocol prototype.
"""

import json
import secrets
from pathlib import Path
from datetime import datetime, timezone


# Fixed tokens for test apps (so simulate_apps.py can use them)
CI_PIPELINE_TOKEN = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
TIME_TRACKER_TOKEN = "z9y8x7w6v5u4t3s2r1q0p9o8n7m6l5k4"


def get_root() -> Path:
    return Path.home() / ".ai-notifications"


def setup_directories(root: Path) -> list[str]:
    """Create the ANP directory structure. Returns list of created dirs."""
    dirs = ["registry", "incoming", "processing", "context", "logs"]
    created = []
    for d in dirs:
        path = root / d
        path.mkdir(parents=True, exist_ok=True)
        created.append(d)
    return created


def write_config(root: Path) -> None:
    """Write the global config.json."""
    config = {
        "version": "1.0",
        "pollIntervalSeconds": 120,
        "maxNotificationAgeDays": 2,
        "maxContextEntries": 50,
        "archiveEnabled": True,
        "logLevel": "info",
    }
    (root / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def register_app(root: Path, app_id: str, display_name: str, allowed_types: list[str], token: str) -> None:
    """Create a registry file for an application."""
    registry = {
        "version": "1.0",
        "appId": app_id,
        "displayName": display_name,
        "registeredAt": datetime.now(timezone.utc).isoformat(),
        "allowedTypes": allowed_types,
        "token": token,
        "maxNotificationsPerHour": 10,
        "enabled": True,
    }
    path = root / "registry" / f"{app_id}.json"
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def run_setup() -> Path:
    """Run the full setup. Returns the root path."""
    root = get_root()

    print(f"Creating directory structure at {root}/")
    created = setup_directories(root)
    for d in created:
        print(f"  [OK] {d}/")

    print("\nWriting config.json...")
    write_config(root)
    print("  [OK] config.json")

    print("\nRegistering test applications...")
    register_app(root, "ci-pipeline", "CI Pipeline", ["deploy_status", "task_complete"], CI_PIPELINE_TOKEN)
    print("  [OK] ci-pipeline (types: deploy_status, task_complete)")

    register_app(root, "time-tracker", "Time Tracker", ["time_audit"], TIME_TRACKER_TOKEN)
    print("  [OK] time-tracker (types: time_audit)")

    return root


if __name__ == "__main__":
    run_setup()
    print("\nSetup complete.")
