"""Ghost detector — finds sessions that died without a trace."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .heartbeat import read_pulse, is_ghost, minutes_since_last_beat


def detect_ghost(echo_root: Path, moneta_root: Path, stale_minutes: int = 30) -> Optional[dict]:
    """
    Detect a ghost session: stale pulse + active Moneta session with empty body.
    Returns ghost report dict or None.
    """
    pulse = read_pulse(echo_root)
    if pulse is None:
        return None

    if not is_ghost(pulse, stale_minutes):
        return None

    moneta_sessions = moneta_root / "sessions"
    session_id = pulse.get("session_id", "")
    ghost_report = {
        "detected_at": datetime.now().isoformat(),
        "pulse": pulse,
        "minutes_silent": round(minutes_since_last_beat(pulse) or 0, 1),
        "moneta_session_id": session_id,
        "moneta_session_empty": False,
        "recovery_brief": "",
    }

    for md_file in moneta_sessions.glob("*.md"):
        if session_id and session_id in md_file.stem:
            content = md_file.read_text()
            is_active = "| **Status** | Active |" in content
            is_empty = (
                "## What Happened\n\n" in content or
                "## What Happened\n-\n" in content or
                "## Files Touched\n-" in content
            )
            ghost_report["moneta_session_empty"] = is_active and is_empty
            ghost_report["moneta_file"] = str(md_file)
            break

    action = pulse.get("last_action", "unknown")
    context = pulse.get("context_summary", "no context recorded")
    files = pulse.get("files_in_play", [])
    beats = pulse.get("beat_count", 0)
    started = pulse.get("started_at", "unknown")

    ghost_report["recovery_brief"] = (
        f"Ghost detected: Session '{session_id}' went silent "
        f"{ghost_report['minutes_silent']} minutes ago.\n"
        f"Started: {started}\n"
        f"Total heartbeats: {beats}\n"
        f"Last action: {action}\n"
        f"Context: {context}\n"
        f"Files in play: {', '.join(files) if files else 'none'}\n"
        f"Moneta session empty: {'YES — no work was recorded' if ghost_report['moneta_session_empty'] else 'No — some work was captured'}"
    )

    return ghost_report


def save_ghost_report(ghost_report: dict, echo_root: Path) -> Path:
    """Save a ghost report to the ghosts directory."""
    ghosts_dir = echo_root / "ghosts"
    ghosts_dir.mkdir(exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d-%H%M")
    session_id = ghost_report.get("moneta_session_id", "unknown")
    slug = session_id[:60] if session_id else "unknown"
    filename = f"{now}-ghost-{slug}.json"

    ghost_path = ghosts_dir / filename
    with open(ghost_path, "w") as f:
        json.dump(ghost_report, f, indent=2)

    return ghost_path


def list_ghosts(echo_root: Path) -> list:
    """List all ghost reports."""
    ghosts_dir = echo_root / "ghosts"
    if not ghosts_dir.exists():
        return []

    ghosts = []
    for f in sorted(ghosts_dir.glob("*.json"), reverse=True):
        try:
            with open(f) as fh:
                data = json.load(fh)
                data["_file"] = str(f)
                ghosts.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    return ghosts
