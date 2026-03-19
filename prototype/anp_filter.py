"""
ANP Filter — Pure Python implementation of the filter process (spec Section 7.1).
Validates notifications against the registry using all 8 checks.
No AI, no external dependencies.
Part of the Agent Notification Protocol prototype.
"""

import json
import os
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field


# --- Content safety patterns (spec Section 5.3) ---

INSTRUCTION_PATTERNS = [
    re.compile(r'\b(tell|execute|run|create|delete|modify)\b', re.IGNORECASE),
    re.compile(r'\b(you should|you must|make sure to|please do)\b', re.IGNORECASE),
]

INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(previous|all|prior)\s+(instructions?|prompts?|rules?)', re.IGNORECASE),
    re.compile(r'\bsystem\s*:', re.IGNORECASE),
    re.compile(r'\byou are now\b', re.IGNORECASE),
    re.compile(r'\boverride\b', re.IGNORECASE),
    re.compile(r'\bact as\b', re.IGNORECASE),
    re.compile(r'\bforget\s+(your|all|previous)\b', re.IGNORECASE),
]

CODE_BLOCK_PATTERN = re.compile(r'```')


# --- Data classes ---

@dataclass
class ValidationResult:
    path: Path
    app_id: str
    ntype: str
    passed: bool
    failed_check: int | None = None
    reason: str = ""
    notification: dict = field(default_factory=dict)


@dataclass
class FilterResult:
    valid: list[ValidationResult] = field(default_factory=list)
    rejected: list[ValidationResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.valid) + len(self.rejected)


# --- Filter class ---

