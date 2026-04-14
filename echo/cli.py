#!/usr/bin/env python3
"""Echo CLI — The Autonomic Heartbeat. Start the heart. Detect the ghosts."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .heartbeat import (
    get_echo_root,
    read_pulse,
    write_pulse,
    flatline,
    is_ghost,
    minutes_since_last_beat,
    detect_uncommitted_files,
    get_files_at_risk,
)
from .ghost_detector import detect_ghost, save_ghost_report, list_ghosts


# ANSI colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    RED_BG = '\033[41m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def colored(text, color, use_color=True):
    if use_color:
        return f"{color}{text}{Colors.ENDC}"
    return text


def print_success(msg, use_color=True):
    print(colored(f"♥ {msg}", Colors.GREEN, use_color))


def print_error(msg, use_color=True):
    print(colored(f"✗ {msg}", Colors.FAIL, use_color), file=sys.stderr)


def print_warning(msg, use_color=True):
    print(colored(f"! {msg}", Colors.WARNING, use_color))


def print_info(msg, use_color=True):
    print(colored(f"→ {msg}", Colors.CYAN, use_color))


def print_header(msg, use_color=True):
    print(colored(msg, Colors.BOLD + Colors.HEADER, use_color))


def print_ghost_alert(msg, use_color=True):
    print(colored(f"👻 {msg}", Colors.FAIL + Colors.BOLD, use_color))


# ============================================================================
# Commands
# ============================================================================

def cmd_beat(args):
    """Record a heartbeat pulse."""
    try:
        root = get_echo_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    project_root = root.parent

    # If no files specified and auto-scan enabled, detect uncommitted files
    files_in_play = []
    if args.files:
        files_in_play = args.files.split(",")
    elif args.scan:
        files_in_play = get_files_at_risk(project_root)

    pulse = write_pulse(
        echo_root=root,
        session_id=args.session,
        last_action=args.action,
        context_summary=args.context or "",
        files_in_play=files_in_play,
    )

    if args.json:
        print(json.dumps(pulse, indent=2))
    else:
        print_success(
            f"Beat #{pulse['beat_count']} — {args.action}",
        )
        if not args.files and not args.scan:
            at_risk = get_files_at_risk(project_root)
            if at_risk:
                print_warning(f"{len(at_risk)} uncommitted file(s) not tracked. Use --scan to auto-detect.")

    return 0


def cmd_status(args):
    """Show Echo status: current pulse, ghost check."""
    try:
        root = get_echo_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    pulse = read_pulse(root)
    ghosts = list_ghosts(root)

    if args.json:
        output = {
            "pulse": pulse,
            "has_pulse": pulse is not None,
            "is_ghost": is_ghost(pulse) if pulse else False,
            "minutes_since_beat": round(minutes_since_last_beat(pulse), 1) if pulse and minutes_since_last_beat(pulse) is not None else None,
            "ghost_reports": len(ghosts),
        }
        print(json.dumps(output, indent=2))
        return 0

    print_header("Echo — Autonomic Heartbeat", True)
    print(colored("=" * 40, Colors.DIM, True))
    print()

    if pulse is None:
        print(colored("  No pulse detected. Heart has not started.", Colors.DIM, True))
        print()
    else:
        status = pulse.get("status", "alive")
        mins = minutes_since_last_beat(pulse)

        if status == "flatlined":
            print(colored("  Status: FLATLINED (session ended gracefully)", Colors.DIM, True))
        elif is_ghost(pulse):
            print_ghost_alert(f"  Status: GHOST — {round(mins, 1)} minutes since last beat")
        else:
            print_success(f"  Status: ALIVE — last beat {round(mins, 1) if mins else '?'} min ago")

        print(f"  Session: {pulse.get('session_id', 'unknown')}")
        print(f"  Beats: {pulse.get('beat_count', 0)}")
        print(f"  Last action: {pulse.get('last_action', 'none')}")
        context = pulse.get('context_summary', '')
        if context:
            print(f"  Context: {context}")
        files = pulse.get('files_in_play', [])
        if files:
            print(f"  Files: {', '.join(files)}")
        print()

    # Ghost archive
    print(colored("Ghost Archive:", Colors.BOLD, True))
    if ghosts:
        print(f"  Total ghost reports: {len(ghosts)}")
        latest = ghosts[0]
        print(f"  Latest: {latest.get('detected_at', 'unknown')[:16]}")
        print(f"    Session: {latest.get('moneta_session_id', 'unknown')[:50]}")
        print(f"    Silent for: {latest.get('minutes_silent', '?')} min")
    else:
        print(colored("  No ghosts recorded. Clean slate.", Colors.DIM, True))
    print()

    # Uncommitted files warning
    project_root = root.parent
    uncommitted = detect_uncommitted_files(project_root)
    untracked_count = len(uncommitted.get("untracked", []))
    modified_count = len(uncommitted.get("modified", []))

    if untracked_count > 0 or modified_count > 0:
        print(colored("Uncommitted Work:", Colors.BOLD, True))
        if untracked_count > 0:
            print_warning(f"  {untracked_count} untracked file(s) — NOT in git, at risk of loss!")
            for f in uncommitted["untracked"][:5]:
                print(colored(f"    + {f}", Colors.WARNING, True))
            if untracked_count > 5:
                print(colored(f"    ... and {untracked_count - 5} more", Colors.DIM, True))
        if modified_count > 0:
            print(colored(f"  {modified_count} modified file(s) — changes not committed", Colors.CYAN, True))
        print()
        print_info("Run 'echo beat --scan' to track these files, or commit them.")
        print()

    return 0


def cmd_detect(args):
    """Check for ghost sessions — stale pulse + empty Moneta session."""
    try:
        root = get_echo_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    moneta_root = root.parent / "moneta"
    if not moneta_root.exists():
        print_error(f"Moneta not found at {moneta_root}")
        return 1

    ghost = detect_ghost(root, moneta_root, stale_minutes=args.stale or 30)

    if ghost is None:
        if args.json:
            print(json.dumps({"ghost": False}))
        else:
            print_success("No ghosts detected. All clear.")
        return 0

    report_path = save_ghost_report(ghost, root)

    if args.json:
        ghost["ghost"] = True
        ghost["report_file"] = str(report_path)
        print(json.dumps(ghost, indent=2))
    else:
        print_ghost_alert("GHOST DETECTED")
        print()
        print(ghost["recovery_brief"])
        print()
        print_info(f"Ghost report saved: {report_path}")

    return 0


def cmd_flatline(args):
    """Gracefully stop the heart (session ending)."""
    try:
        root = get_echo_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    pulse = flatline(root)

    if pulse is None:
        if args.json:
            print(json.dumps({"flatlined": False, "reason": "no active pulse"}))
        else:
            print_warning("No pulse to flatline.")
        return 0

    if args.json:
        print(json.dumps({"flatlined": True, "final_pulse": pulse}))
    else:
        beats = pulse.get("beat_count", 0)
        session = pulse.get("session_id", "unknown")
        print(colored(f"—— Flatline. Session '{session}' ended after {beats} beats. ——", Colors.DIM, True))

    return 0


def cmd_ghosts(args):
    """List all ghost reports from the archive."""
    try:
        root = get_echo_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    ghosts = list_ghosts(root)

    if args.json:
        print(json.dumps(ghosts, indent=2))
        return 0

    print_header("Ghost Archive", True)
    print()

    if not ghosts:
        print(colored("  No ghosts recorded.", Colors.DIM, True))
        return 0

    for g in ghosts:
        detected = g.get("detected_at", "unknown")[:16]
        session = g.get("moneta_session_id", "unknown")[:50]
        mins = g.get("minutes_silent", "?")
        empty = "EMPTY" if g.get("moneta_session_empty") else "partial"
        print(f"  {colored(detected, Colors.DIM, True)}  {session}")
        print(f"    Silent: {mins} min | Moneta: {empty}")
        print()

    return 0


def cmd_recover(args):
    """Print recovery brief for the current ghost or most recent ghost report."""
    try:
        root = get_echo_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    pulse = read_pulse(root)
    if pulse and is_ghost(pulse):
        moneta_root = root.parent / "moneta"
        ghost = detect_ghost(root, moneta_root)
        if ghost:
            print_header("Recovery Brief — Live Ghost", True)
            print()
            print(ghost["recovery_brief"])
            return 0

    ghosts = list_ghosts(root)
    if not ghosts:
        print_info("No ghost to recover from. All clear.")
        return 0

    latest = ghosts[0]
    print_header("Recovery Brief — From Archive", True)
    print()
    print(latest.get("recovery_brief", "No recovery brief available."))
    return 0


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Echo — The Autonomic Heartbeat. Records vital signs even when consciousness is lost.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  echo beat --session "my-session" --action "reading root.md"
  echo beat --session "my-session" --action "deploying to prod" --context "project deploy" --files "index.html,style.css"
  echo status                          Show current pulse and ghost archive
  echo detect                          Check for ghost sessions
  echo detect --stale 15               Ghost threshold: 15 minutes
  echo flatline                        Gracefully stop the heart
  echo ghosts                          List all ghost reports
  echo recover                         Show recovery brief for last ghost

The Flow:
  Session Start → echo beat (first heartbeat)
      ↓
  During Work  → echo beat (on each significant action)
      ↓
  Session End  → echo flatline (graceful stop)
      ↓
  Next Session → echo detect (check for ghosts from previous session)
      ↓
  Ghost Found  → echo recover (read the last words)
"""
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Echo v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # beat
    p_beat = subparsers.add_parser("beat", help="Record a heartbeat pulse")
    p_beat.add_argument("--session", "-s", required=True, help="Moneta session ID")
    p_beat.add_argument("--action", "-a", required=True, help="What you're doing right now")
    p_beat.add_argument("--context", "-c", help="Broader context of the work")
    p_beat.add_argument("--files", "-f", help="Comma-separated list of files in play")
    p_beat.add_argument("--scan", action="store_true", help="Auto-detect uncommitted files at risk")
    p_beat.add_argument("--json", action="store_true", help="Output as JSON")
    p_beat.set_defaults(func=cmd_beat)

    # status
    p_status = subparsers.add_parser("status", help="Show Echo status")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")
    p_status.set_defaults(func=cmd_status)

    # detect
    p_detect = subparsers.add_parser("detect", help="Check for ghost sessions")
    p_detect.add_argument("--stale", type=int, help="Minutes before a pulse is considered stale (default: 30)")
    p_detect.add_argument("--json", action="store_true", help="Output as JSON")
    p_detect.set_defaults(func=cmd_detect)

    # flatline
    p_flatline = subparsers.add_parser("flatline", help="Gracefully stop the heart")
    p_flatline.add_argument("--json", action="store_true", help="Output as JSON")
    p_flatline.set_defaults(func=cmd_flatline)

    # ghosts
    p_ghosts = subparsers.add_parser("ghosts", help="List ghost reports")
    p_ghosts.add_argument("--json", action="store_true", help="Output as JSON")
    p_ghosts.set_defaults(func=cmd_ghosts)

    # recover
    p_recover = subparsers.add_parser("recover", help="Show recovery brief for last ghost")
    p_recover.add_argument("--json", action="store_true", help="Output as JSON")
    p_recover.set_defaults(func=cmd_recover)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
