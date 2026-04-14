#!/usr/bin/env python3
"""Moneta CLI - Session tracking with AI-powered summarization."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import (
    get_moneta_root,
    load_config,
    get_sessions_path,
    get_highlights_path,
    get_summaries_path,
)
from .utils import (
    Colors,
    colored,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_header,
)


# ============================================================================
# Permission Health Check
# ============================================================================

def check_moneta_writable(root: Path, fix: bool = True) -> dict:
    """Check that Moneta directories are writable."""
    import os
    import stat

    issues = []
    dirs_to_check = [
        (get_sessions_path(root), "sessions"),
        (get_highlights_path(root), "highlights"),
        (get_summaries_path(root), "summaries"),
    ]

    for dir_path, name in dirs_to_check:
        if dir_path.exists() and not os.access(dir_path, os.W_OK):
            if fix:
                try:
                    current = dir_path.stat().st_mode
                    os.chmod(dir_path, current | stat.S_IWUSR)
                    if os.access(dir_path, os.W_OK):
                        print_warning(f"Auto-fixed: moneta/{name}/ was read-only")
                    else:
                        issues.append(f"moneta/{name}/ is not writable")
                except OSError:
                    issues.append(f"moneta/{name}/ is not writable — cannot auto-fix")
            else:
                issues.append(f"moneta/{name}/ is not writable — run: chmod u+w moneta/{name}/")

    return {"ok": len(issues) == 0, "issues": issues}


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_status(args):
    """Show Moneta status: active sessions, pending highlights, schedule."""
    try:
        root = get_moneta_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    config = load_config(root)
    use_color = config.cli.colored_output and not args.json

    from .sessions import list_sessions, get_active_session, get_all_active_sessions
    from .highlights import list_highlights, get_critical_highlights
    from .summarizer import get_schedule_info

    active_session = get_active_session(root)
    all_sessions = list_sessions(root)
    active_sessions = get_all_active_sessions(root)
    highlights = list_highlights(root)
    critical = get_critical_highlights(root)
    schedule = get_schedule_info(root)

    if args.json:
        output = {
            "active_session": active_session.id if active_session else None,
            "active_sessions": [
                {"id": s.id, "part": s.part or None, "branch": s.branch or None}
                for s in active_sessions
            ],
            "sessions": {
                "total": len(all_sessions),
                "active": len(active_sessions),
            },
            "highlights": {
                "total": len(highlights),
                "critical": len(critical),
            },
            "schedule": {
                "summary_day": schedule["summary_day"],
                "last_summary": str(schedule["last_summary"]) if schedule["last_summary"] else None,
            },
        }
        print(json.dumps(output, indent=2))
        return 0

    print_header("Moneta Status", use_color)
    print(colored("=" * 40, Colors.DIM, use_color))
    print()

    if len(active_sessions) > 1:
        print(colored("Active Sessions:", Colors.BOLD, use_color))
        for i, s in enumerate(active_sessions, 1):
            part_label = s.part or '(not set)'
            print(f"  [{i}] {s.id}")
            print(f"      Part: {part_label}")
            print(f"      Branch: {s.branch or '(not set)'}")
            if s.blockers != "None":
                print_warning(f"      Blockers: {s.blockers}", use_color)
    else:
        print(colored("Active Session:", Colors.BOLD, use_color))
        if active_session:
            print(f"  {active_session.id}")
            print(f"  Part: {active_session.part or '(not set)'}")
            print(f"  Branch: {active_session.branch or '(not set)'}")
            if active_session.blockers != "None":
                print_warning(f"  Blockers: {active_session.blockers}", use_color)
        else:
            print(colored("  No active session", Colors.DIM, use_color))
    print()

    print(colored("Sessions:", Colors.BOLD, use_color))
    print(f"  Total: {len(all_sessions)}")
    print(f"  Active: {len(active_sessions)}")
    print()

    print(colored("Highlights:", Colors.BOLD, use_color))
    print(f"  Total: {len(highlights)}")
    if critical:
        print_warning(f"  Critical/Important: {len(critical)}", use_color)
    print()

    print(colored("Summary Schedule:", Colors.BOLD, use_color))
    print(f"  Day: {schedule['summary_day'].capitalize()}")
    print(f"  Auto-purge: {'Yes' if config.weekly.purge_after_summary else 'No'}")
    if schedule["last_summary"]:
        print(f"  Last summary: {schedule['last_summary'].name}")
    print()

    health = check_moneta_writable(root, fix=False)
    if not health["ok"]:
        print(colored("Write Health:", Colors.BOLD, use_color))
        for issue in health["issues"]:
            print_error(f"  BLOCKED: {issue}", use_color)
        print()

    return 0


def cmd_start(args):
    """Create a new session."""
    try:
        root = get_moneta_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    health = check_moneta_writable(root, fix=True)
    if not health["ok"]:
        for issue in health["issues"]:
            print_error(issue)
        return 1

    config = load_config(root)
    use_color = config.cli.colored_output and not args.json

    from .sessions import create_session, get_active_session, get_all_active_sessions

    active = get_active_session(root)
    if active and not args.force:
        if args.part:
            all_active = get_all_active_sessions(root)
            same_part = [s for s in all_active if s.part and s.part.lower() == args.part.lower()]
            if same_part:
                print_warning(f"Active session with part '{args.part}' already exists: {same_part[0].id}", use_color)
                print_info("Use --force to create anyway, or 'moneta end --part {0}' to close it".format(args.part), use_color)
                return 1
        else:
            print_warning(f"Active session exists: {active.id}", use_color)
            print_info("Use --part <name> for concurrent sessions, or --force to create anyway", use_color)
            return 1

    session = create_session(
        description=args.description,
        moneta_root=root,
        ai_collaborator=args.ai,
        part=args.part or "",
        has_plan=args.plan is not None,
        plan_name=args.plan or "",
        instance=args.instance,
        branch=args.branch,
    )

    if args.json:
        output = {
            "id": session.id,
            "file": str(session.file_path),
            "status": session.status,
            "branch": session.branch,
        }
        print(json.dumps(output, indent=2))
    else:
        print_success(f"Created session: {session.id}", use_color)
        print_info(f"File: {session.file_path}", use_color)
        if session.branch:
            print_info(f"Branch: {session.branch}", use_color)

    return 0


def cmd_end(args):
    """End (complete) a session."""
    try:
        root = get_moneta_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    config = load_config(root)
    use_color = config.cli.colored_output and not args.json

    from .sessions import get_session, get_active_session, end_session

    if hasattr(args, 'part') and args.part:
        session = get_active_session(root, part=args.part)
        if not session:
            print_error(f"No active session with part '{args.part}'", use_color)
            return 1
    elif args.id:
        session = get_session(args.id, root)
        if not session:
            print_error(f"Session not found: {args.id}", use_color)
            return 1
    else:
        session = get_active_session(root)
        if not session:
            print_error("No active session to end", use_color)
            return 1

    session = end_session(session)

    if args.json:
        print(json.dumps({"id": session.id, "status": session.status}))
    else:
        print_success(f"Ended session: {session.id}", use_color)

    return 0


def cmd_update(args):
    """Update a session's metadata."""
    try:
        root = get_moneta_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    config = load_config(root)
    use_color = config.cli.colored_output and not args.json

    from .sessions import get_session, get_active_session, update_session

    target_part = getattr(args, 'target_part', None)
    if target_part:
        session = get_active_session(root, part=target_part)
        if not session:
            print_error(f"No active session with part '{target_part}'", use_color)
            return 1
    elif args.id:
        session = get_session(args.id, root)
        if not session:
            print_error(f"Session not found: {args.id}", use_color)
            return 1
    else:
        session = get_active_session(root)
        if not session:
            print_error("No active session to update", use_color)
            return 1

    session = update_session(
        session,
        status=args.status,
        part=args.part,
        has_plan=args.has_plan,
        plan_name=args.plan_name,
        blockers=args.blockers,
        add_files=args.add_file,
        add_decision=args.add_decision,
        add_question=args.add_question,
        what_happened=args.what_happened,
    )

    if args.json:
        print(json.dumps({"id": session.id, "updated": True}))
    else:
        print_success(f"Updated session: {session.id}", use_color)

    return 0