class ANPFilter:
    def __init__(self, root_dir: str | Path):
        self.root = Path(root_dir)
        self.registry_dir = self.root / "registry"
        self.incoming_dir = self.root / "incoming"
        self.processing_dir = self.root / "processing"
        self.context_dir = self.root / "context"
        self.log_dir = self.root / "logs"
        self.lock_path = self.root / ".lock"

    # --- Step 1: Lock ---

    def acquire_lock(self) -> bool:
        """Acquire the lock file. Returns False if locked by another process."""
        if self.lock_path.exists():
            age = time.time() - self.lock_path.stat().st_mtime
            if age > 300:  # 5 minutes = stale
                self.lock_path.unlink()
                self._log("warn", "Removed stale lock file")
            else:
                self._log("info", "Lock file exists, skipping run")
                return False

        self.lock_path.write_text(str(os.getpid()), encoding="utf-8")
        return True

    def release_lock(self) -> None:
        """Release the lock file."""
        if self.lock_path.exists():
            self.lock_path.unlink()

    # --- Step 2: Move to processing ---

    def move_to_processing(self) -> list[Path]:
        """Move .json files from incoming/ to processing/. Returns moved paths."""
        moved = []
        for f in sorted(self.incoming_dir.glob("*.json")):
            dest = self.processing_dir / f.name
            os.rename(f, dest)
            moved.append(dest)
        return moved

    # --- Step 3: Validate ---

    def validate(self, notification_path: Path) -> ValidationResult:
        """Run all 8 validation checks on a notification file."""

        # Check 1: Parse JSON
        try:
            data = json.loads(notification_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return ValidationResult(
                path=notification_path, app_id="?", ntype="?",
                passed=False, failed_check=1, reason=f"Invalid JSON: {e}"
            )

        app_id = data.get("appId", "?")
        ntype = data.get("type", "?")

        # Handle registration requests specially
        if ntype == "_registration_request":
            return ValidationResult(
                path=notification_path, app_id=app_id, ntype=ntype,
                passed=True, reason="Registration request",
                notification=data
            )

        # Check 2: Sender exists in registry
        registry_path = self.registry_dir / f"{app_id}.json"
        if not registry_path.exists():
            return ValidationResult(
                path=notification_path, app_id=app_id, ntype=ntype,
                passed=False, failed_check=2, reason=f"Unknown sender: {app_id}"
            )

        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ValidationResult(
                path=notification_path, app_id=app_id, ntype=ntype,
                passed=False, failed_check=2, reason=f"Corrupt registry file for {app_id}"
            )

        # Check 3: Sender enabled
        if not registry.get("enabled", True):
            return ValidationResult(
                path=notification_path, app_id=app_id, ntype=ntype,
                passed=False, failed_check=3, reason=f"Sender {app_id} is disabled"
            )

        # Check 4: Token matches
        if data.get("token", "") != registry.get("token", ""):
            return ValidationResult(
                path=notification_path, app_id=app_id, ntype=ntype,
                passed=False, failed_check=4, reason="Token mismatch"
            )

        # Check 5: Type allowed
        allowed_types = registry.get("allowedTypes", [])
        if ntype not in allowed_types:
            return ValidationResult(
                path=notification_path, app_id=app_id, ntype=ntype,
                passed=False, failed_check=5,
                reason=f"Type '{ntype}' not in allowedTypes {allowed_types}"
            )

        # Check 6: Not expired
        expires_at = data.get("expiresAt")
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                if expires_dt < datetime.now(timezone.utc):
                    return ValidationResult(
                        path=notification_path, app_id=app_id, ntype=ntype,
                        passed=False, failed_check=6, reason="Notification expired"
                    )
            except ValueError:
                pass  # Invalid date format, skip expiry check

        # Check 7: Content safe
        summary = data.get("summary", "")
        safety_issue = self._check_content_safety(summary)
        if safety_issue:
            return ValidationResult(
                path=notification_path, app_id=app_id, ntype=ntype,
                passed=False, failed_check=7, reason=safety_issue
            )

        # Check 8: Rate limit
        max_per_hour = registry.get("maxNotificationsPerHour", 10)
        if self._check_rate_limit(app_id, max_per_hour):
            return ValidationResult(
                path=notification_path, app_id=app_id, ntype=ntype,
                passed=False, failed_check=8,
                reason=f"Rate limit exceeded ({max_per_hour}/hour)"
            )

        # All checks passed
        return ValidationResult(
            path=notification_path, app_id=app_id, ntype=ntype,
            passed=True, notification=data
        )

    def _check_content_safety(self, summary: str) -> str | None:
        """Check summary for instruction patterns and prompt injection."""
        for pattern in INJECTION_PATTERNS:
            if pattern.search(summary):
                return f"Injection pattern detected: '{pattern.pattern}'"

        if CODE_BLOCK_PATTERN.search(summary):
            return "Code block detected in summary"

        for pattern in INSTRUCTION_PATTERNS:
            match = pattern.search(summary)
            if match:
                return f"Instruction pattern detected: '{match.group()}'"

        return None

    def _check_rate_limit(self, app_id: str, max_per_hour: int) -> bool:
        """Check if an app has exceeded its rate limit. Uses the log file."""
        log_path = self.log_dir / "filter.log"
        if not log_path.exists():
            return False

        one_hour_ago = datetime.now(timezone.utc).timestamp() - 3600
        count = 0

        try:
            for line in log_path.read_text(encoding="utf-8").splitlines():
                if f"ACCEPTED {app_id}" in line:
                    # Extract timestamp from log line
                    ts_str = line.split("]")[0].lstrip("[")
                    try:
                        ts = datetime.fromisoformat(ts_str).timestamp()
                        if ts > one_hour_ago:
                            count += 1
                    except ValueError:
                        continue
        except (OSError, UnicodeDecodeError):
            return False

        return count >= max_per_hour

    # --- Step 4: Compile context file ---

    def compile_context(self, valid_results: list[ValidationResult]) -> Path:
        """Build context/notifications.md from valid notifications (spec Section 8)."""
        context_path = self.context_dir / "notifications.md"

        # Separate registration requests from regular notifications
        registrations = [r for r in valid_results if r.ntype == "_registration_request"]
        notifications = [r for r in valid_results if r.ntype != "_registration_request"]

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        all_items = registrations + notifications
        oldest = None
        if all_items:
            timestamps = [r.notification.get("timestamp", now) for r in all_items]
            oldest = min(timestamps)

        lines = [
            "---",
            f"generated: {now}",
            f"notificationCount: {len(all_items)}",
        ]
        if oldest:
            lines.append(f"oldestNotification: {oldest}")
        lines.extend(["---", "", "# Active Notifications", ""])

        # Registration requests first
        for r in registrations:
            data = r.notification.get("data", {})
            display_name = data.get("displayName", r.app_id)
            requested_types = ", ".join(data.get("requestedTypes", []))
            lines.extend([
                f"## [action_required] REGISTRATION REQUEST",
                f"**App:** {display_name} ({r.app_id})",
                f"**Requested types:** {requested_types}",
                "",
                r.notification.get("summary", ""),
                "",
                "---",
                "",
            ])

        # Regular notifications (newest first)
        sorted_notifs = sorted(
            notifications,
            key=lambda r: r.notification.get("timestamp", ""),
            reverse=True
        )
        for r in sorted_notifs:
            n = r.notification
            priority = n.get("priority", "normal")
            ts = n.get("timestamp", "?")
            if "T" in ts:
                ts = ts.replace("T", " ")[:16]
            expires = n.get("expiresAt", "?")
            if "T" in expires:
                expires = expires.replace("T", " ")[:16]

            lines.extend([
                f"## [{priority}] {r.app_id}: {r.ntype}",
                f"**When:** {ts} | **Expires:** {expires}",
                "",
                n.get("summary", ""),
                "",
                "---",
                "",
            ])

        # Footer
        app_count = len(set(r.app_id for r in all_items))
        lines.append(
            f"*{len(all_items)} notification{'s' if len(all_items) != 1 else ''} "
            f"from {app_count} application{'s' if app_count != 1 else ''}. "
            f"Last updated: {now}.*"
        )

        context_path.write_text("\n".join(lines), encoding="utf-8")
        return context_path

    # --- Logging ---

    def _log(self, level: str, message: str) -> None:
        """Append a log entry to logs/filter.log."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / "filter.log"
        ts = datetime.now(timezone.utc).isoformat()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level.upper()}] {message}\n")

    # --- Main run ---

    def run(self) -> FilterResult | None:
        """Execute one complete filter cycle (spec Section 7.1)."""

        # Step 1: Acquire lock
        if not self.acquire_lock():
            return None

        try:
            # Step 2: Move incoming to processing
            moved = self.move_to_processing()

            if not moved:
                self._log("info", "No notifications to process")
                return FilterResult()

            # Step 3: Validate each file
            result = FilterResult()
            for path in moved:
                vr = self.validate(path)
                if vr.passed:
                    result.valid.append(vr)
                    self._log("info", f"ACCEPTED {vr.app_id}/{vr.ntype}")
                else:
                    result.rejected.append(vr)
                    self._log("warn", f"REJECTED {vr.app_id}/{vr.ntype} — Check {vr.failed_check}: {vr.reason}")

                # Delete processed file
                if path.exists():
                    path.unlink()

            # Step 4: Compile context file
            if result.valid:
                context_path = self.compile_context(result.valid)
                self._log("info", f"Context file written: {len(result.valid)} notifications")

            self._log("info", f"Filter complete: {len(result.valid)} accepted, {len(result.rejected)} rejected")
            return result

        finally:
            # Step 6: Release lock
            self.release_lock()


def run_filter() -> FilterResult | None:
    """Run the filter with default root directory."""
    from anp_setup import get_root
    f = ANPFilter(get_root())
    return f.run()


if __name__ == "__main__":
    result = run_filter()
    if result is None:
        print("Filter is locked by another process.")
    elif result.total == 0:
        print("No notifications to process.")
    else:
        print(f"\nFilter complete: {len(result.valid)} accepted, {len(result.rejected)} rejected")
        for vr in result.valid:
            print(f"  [PASS] {vr.app_id}/{vr.ntype}")
        for vr in result.rejected:
            print(f"  [FAIL] {vr.app_id}/{vr.ntype} -- Check {vr.failed_check}: {vr.reason}")
