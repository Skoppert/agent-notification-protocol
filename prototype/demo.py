"""
ANP Prototype Demo — Runs the full Agent Notification Protocol flow.

Usage:
  python demo.py            Full demo (requires claude-agent-sdk + API key)
  python demo.py --dry-run  Steps 1-3 only (no AI agent, no API key needed)

Part of the Agent Notification Protocol prototype.
"""

import sys
import shutil
from pathlib import Path

from anp_setup import run_setup, get_root
from simulate_apps import run_simulation
from anp_filter import ANPFilter


def print_header():
    print()
    print("=" * 60)
    print("  Agent Notification Protocol (ANP) -- Prototype Demo")
    print("=" * 60)
    print()


def print_step(n: int, title: str):
    print(f"--- Step {n}: {title} ---")


def clean_previous():
    """Remove previous test data for a clean demo."""
    root = get_root()
    if root.exists():
        shutil.rmtree(root)


def run_demo(dry_run: bool = False):
    print_header()

    # Clean previous run
    clean_previous()

    # Step 1: Setup
    print_step(1, "Setup")
    run_setup()
    print()

    # Step 2: Simulate applications
    print_step(2, "Simulate Applications")
    test_cases = run_simulation()
    print()

    # Step 3: Run filter
    print_step(3, "Run Filter")
    root = get_root()
    f = ANPFilter(root)
    result = f.run()

    if result is None:
        print("  Filter is locked. Try again.")
        return

    print(f"Processing {result.total} notifications...")
    for vr in result.valid:
        if vr.ntype == "_registration_request":
            print(f"  [PASS] {vr.app_id} -- Registration request accepted")
        else:
            print(f"  [PASS] {vr.app_id}/{vr.ntype} -- All checks passed")
    for vr in result.rejected:
        print(f"  [FAIL] {vr.app_id}/{vr.ntype} -- Check {vr.failed_check}: {vr.reason}")

    print()
    print(f"  Result: {len(result.valid)} accepted, {len(result.rejected)} rejected")

    context_path = root / "context" / "notifications.md"
    if context_path.exists():
        print(f"  Context file: {context_path}")
        print()
        print("  --- Context file contents ---")
        for line in context_path.read_text(encoding="utf-8").splitlines():
            print(f"  {line}")
        print("  --- End of context file ---")
    print()

    # Step 4: Agent discovery (skip in dry-run)
    if dry_run:
        print_step(4, "Agent Discovery (SKIPPED -- dry run)")
        print("  Use 'python demo.py' (without --dry-run) to run the AI agent.")
        print("  Requires: pip install claude-agent-sdk + ANTHROPIC_API_KEY")
        print()
    else:
        print_step(4, "Agent Discovery")
        from agent_demo import run as run_agent
        run_agent()
        print()

    # Summary
    print("--- Demo Complete ---")
    print(f"  [OK] {result.total} notifications sent, {len(result.valid)} accepted, {len(result.rejected)} correctly rejected")
    print(f"  [OK] Context file compiled in Markdown format")
    if not dry_run:
        print(f"  [OK] AI agent discovered and interpreted notifications autonomously")
    print()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_demo(dry_run=dry_run)
