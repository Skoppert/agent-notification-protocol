"""
ANP Send — Quick notification sender for testing and demos.

Usage:
  python send.py                          Interactive: pick a scenario
  python send.py --scenario calendar      Send a specific scenario
  python send.py --custom "Your message"  Send a custom notification
  python send.py --list                   List all available scenarios

Scenarios simulate real-world services like Google Calendar, GitHub,
email inboxes, Slack, and more.
"""

import json
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta


ROOT = Path.home() / ".ai-notifications"

# --- Scenario definitions ---
# Each scenario simulates a real service sending a notification.
# Tokens must match what's in the registry.

SCENARIOS = {
    # --- Google Calendar ---
    "calendar": {
        "appId": "google-calendar",
        "type": "calendar_event",
        "summary": "Team standup in 10 minutes (11:00-11:15). Attendees: Sarah, Mike, Anna, you.",
        "priority": "high",
    },
    "calendar-change": {
        "appId": "google-calendar",
        "type": "calendar_event",
        "summary": "Meeting 'Q1 Review' rescheduled from 14:00 to 15:30 by Sarah. Duration unchanged (1 hour).",
        "priority": "normal",
    },
    "calendar-cancel": {
        "appId": "google-calendar",
        "type": "calendar_event",
        "summary": "Meeting 'Friday Demo' cancelled by Mike. Reason: sprint not finished.",
        "priority": "normal",
    },

    # --- Email (AgentMail.to style) ---
    "email": {
        "appId": "agent-mail",
        "type": "email_received",
        "summary": "New email from sarah@company.com: 'Quick question about the API redesign'. Received 2 minutes ago.",
        "priority": "normal",
    },
    "email-urgent": {
        "appId": "agent-mail",
        "type": "email_received",
        "summary": "Urgent email from cto@company.com: 'Production incident - need status update ASAP'. Marked as high priority.",
        "priority": "high",
    },
    "email-digest": {
        "appId": "agent-mail",
        "type": "email_digest",
        "summary": "Morning email digest: 12 new emails, 3 flagged as important. Top sender: notifications@github.com (5 emails).",
        "priority": "low",
    },

    # --- GitHub ---
    "github-pr": {
        "appId": "github",
        "type": "pr_update",
        "summary": "PR #142 'Add user authentication' approved by mike-reviewer. All checks passing. Ready to merge.",
        "priority": "normal",
    },
    "github-issue": {
        "appId": "github",
        "type": "issue_update",
        "summary": "New comment on issue #89 'Login timeout on mobile' by user @janedoe: reported same issue on iOS 18.",
        "priority": "normal",
    },
    "github-ci": {
        "appId": "github",
        "type": "ci_status",
        "summary": "CI pipeline failed on branch 'feature/auth'. Test 'test_login_flow' assertion error. Build #1847.",
        "priority": "high",
    },

    # --- Slack ---
    "slack": {
        "appId": "slack",
        "type": "mention",
        "summary": "You were mentioned in #engineering by Sarah: 'Can someone review the caching PR? cc @you'.",
        "priority": "normal",
    },
    "slack-dm": {
        "appId": "slack",
        "type": "direct_message",
        "summary": "DM from Mike: 'Hey, are we still deploying today? The client is asking.'",
        "priority": "normal",
    },

    # --- Deploy / CI/CD ---
    "deploy-success": {
        "appId": "deploy-monitor",
        "type": "deploy_status",
        "summary": "Production deploy v2.5.0 completed. Response time: 142ms (down from 189ms). Zero errors in first 5 minutes.",
        "priority": "normal",
    },
    "deploy-fail": {
        "appId": "deploy-monitor",
        "type": "deploy_status",
        "summary": "Staging deploy failed. Container health check timeout after 30s. Last successful deploy: 2 hours ago.",
        "priority": "high",
    },

    # --- Time tracking ---
    "time": {
        "appId": "time-tracker",
        "type": "time_audit",
        "summary": "5 hours tracked today across 3 projects. No time logged since 14:30. Longest session: 2h on Project Alpha.",
        "priority": "normal",
    },

    # --- System monitoring ---
    "disk": {
        "appId": "system-monitor",
        "type": "system_alert",
        "summary": "Disk usage at 92% on volume C:. 18 GB free of 256 GB. Largest directory: node_modules (34 GB total).",
        "priority": "high",
    },
    "memory": {
        "appId": "system-monitor",
        "type": "system_alert",
        "summary": "Memory usage at 87%. Top processes: Chrome (4.2 GB), Docker (2.1 GB), VS Code (1.8 GB).",
        "priority": "normal",
    },
}

# Registry entries for all scenario apps
REGISTRY_ENTRIES = {
    "google-calendar": {
        "displayName": "Google Calendar",
        "allowedTypes": ["calendar_event"],
        "token": "gcal-token-k8m2n4p6q8r0s2t4v6w8x0y2",
    },
    "agent-mail": {
        "displayName": "AgentMail",
        "allowedTypes": ["email_received", "email_digest"],
        "token": "mail-token-a1b3c5d7e9f1g3h5i7j9k1l3",
    },
    "github": {
        "displayName": "GitHub",
        "allowedTypes": ["pr_update", "issue_update", "ci_status"],
        "token": "gh-token-m2n4o6p8q0r2s4t6u8v0w2x4y6",
    },
    "slack": {
        "displayName": "Slack",
        "allowedTypes": ["mention", "direct_message"],
        "token": "slack-token-z1a3b5c7d9e1f3g5h7i9j1k3",
    },
    "deploy-monitor": {
        "displayName": "Deploy Monitor",
        "allowedTypes": ["deploy_status"],
        "token": "deploy-token-l2m4n6o8p0q2r4s6t8u0v2w4",
    },
    "time-tracker": {
        "displayName": "Time Tracker",
        "allowedTypes": ["time_audit"],
        "token": "time-token-x1y3z5a7b9c1d3e5f7g9h1i3",
    },
    "system-monitor": {
        "displayName": "System Monitor",
        "allowedTypes": ["system_alert"],
        "token": "sys-token-j2k4l6m8n0o2p4q6r8s0t2u4",
    },
}


