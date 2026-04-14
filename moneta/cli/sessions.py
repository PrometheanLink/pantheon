"""Session management for Moneta CLI."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import get_sessions_path, load_config, get_moneta_root, get_current_branch


@dataclass
class Session:
    """Represents a Moneta session."""
    id: str
    ai_collaborator: str = ""
    started: str = ""
    status: str = "Active"
    part: str = ""
    has_plan: str = "No"
    plan_name: str = "—"
    instance: str = "local"
    branch: str = ""
    blockers: str = "None"
    files_touched: List[str] = field(default_factory=list)
    what_happened: str = ""
    decisions_made: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    file_path: Optional[Path] = None

    @property
    def filename(self) -> str:
        return f"{self.id}.md"


def parse_session_markdown(content: str, file_path: Path = None) -> Session:
    """Parse session markdown content into Session object."""
    id_match = re.search(r'^# Session: (.+)$', content, re.MULTILINE)
    session_id = id_match.group(1) if id_match else "unknown"

    session = Session(id=session_id, file_path=file_path)

    table_patterns = {
        r'\*\*AI Collaborator\*\*\s*\|\s*(.*)': 'ai_collaborator',
        r'\*\*Started\*\*\s*\|\s*(.*)': 'started',
        r'\*\*Status\*\*\s*\|\s*(.*)': 'status',
        r'\*\*Part\*\*\s*\|\s*(.*)': 'part',
        r'\*\*Has Plan\*\*\s*\|\s*(.*)': 'has_plan',
        r'\*\*Plan Name\*\*\s*\|\s*(.*)': 'plan_name',
        r'\*\*Instance\*\*\s*\|\s*(.*)': 'instance',
        r'\*\*Branch\*\*\s*\|\s*(.*)': 'branch',
        r'\*\*Blockers\*\*\s*\|\s*(.*)': 'blockers',
    }

    for pattern, attr in table_patterns.items():
        match = re.search(pattern, content)
        if match:
            value = match.group(1).strip().rstrip('|').strip()
            setattr(session, attr, value)

    files_section = re.search(r'## Files Touched\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if files_section:
        files = re.findall(r'^- (.+)$', files_section.group(1), re.MULTILINE)
        session.files_touched = [f.strip() for f in files if f.strip()]

    what_happened = re.search(r'## What Happened\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if what_happened:
        session.what_happened = what_happened.group(1).strip()

    decisions_section = re.search(r'## Decisions Made\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if decisions_section:
        decisions = re.findall(r'^- (.+)$', decisions_section.group(1), re.MULTILINE)
        session.decisions_made = [d.strip() for d in decisions if d.strip()]

    questions_section = re.search(r'## Open Questions\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if questions_section:
        questions = re.findall(r'^- (.+)$', questions_section.group(1), re.MULTILINE)
        session.open_questions = [q.strip() for q in questions if q.strip()]

    return session


def render_session_markdown(session: Session) -> str:
    """Render Session object to markdown format."""
    files_list = "\n".join(f"- {f}" for f in session.files_touched) if session.files_touched else "-"
    decisions_list = "\n".join(f"- {d}" for d in session.decisions_made) if session.decisions_made else "-"
    questions_list = "\n".join(f"- {q}" for q in session.open_questions) if session.open_questions else "-"

    return f"""# Session: {session.id}

| Field | Value |
|-------|-------|
| **AI Collaborator** | {session.ai_collaborator} |
| **Started** | {session.started} |
| **Status** | {session.status} |
| **Part** | {session.part} |
| **Has Plan** | {session.has_plan} |
| **Plan Name** | {session.plan_name} |
| **Instance** | {session.instance} |
| **Branch** | {session.branch} |
| **Blockers** | {session.blockers} |

## Files Touched
{files_list}

## What Happened
{session.what_happened}

## Decisions Made
{decisions_list}

## Open Questions
{questions_list}
"""


def list_sessions(moneta_root: Path = None, status_filter: Optional[str] = None) -> List[Session]:
    root = moneta_root or get_moneta_root()
    sessions_path = get_sessions_path(root)

    sessions = []
    for md_file in sessions_path.glob("*.md"):
        if md_file.name == ".gitkeep":
            continue
        try:
            content = md_file.read_text()
            session = parse_session_markdown(content, md_file)
            if status_filter is None or session.status.lower() == status_filter.lower():
                sessions.append(session)
        except Exception:
            continue

    sessions.sort(key=lambda s: s.started, reverse=True)
    return sessions


def get_session(session_id: str, moneta_root: Path = None) -> Optional[Session]:
    root = moneta_root or get_moneta_root()
    sessions_path = get_sessions_path(root)

    exact_path = sessions_path / f"{session_id}.md"
    if exact_path.exists():
        content = exact_path.read_text()
        return parse_session_markdown(content, exact_path)

    for md_file in sessions_path.glob("*.md"):
        if session_id in md_file.stem:
            content = md_file.read_text()
            return parse_session_markdown(content, md_file)

    return None


def get_active_session(moneta_root: Path = None, part: str = None) -> Optional[Session]:
    active_sessions = list_sessions(moneta_root, status_filter="Active")
    if part:
        matching = [s for s in active_sessions if s.part and s.part.lower() == part.lower()]
        return matching[0] if matching else None
    return active_sessions[0] if active_sessions else None


def get_all_active_sessions(moneta_root: Path = None) -> List[Session]:
    return list_sessions(moneta_root, status_filter="Active")


def create_session(
    description: str,
    moneta_root: Path = None,
    ai_collaborator: str = None,
    part: str = "",
    has_plan: bool = False,
    plan_name: str = "",
    instance: str = None,
    branch: str = None,
) -> Session:
    root = moneta_root or get_moneta_root()
    config = load_config(root)
    sessions_path = get_sessions_path(root, config)

    today = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', description.lower()).strip('-')
    max_slug = 80
    if len(slug) > max_slug:
        slug = slug[:max_slug].rstrip('-')
    session_id = f"{today}-{slug}"

    if branch is None and config.cli.auto_detect_branch:
        branch = get_current_branch() or ""

    session = Session(
        id=session_id,
        ai_collaborator=ai_collaborator or config.defaults.ai_collaborator,
        started=today,
        status="Active",
        part=part,
        has_plan="Yes" if has_plan else "No",
        plan_name=plan_name or "—",
        instance=instance or config.defaults.instance,
        branch=branch or "",
        blockers="None",
    )

    file_path = sessions_path / session.filename
    file_path.write_text(render_session_markdown(session))
    session.file_path = file_path

    return session


def update_session(
    session: Session,
    status: str = None,
    part: str = None,
    has_plan: bool = None,
    plan_name: str = None,
    blockers: str = None,
    add_files: List[str] = None,
    add_decision: str = None,
    add_question: str = None,
    what_happened: str = None,
) -> Session:
    if status is not None:
        session.status = status
    if part is not None:
        session.part = part
    if has_plan is not None:
        session.has_plan = "Yes" if has_plan else "No"
    if plan_name is not None:
        session.plan_name = plan_name or "—"
    if blockers is not None:
        session.blockers = blockers
    if add_files:
        session.files_touched.extend(add_files)
    if add_decision:
        session.decisions_made.append(add_decision)
    if add_question:
        session.open_questions.append(add_question)
    if what_happened is not None:
        session.what_happened = what_happened

    if session.file_path:
        session.file_path.write_text(render_session_markdown(session))

    return session


def end_session(session: Session) -> Session:
    return update_session(session, status="Completed")