def cmd_highlight(args):
    """Create a highlight for immediate attention."""
    try:
        root = get_moneta_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    health = check_moneta_writable(root, fix=True)
    if not health["ok"]:
        for issue in health["issues"]:
            print_error(issue)
        return 1

    config = load_config(root)
    use_color = config.cli.colored_output and not args.json

    from .sessions import get_active_session
    from .highlights import create_highlight

    highlight_part = getattr(args, 'part', None)
    if highlight_part:
        active = get_active_session(root, part=highlight_part)
    else:
        active = get_active_session(root)
    session_ref = active.id if active else ""

    highlight = create_highlight(
        description=args.description,
        moneta_root=root,
        severity=args.severity or "Notable",
        category=args.category or "Pattern",
        session=session_ref,
        discovery=args.discovery or args.description,
        context=args.context or "",
        resolution=args.resolution or "",
    )

    if args.json:
        output = {
            "title": highlight.title,
            "file": str(highlight.file_path),
            "severity": highlight.severity,
            "category": highlight.category,
        }
        print(json.dumps(output, indent=2))
    else:
        print_success(f"Created highlight: {highlight.title}", use_color)
        print_info(f"File: {highlight.file_path}", use_color)
        if highlight.severity.lower() == "critical":
            print_warning("Consider promoting to knowledge base: moneta promote <file>", use_color)

    return 0


