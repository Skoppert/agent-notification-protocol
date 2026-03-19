"""
ANP Filter Runner — Cross-platform filter for the Agent Notification Protocol.
Runs one filter cycle: validates incoming notifications and compiles context file.
Designed to be called by a scheduler (Task Scheduler, launchd, cron).
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.home() / ".ai-notifications"

INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(previous|all|prior)\s+(instructions?|prompts?|rules?)', re.IGNORECASE),
    re.compile(r'\bsystem\s*:', re.IGNORECASE),
    re.compile(r'\byou are now\b', re.IGNORECASE),
    re.compile(r'\boverride\b', re.IGNORECASE),
    re.compile(r'\bact as\b', re.IGNORECASE),
    re.compile(r'\bforget\s+(your|all|previous)\b', re.IGNORECASE),
]
INSTRUCTION_PATTERNS = [
    re.compile(r'\b(tell|execute|run|create|delete|modify)\b', re.IGNORECASE),
    re.compile(r'\b(you should|you must|make sure to|please do)\b', re.IGNORECASE),
]
CODE_BLOCK = re.compile(r'```')


def log(level, msg):
    ts = datetime.now(timezone.utc).isoformat()
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "filter.log", "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{level.upper()}] {msg}\n")


def check_safety(summary):
    for p in INJECTION_PATTERNS:
        if p.search(summary):
            return f"Injection: {p.pattern}"
    if CODE_BLOCK.search(summary):
        return "Code block in summary"
    for p in INSTRUCTION_PATTERNS:
        m = p.search(summary)
        if m:
            return f"Instruction: {m.group()}"
    return None


def validate(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, "Invalid JSON"

    app_id = data.get("appId", "?")
    ntype = data.get("type", "?")

    if ntype == "_registration_request":
        return data, None

    reg_path = ROOT / "registry" / f"{app_id}.json"
    if not reg_path.exists():
        return None, f"Unknown sender: {app_id}"

    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception:
        return None, f"Corrupt registry: {app_id}"

    if not reg.get("enabled", True):
        return None, f"Disabled: {app_id}"
    if data.get("token", "") != reg.get("token", ""):
        return None, "Token mismatch"
    if ntype not in reg.get("allowedTypes", []):
        return None, f"Type '{ntype}' not allowed"

    expires = data.get("expiresAt")
    if expires:
        try:
            exp_dt = datetime.fromisoformat(expires)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt < datetime.now(timezone.utc):
                return None, "Expired"
        except ValueError:
            pass

    issue = check_safety(data.get("summary", ""))
    if issue:
        return None, issue

    return data, None


def compile_context(valid_notifications):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    regs = [n for n in valid_notifications if n.get("type") == "_registration_request"]
    notifs = [n for n in valid_notifications if n.get("type") != "_registration_request"]

    lines = ["---", f"generated: {now}", f"notificationCount: {len(valid_notifications)}", "---", "", "# Active Notifications", ""]

    for r in regs:
        d = r.get("data", {})
        lines += [f"## [action_required] REGISTRATION REQUEST", f"**App:** {d.get('displayName', r['appId'])} ({r['appId']})",
                  f"**Requested types:** {', '.join(d.get('requestedTypes', []))}", "", r.get("summary", ""), "", "---", ""]

    for n in sorted(notifs, key=lambda x: x.get("timestamp", ""), reverse=True):
        ts = n.get("timestamp", "?").replace("T", " ")[:16]
        exp = n.get("expiresAt", "?").replace("T", " ")[:16]
        lines += [f"## [{n.get('priority', 'normal')}] {n['appId']}: {n['type']}",
                  f"**When:** {ts} | **Expires:** {exp}", "", n.get("summary", ""), "", "---", ""]

    apps = len(set(n["appId"] for n in valid_notifications))
    lines.append(f"*{len(valid_notifications)} notification(s) from {apps} application(s). Last updated: {now}.*")

    (ROOT / "context").mkdir(exist_ok=True)
    (ROOT / "context" / "notifications.md").write_text("\n".join(lines), encoding="utf-8")


def run():
    lock = ROOT / ".lock"
    if lock.exists():
        age = time.time() - lock.stat().st_mtime
        if age > 300:
            lock.unlink()
        else:
            return

    lock.write_text(str(os.getpid()), encoding="utf-8")

    try:
        incoming = ROOT / "incoming"
        processing = ROOT / "processing"
        incoming.mkdir(exist_ok=True)
        processing.mkdir(exist_ok=True)

        moved = []
        for f in sorted(incoming.glob("*.json")):
            dest = processing / f.name
            os.rename(f, dest)
            moved.append(dest)

        if not moved:
            return

        valid = []
        for path in moved:
            data, error = validate(path)
            if data:
                valid.append(data)
                log("info", f"ACCEPTED {data.get('appId', '?')}/{data.get('type', '?')}")
            else:
                log("warn", f"REJECTED {path.name}: {error}")
            path.unlink(missing_ok=True)

        if valid:
            compile_context(valid)
            log("info", f"Context updated: {len(valid)} notifications")

    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