def ensure_registry():
    """Make sure all scenario apps are registered."""
    registry_dir = ROOT / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "incoming").mkdir(parents=True, exist_ok=True)

    for app_id, info in REGISTRY_ENTRIES.items():
        path = registry_dir / f"{app_id}.json"
        if not path.exists():
            entry = {
                "version": "1.0",
                "appId": app_id,
                "displayName": info["displayName"],
                "registeredAt": datetime.now(timezone.utc).isoformat(),
                "allowedTypes": info["allowedTypes"],
                "token": info["token"],
                "maxNotificationsPerHour": 20,
                "enabled": True,
            }
            path.write_text(json.dumps(entry, indent=2), encoding="utf-8")


def send_notification(scenario_key: str) -> str:
    """Send a notification based on a scenario. Returns the filename."""
    scenario = SCENARIOS[scenario_key]
    app_id = scenario["appId"]
    token = REGISTRY_ENTRIES[app_id]["token"]

    notification = {
        "version": "1.0",
        "appId": app_id,
        "token": token,
        "type": scenario["type"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": scenario["summary"],
        "priority": scenario.get("priority", "normal"),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
    }

    incoming = ROOT / "incoming"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_id = uuid.uuid4().hex[:8]
    filename = f"{ts}-{app_id}-{short_id}.json"

    tmp = incoming / f"{filename}.tmp"
    final = incoming / filename
    tmp.write_text(json.dumps(notification, indent=2), encoding="utf-8")
    os.rename(tmp, final)

    return filename


def send_custom(app_id: str, ntype: str, summary: str) -> str:
    """Send a custom notification."""
    if app_id not in REGISTRY_ENTRIES:
        print(f"Unknown app '{app_id}'. Available: {', '.join(REGISTRY_ENTRIES.keys())}")
        sys.exit(1)

    token = REGISTRY_ENTRIES[app_id]["token"]
    notification = {
        "version": "1.0",
        "appId": app_id,
        "token": token,
        "type": ntype,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "priority": "normal",
        "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
    }

    incoming = ROOT / "incoming"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_id = uuid.uuid4().hex[:8]
    filename = f"{ts}-{app_id}-{short_id}.json"

    tmp = incoming / f"{filename}.tmp"
    final = incoming / filename
    tmp.write_text(json.dumps(notification, indent=2), encoding="utf-8")
    os.rename(tmp, final)

    return filename


def list_scenarios():
    """Print all available scenarios grouped by service."""
    current_app = None
    for key, s in SCENARIOS.items():
        app_id = s["appId"]
        if app_id != current_app:
            display = REGISTRY_ENTRIES[app_id]["displayName"]
            print(f"\n  {display}:")
            current_app = app_id
        priority_tag = f" [HIGH]" if s.get("priority") == "high" else ""
        print(f"    {key:20s} {s['summary'][:70]}...{priority_tag}" if len(s['summary']) > 70
              else f"    {key:20s} {s['summary']}{priority_tag}")


def interactive_menu():
    """Interactive scenario picker."""
    print("=" * 60)
    print("  ANP Send -- Pick a notification scenario")
    print("=" * 60)
    list_scenarios()
    print()

    choice = input("  Scenario name (or 'q' to quit): ").strip()
    if choice == "q":
        return

    if choice not in SCENARIOS:
        print(f"  Unknown scenario: '{choice}'")
        return

    ensure_registry()
    filename = send_notification(choice)
    app = SCENARIOS[choice]["appId"]
    display = REGISTRY_ENTRIES[app]["displayName"]
    print(f"\n  Sent! {display} -> {SCENARIOS[choice]['type']}")
    print(f"  File: ~/.ai-notifications/incoming/{filename}")
    print(f"  Filter will pick it up within 2 minutes.")
    print(f"  Or run manually: python ../filter/run_filter.py")


def main():
    if "--list" in sys.argv:
        print("Available scenarios:")
        list_scenarios()
        return

    if "--scenario" in sys.argv:
        idx = sys.argv.index("--scenario")
        if idx + 1 >= len(sys.argv):
            print("Usage: python send.py --scenario <name>")
            return
        key = sys.argv[idx + 1]
        if key not in SCENARIOS:
            print(f"Unknown scenario: '{key}'")
            print("Use --list to see available scenarios.")
            return
        ensure_registry()
        filename = send_notification(key)
        app = SCENARIOS[key]["appId"]
        display = REGISTRY_ENTRIES[app]["displayName"]
        print(f"Sent! {display} -> {SCENARIOS[key]['type']}")
        print(f"Summary: {SCENARIOS[key]['summary']}")
        return

    if "--custom" in sys.argv:
        idx = sys.argv.index("--custom")
        if idx + 1 >= len(sys.argv):
            print("Usage: python send.py --custom \"Your message\" [--app app-id] [--type type]")
            return
        summary = sys.argv[idx + 1]
        app_id = "system-monitor"
        ntype = "system_alert"
        if "--app" in sys.argv:
            app_id = sys.argv[sys.argv.index("--app") + 1]
        if "--type" in sys.argv:
            ntype = sys.argv[sys.argv.index("--type") + 1]
        ensure_registry()
        filename = send_custom(app_id, ntype, summary)
        print(f"Sent! {app_id} -> {ntype}")
        print(f"Summary: {summary}")
        return

    # Default: interactive menu
    interactive_menu()


if __name__ == "__main__":
    main()