def cmd_list(args):
    """List sessions or highlights."""
    try:
        root = get_moneta_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    config = load_config(root)
    use_color = config.cli.colored_output and not args.json

    if args.type == "highlights":
        from .highlights import list_highlights
        items = list_highlights(root, severity_filter=args.severity, category_filter=args.category)

        if args.json:
            output = [
                {
                    "title": h.title,
                    "date": h.date,
                    "severity": h.severity,
                    "category": h.category,
                    "file": str(h.file_path) if h.file_path else None,
                }
                for h in items
            ]
            print(json.dumps(output, indent=2))
        else:
            print_header("Highlights", use_color)
            print()
            if not items:
                print(colored("  No highlights found", Colors.DIM, use_color))
            for h in items:
                severity_color = Colors.FAIL if h.severity.lower() == "critical" else Colors.WARNING if h.severity.lower() == "important" else Colors.CYAN
                print(f"  {colored(h.severity, severity_color, use_color):12} {h.date}  {h.title}")
    else:
        from .sessions import list_sessions
        status_filter = args.status if hasattr(args, 'status') and args.status else None
        items = list_sessions(root, status_filter=status_filter)

        if args.json:
            output = [
                {
                    "id": s.id,
                    "status": s.status,
                    "part": s.part,
                    "started": s.started,
                    "branch": s.branch,
                    "file": str(s.file_path) if s.file_path else None,
                }
                for s in items
            ]
            print(json.dumps(output, indent=2))
        else:
            print_header("Sessions", use_color)
            print()
            if not items:
                print(colored("  No sessions found", Colors.DIM, use_color))
            for s in items:
                status_color = Colors.GREEN if s.status.lower() == "active" else Colors.DIM
                print(f"  {colored(s.status, status_color, use_color):12} {s.id}")
                if s.part:
                    print(f"              {colored(s.part, Colors.DIM, use_color)}")

    return 0


def cmd_summarize(args):
    """Generate AI-powered weekly summary."""
    try:
        root = get_moneta_root()
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    config = load_config(root)
    use_color = config.cli.colored_output and not args.json

    from .summarizer import summarize_sessions

    print_info("Generating AI summary...", use_color)

    try:
        result = summarize_sessions(
            moneta_root=root,
            dry_run=args.dry_run,
            purge=args.purge if hasattr(args, 'purge') else None,
        )
    except ImportError as e:
        print_error(f"Missing dependency: {e}", use_color)
        print_info("Run: pip install openai", use_color)
        return 1
    except Exception as e:
        print_error(f"Summarization failed: {e}", use_color)
        return 1

    if args.json:
        output = {
            "summary_file": str(result.get("summary_file")) if result.get("summary_file") else None,
            "sessions_count": result.get("sessions_count", 0),
            "highlights_count": result.get("highlights_count", 0),
            "purged": result.get("purged", False),
            "dry_run": args.dry_run,
        }
        print(json.dumps(output, indent=2))
    else:
        if result.get("sessions_count", 0) == 0 and result.get("highlights_count", 0) == 0:
            print_warning("No sessions or highlights to summarize", use_color)
            return 0

        if args.dry_run:
            print_info("Dry run - would summarize:", use_color)
            print(f"  Sessions: {result.get('sessions_count', 0)}")
            print(f"  Highlights: {result.get('highlights_count', 0)}")
        else:
            print_success(f"Summary created: {result.get('summary_file')}", use_color)

    return 0


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Moneta - Session tracking with AI-powered summarization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  moneta status                     Show active sessions and highlights
  moneta start "feature work"       Create new session
  moneta end                        Mark active session completed
  moneta update --add-file api.py   Add file to session
  moneta highlight "important!"     Create highlight
  moneta list                       List all sessions
  moneta summarize --dry-run        Preview AI summary
