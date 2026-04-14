"""Highlight management for Moneta CLI."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import get_highlights_path, get_moneta_root


@dataclass
class Highlight:
    """Represents a Moneta highlight."""
    title: str
    date: str = ""
    session: str = ""
    severity: str = "Notable"
    category: str = "Pattern"
    discovery: str = ""
    context: str = ""
    resolution: str = ""
    promote_to_knowledge: bool = False
    file_path: Optional[Path] = None

    @property
    def filename(self) -> str:
        slug = re.sub(r'[^a-z0-9]+', '-', self.title.lower()).strip('-')
        max_slug = 80
        if len(slug) > max_slug:
            slug = slug[:max_slug].rstrip('-')
        return f"{self.date}-{slug}.md"


def parse_highlight_markdown(content: str, file_path: Path = None) -> Highlight:
    title_match = re.search(r'^# Highlight: (.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "Unknown"

    highlight = Highlight(title=title, file_path=file_path)

    table_patterns = {
        r'\*\*Date\*\*\s*\|\s*(.*)': 'date',
        r'\*\*Session\*\*\s*\|\s*(.*)': 'session',
        r'\*\*Severity\*\*\s*\|\s*(.*)': 'severity',
        r'\*\*Category\*\*\s*\|\s*(.*)': 'category',
    }

    for pattern, attr in table_patterns.items():
        match = re.search(pattern, content)
        if match:
            value = match.group(1).strip().rstrip('|').strip()
            setattr(highlight, attr, value)

    discovery_section = re.search(r'## Discovery\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if discovery_section:
        highlight.discovery = discovery_section.group(1).strip()

    context_section = re.search(r'## Context\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if context_section:
        highlight.context = context_section.group(1).strip()

    resolution_section = re.search(r'## Resolution / Action\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if resolution_section:
        highlight.resolution = resolution_section.group(1).strip()

    if re.search(r'- \[x\] Yes', content, re.IGNORECASE):
        highlight.promote_to_knowledge = True

    return highlight


def render_highlight_markdown(highlight: Highlight) -> str:
    promote_yes = "[x]" if highlight.promote_to_knowledge else "[ ]"
    promote_no = "[ ]" if highlight.promote_to_knowledge else "[x]"

    return f"""# Highlight: {highlight.title}

| Field | Value |
|-------|-------|
| **Date** | {highlight.date} |
| **Session** | {highlight.session} |
| **Severity** | {highlight.severity} |
| **Category** | {highlight.category} |

## Discovery
{highlight.discovery}

## Context
{highlight.context}

## Resolution / Action
{highlight.resolution}

## Promote to Knowledge Base?
- {promote_yes} Yes → Move to knowledge/lessons/
- {promote_no} No → Archive after weekly summary
"""


def list_highlights(
    moneta_root: Path = None,
    severity_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
) -> List[Highlight]:
    root = moneta_root or get_moneta_root()
    highlights_path = get_highlights_path(root)

    highlights = []
    for md_file in highlights_path.glob("*.md"):
        if md_file.name == ".gitkeep":
            continue
        try:
            content = md_file.read_text()
            highlight = parse_highlight_markdown(content, md_file)
            if severity_filter and highlight.severity.lower() != severity_filter.lower():
                continue
            if category_filter and highlight.category.lower() != category_filter.lower():
                continue
            highlights.append(highlight)
        except Exception:
            continue

    highlights.sort(key=lambda h: h.date, reverse=True)
    return highlights


def get_critical_highlights(moneta_root: Path = None) -> List[Highlight]:
    highlights = list_highlights(moneta_root)
    return [h for h in highlights if h.severity.lower() in ("critical", "important")]


def create_highlight(
    description: str,
    moneta_root: Path = None,
    severity: str = "Notable",
    category: str = "Pattern",
    session: str = "",
    discovery: str = "",
    context: str = "",
    resolution: str = "",
) -> Highlight:
    root = moneta_root or get_moneta_root()
    highlights_path = get_highlights_path(root)

    today = datetime.now().strftime("%Y-%m-%d")

    highlight = Highlight(
        title=description,
        date=today,
        session=session,
        severity=severity,
        category=category,
        discovery=discovery or description,
        context=context,
        resolution=resolution,
    )

    file_path = highlights_path / highlight.filename
    file_path.write_text(render_highlight_markdown(highlight))
    highlight.file_path = file_path

    return highlight
