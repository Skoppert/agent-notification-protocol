"""
ANP Watch — Live monitor for incoming notifications.

Shows notifications being received, validated, and compiled in real-time.
Open this in one terminal, then use send.py in another terminal to see
notifications flow through the system.

Usage:
  python watch.py

Press Ctrl+C to stop.
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# Add parent dir so we can import the filter
sys.path.insert(0, str(Path(__file__).parent.parent / "filter"))

ROOT = Path.home() / ".ai-notifications"


def format_time():
    return datetime.now().strftime("%H:%M:%S")


def count_files(directory: Path, pattern="*.json") -> int:
    if not directory.exists():
        return 0
    return len(list(directory.glob(pattern)))


def read_context() -> tuple[int, list[str]]:
    """Read the context file and return (count, summaries)."""
    context_path = ROOT / "context" / "notifications.md"
    if not context_path.exists():
        return 0, []

    content = context_path.read_text(encoding="utf-8")
    count = 0
    summaries = []

    for line in content.splitlines():
        if line.startswith("notificationCount:"):
            try:
                count = int(line.split(":")[1].strip())
            except (ValueError, IndexError):
                pass
        if line.startswith("## ["):
            summaries.append(line)

    return count, summaries


def run_filter_once():
    """Run the filter inline (same logic as run_filter.py)."""
    try:
        # Try importing from the filter directory
        filter_path = Path(__file__).parent.parent / "filter" / "run_filter.py"
        if filter_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("run_filter", filter_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run()
            return True

        # Fallback: try the installed filter
        installed = ROOT / "run_filter.py"
        if installed.exists():
            spec = importlib.util.spec_from_file_location("run_filter", installed)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run()
            return True

    except Exception as e:
        print(f"  [!] Filter error: {e}")

    return False


def watch():
    print("=" * 60)
    print("  ANP Watch -- Live notification monitor")
    print("=" * 60)
    print()
    print(f"  Watching: {ROOT / 'incoming'}")
    print(f"  Context:  {ROOT / 'context' / 'notifications.md'}")
    print(f"  Press Ctrl+C to stop")
    print()
    print("-" * 60)

    prev_incoming = set()
    prev_context_count = 0

    # Initial state
    context_count, summaries = read_context()
    prev_context_count = context_count
    if context_count > 0:
        print(f"  [{format_time()}] {context_count} existing notification(s) in context")
        for s in summaries:
            print(f"             {s}")
        print()

    try:
        while True:
            incoming_dir = ROOT / "incoming"
            if incoming_dir.exists():
                current_files = set(f.name for f in incoming_dir.glob("*.json"))
                new_files = current_files - prev_incoming

                if new_files:
                    for fname in sorted(new_files):
                        fpath = incoming_dir / fname
                        try:
                            data = json.loads(fpath.read_text(encoding="utf-8"))
                            app = data.get("appId", "?")
                            ntype = data.get("type", "?")
                            summary = data.get("summary", "?")
                            priority = data.get("priority", "normal")
                            prio_tag = " [HIGH]" if priority == "high" else ""

                            print(f"  [{format_time()}] INCOMING {app} -> {ntype}{prio_tag}")
                            # Truncate summary for display
                            if len(summary) > 80:
                                print(f"             {summary[:80]}...")
                            else:
                                print(f"             {summary}")
                        except Exception:
                            print(f"  [{format_time()}] INCOMING {fname}")

                    # Run the filter immediately
                    print(f"  [{format_time()}] Running filter...")
                    run_filter_once()

                    # Check what happened
                    new_count, new_summaries = read_context()
                    accepted = new_count - prev_context_count
                    rejected = len(new_files) - max(0, accepted)

                    if accepted > 0:
                        print(f"  [{format_time()}] ACCEPTED {accepted} notification(s)")
                    if rejected > 0:
                        print(f"  [{format_time()}] REJECTED {rejected} notification(s)")

                        # Show rejection reasons from log
                        log_path = ROOT / "logs" / "filter.log"
                        if log_path.exists():
                            lines = log_path.read_text(encoding="utf-8").splitlines()
                            for line in lines[-10:]:  # last 10 log entries
                                if "REJECTED" in line:
                                    reason = line.split("REJECTED")[-1].strip()
                                    print(f"             Reason: {reason}")

                    prev_context_count = new_count
                    print()

                prev_incoming = current_files

            time.sleep(1)  # Check every second

    except KeyboardInterrupt:
        print(f"\n  [{format_time()}] Watch stopped.")


if __name__ == "__main__":
    watch()
