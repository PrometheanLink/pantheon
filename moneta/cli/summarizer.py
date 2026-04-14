"""AI-powered summarization for Moneta CLI."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .config import (
    get_moneta_root,
    get_summaries_path,
    load_config,
)
from .sessions import Session, list_sessions, render_session_markdown
from .highlights import Highlight, list_highlights


_openai_client = None


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
            _openai_client = OpenAI()
        except ImportError:
            raise ImportError("OpenAI package not installed. Run: pip install openai")
    return _openai_client


WEEKLY_SUMMARY_PROMPT = """You are analyzing session logs from a software development project. Create a weekly summary with the following sections:

1. **Week Overview** (2-3 sentences capturing the main themes)
2. **Work Areas** (bullet list of domains/features worked on)
3. **Key Decisions** (important architectural or design decisions made)
4. **Learnings & Discoveries** (new knowledge gained, gotchas discovered)
5. **Patterns Observed** (recurring themes, workflow improvements)
6. **Resolved Blockers** (problems that were solved)
7. **Open Questions** (unresolved items carrying forward)

Be concise but comprehensive. Focus on actionable insights and knowledge preservation.

Here are the session logs to analyze:

---
{sessions_content}
---

{highlights_content}

Generate the weekly summary in Markdown format."""


def summarize_sessions(
    moneta_root: Path = None,
    dry_run: bool = False,
    purge: bool = None,
) -> Dict[str, Any]:
    root = moneta_root or get_moneta_root()
    config = load_config(root)

    sessions = list_sessions(root)
    highlights = list_highlights(root)

    if not sessions and not highlights:
        return {
            "summary_file": None,
            "sessions_count": 0,
            "highlights_count": 0,
            "purged": False,
        }

    sessions_content = "\n\n---\n\n".join(
        render_session_markdown(s) for s in sessions
    )

    if highlights:
        highlights_content = "\n\nHighlights this week:\n" + "\n".join(
            f"- **{h.title}** ({h.severity}, {h.category}): {h.discovery[:200]}..."
            for h in highlights
        )
    else:
        highlights_content = ""

    prompt = WEEKLY_SUMMARY_PROMPT.format(
        sessions_content=sessions_content,
        highlights_content=highlights_content,
    )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=config.ai.model,
        messages=[
            {"role": "system", "content": "You are a technical project analyst creating weekly summaries."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    ai_summary = response.choices[0].message.content

    today = datetime.now().strftime("%Y-%m-%d")
    summary_content = f"""# Weekly Summary: Week of {today}

## Sessions Analyzed
{len(sessions)} session(s), {len(highlights)} highlight(s)

{ai_summary}
"""

    result = {
        "content": summary_content,
        "sessions_count": len(sessions),
        "highlights_count": len(highlights),
        "ai_summary": ai_summary,
    }

    if dry_run:
        result["summary_file"] = None
        result["purged"] = False
        return result

    summaries_path = get_summaries_path(root, config)
    summary_file = summaries_path / f"week-of-{today}.md"
    summary_file.write_text(summary_content)
    result["summary_file"] = summary_file

    should_purge = purge if purge is not None else config.weekly.purge_after_summary
    if should_purge:
        from .sessions import get_sessions_path
        purged_count = 0
        for session in sessions:
            if session.file_path and session.file_path.exists():
                session.file_path.unlink()
                purged_count += 1
        result["purged"] = True
        result["purged_count"] = purged_count
    else:
        result["purged"] = False

    return result


def get_schedule_info(moneta_root: Path = None) -> Dict[str, Any]:
    root = moneta_root or get_moneta_root()
    config = load_config(root)
    summaries_path = get_summaries_path(root, config)

    summaries = sorted(summaries_path.glob("week-of-*.md"), reverse=True)
    last_summary = summaries[0] if summaries else None

    return {
        "summary_day": config.weekly.summary_day,
        "purge_after_summary": config.weekly.purge_after_summary,
        "last_summary": last_summary,
        "summaries_count": len(summaries),
    }
