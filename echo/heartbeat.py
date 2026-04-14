"""Echo heartbeat — the pulse file that keeps beating until it doesn't."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict


PULSE_FILENAME = "pulse.json"


def get_echo_root() -> Path:
    """Find Echo root by walking up from cwd."""
    path = Path.cwd()

    candidates = [
        path / "echo",
        path,
    ]
    for c in candidates:
        if (c / "echo.yaml").exists() or (c / "heartbeat.py").exists():
            return c

    for parent in path.parents:
        candidate = parent / "echo"
        if candidate.exists() and (candidate / "echo.yaml").exists():
            return candidate

    raise FileNotFoundError("Echo not found. Run from within a project with echo/ directory.")


def get_pulse_path(echo_root: Path = None) -> Path:
    """Get path to the pulse file."""
    root = echo_root or get_echo_root()
    return root / PULSE_FILENAME


def read_pulse(echo_root: Path = None) -> Optional[dict]:
    """Read current pulse. Returns None if no pulse exists."""
    pulse_path = get_pulse_path(echo_root)
    if not pulse_path.exists():
        return None
    try:
        with open(pulse_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def write_pulse(
    echo_root: Path,
    session_id: str,
    last_action: str,
    context_summary: str = "",
    files_in_play: list = None,
    beat_count: int = 1,
) -> dict:
    """Write a heartbeat pulse."""
    now = datetime.now().isoformat()
    pulse = {
        "session_id": session_id,
        "last_beat": now,
        "beat_count": beat_count,
        "last_action": last_action,
        "context_summary": context_summary,
        "files_in_play": files_in_play or [],
        "started_at": None,
    }

    # Preserve started_at from existing pulse if same session
    existing = read_pulse(echo_root)
    if existing and existing.get("session_id") == session_id:
        pulse["started_at"] = existing.get("started_at", now)
        pulse["beat_count"] = existing.get("beat_count", 0) + 1
    else:
        pulse["started_at"] = now
        pulse["beat_count"] = 1

    pulse_path = get_pulse_path(echo_root)
    with open(pulse_path, "w") as f:
        json.dump(pulse, f, indent=2)

    return pulse


def flatline(echo_root: Path = None) -> Optional[dict]:
    """Stop the heart. Write a final pulse with flatline marker and return it."""
    root = echo_root or get_echo_root()
    pulse = read_pulse(root)
    if pulse is None:
        return None

    pulse["flatlined_at"] = datetime.now().isoformat()
    pulse["status"] = "flatlined"

    pulse_path = get_pulse_path(root)
    with open(pulse_path, "w") as f:
        json.dump(pulse, f, indent=2)

    return pulse


def is_ghost(pulse: dict, stale_minutes: int = 30) -> bool:
    """Check if a pulse represents a ghost (stale active session)."""
    if pulse is None:
        return False

    if pulse.get("status") == "flatlined":
        return False

    last_beat = pulse.get("last_beat")
    if not last_beat:
        return True

    try:
        beat_time = datetime.fromisoformat(last_beat)
        elapsed = (datetime.now() - beat_time).total_seconds() / 60
        return elapsed > stale_minutes
    except (ValueError, TypeError):
        return True


def minutes_since_last_beat(pulse: dict) -> Optional[float]:
    """How many minutes since the last heartbeat."""
    last_beat = pulse.get("last_beat")
    if not last_beat:
        return None
    try:
        beat_time = datetime.fromisoformat(last_beat)
        return (datetime.now() - beat_time).total_seconds() / 60
    except (ValueError, TypeError):
        return None


def detect_uncommitted_files(project_root: Path = None) -> Dict[str, List[str]]:
    """Detect uncommitted work in the git repository."""
    root = project_root or Path.cwd()

    result = {
        "untracked": [],
        "modified": [],
        "staged": [],
    }

    try:
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if untracked.returncode == 0 and untracked.stdout.strip():
            result["untracked"] = [
                f for f in untracked.stdout.strip().split("\n")
                if f and not f.startswith(".")
            ]

        modified = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if modified.returncode == 0 and modified.stdout.strip():
            result["modified"] = modified.stdout.strip().split("\n")

        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if staged.returncode == 0 and staged.stdout.strip():
            result["staged"] = staged.stdout.strip().split("\n")

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return result


def get_files_at_risk(project_root: Path = None) -> List[str]:
    """Get list of files that would be lost if session crashes."""
    uncommitted = detect_uncommitted_files(project_root)

    at_risk = []
    at_risk.extend(uncommitted.get("untracked", []))
    at_risk.extend(uncommitted.get("modified", []))

    significant = [
        f for f in at_risk
        if not any(skip in f for skip in [
            "moneta/highlights/",
            "echo/pulse.json",
            "__pycache__",
            ".pyc",
            "node_modules/",
            ".next/",
        ])
    ]

    return significant[:20]