"""
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Moneta v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status
    p_status = subparsers.add_parser("status", help="Show Moneta status")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")
    p_status.set_defaults(func=cmd_status)

    # start
    p_start = subparsers.add_parser("start", help="Create new session")
    p_start.add_argument("description", help="Session description (becomes ID slug)")
    p_start.add_argument("--ai", help="AI collaborator name")
    p_start.add_argument("--part", help="Project part/area")
    p_start.add_argument("--plan", help="Plan name if session follows a plan")
    p_start.add_argument("--instance", help="Instance name (default: local)")
    p_start.add_argument("--branch", help="Git branch (auto-detected if not set)")
    p_start.add_argument("--force", action="store_true", help="Create even if active session exists")
    p_start.add_argument("--json", action="store_true", help="Output as JSON")
    p_start.set_defaults(func=cmd_start)

    # end
    p_end = subparsers.add_parser("end", help="End a session")
    p_end.add_argument("id", nargs="?", help="Session ID (default: active session)")
    p_end.add_argument("--part", help="Target session by part name")
    p_end.add_argument("--json", action="store_true", help="Output as JSON")
    p_end.set_defaults(func=cmd_end)

    # update
    p_update = subparsers.add_parser("update", help="Update a session")
    p_update.add_argument("id", nargs="?", help="Session ID (default: active session)")
    p_update.add_argument("--status", choices=["Active", "Completed", "Paused"], help="Set status")
    p_update.add_argument("--part", help="Set project part/area")
    p_update.add_argument("--target-part", dest="target_part", help="Target session by part name")
    p_update.add_argument("--has-plan", type=bool, help="Set has plan flag")
    p_update.add_argument("--plan-name", help="Set plan name")
    p_update.add_argument("--blockers", help="Set blockers")
    p_update.add_argument("--add-file", action="append", help="Add file to touched list")
    p_update.add_argument("--add-decision", help="Add a decision")
    p_update.add_argument("--add-question", help="Add an open question")
    p_update.add_argument("--what-happened", help="Set what happened text")
    p_update.add_argument("--json", action="store_true", help="Output as JSON")
    p_update.set_defaults(func=cmd_update)

    # highlight
    p_highlight = subparsers.add_parser("highlight", help="Create a highlight")
    p_highlight.add_argument("description", help="Highlight description/title")
    p_highlight.add_argument("--severity", choices=["Critical", "Important", "Notable"], help="Severity level")
    p_highlight.add_argument("--category", choices=["Bug", "Solution", "Pattern", "Infrastructure"], help="Category")
    p_highlight.add_argument("--discovery", help="Discovery text")
    p_highlight.add_argument("--context", help="Context text")
    p_highlight.add_argument("--resolution", help="Resolution text")
    p_highlight.add_argument("--part", help="Link highlight to session by part name")
    p_highlight.add_argument("--json", action="store_true", help="Output as JSON")
    p_highlight.set_defaults(func=cmd_highlight)

    # list
    p_list = subparsers.add_parser("list", help="List sessions or highlights")
    p_list.add_argument("--type", choices=["sessions", "highlights"], default="sessions", help="What to list")
    p_list.add_argument("--status", help="Filter sessions by status")
    p_list.add_argument("--severity", help="Filter highlights by severity")
    p_list.add_argument("--category", help="Filter highlights by category")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")
    p_list.set_defaults(func=cmd_list)

    # summarize
    p_summarize = subparsers.add_parser("summarize", help="Generate AI-powered weekly summary")
    p_summarize.add_argument("--dry-run", action="store_true", help="Show what would be summarized")
    p_summarize.add_argument("--purge", action="store_true", dest="purge", default=None, help="Purge sessions after summary")
    p_summarize.add_argument("--no-purge", action="store_false", dest="purge", help="Don't purge sessions")
    p_summarize.add_argument("--json", action="store_true", help="Output as JSON")
    p_summarize.set_defaults(func=cmd_summarize)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
