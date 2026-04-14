"""Configuration management for Moneta CLI."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class PathsConfig:
    """Paths configuration."""
    sessions: str = "sessions"
    highlights: str = "highlights"
    summaries: str = "summaries"


@dataclass
class AIConfig:
    """AI provider configuration."""
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"


@dataclass
class WeeklyConfig:
    """Weekly summary configuration."""
    purge_after_summary: bool = True
    summary_day: str = "sunday"


@dataclass
class CLIConfig:
    """CLI configuration."""
    colored_output: bool = True
    auto_detect_branch: bool = True


@dataclass
class DefaultsConfig:
    """Default values configuration."""
    ai_collaborator: str = "Claude"
    instance: str = "local"


@dataclass
class MonetaConfig:
    """Main Moneta configuration."""
    version: str = "1.0"
    paths: PathsConfig = field(default_factory=PathsConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    weekly: WeeklyConfig = field(default_factory=WeeklyConfig)
    cli: CLIConfig = field(default_factory=CLIConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)

    @classmethod
    def from_file(cls, path: Path) -> "MonetaConfig":
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        config = cls()
        config.version = data.get("version", "1.0")

        if "paths" in data:
            p = data["paths"]
            config.paths = PathsConfig(
                sessions=p.get("sessions", "sessions"),
                highlights=p.get("highlights", "highlights"),
                summaries=p.get("summaries", "summaries"),
            )

        if "ai" in data:
            ai = data["ai"]
            config.ai = AIConfig(
                provider=ai.get("provider", "openai"),
                model=ai.get("model", "gpt-4o-mini"),
                api_key_env=ai.get("api_key_env", "OPENAI_API_KEY"),
            )

        if "weekly" in data:
            w = data["weekly"]
            config.weekly = WeeklyConfig(
                purge_after_summary=w.get("purge_after_summary", True),
                summary_day=w.get("summary_day", "sunday"),
            )

        if "cli" in data:
            c = data["cli"]
            config.cli = CLIConfig(
                colored_output=c.get("colored_output", True),
                auto_detect_branch=c.get("auto_detect_branch", True),
            )

        if "defaults" in data:
            d = data["defaults"]
            config.defaults = DefaultsConfig(
                ai_collaborator=d.get("ai_collaborator", "Claude"),
                instance=d.get("instance", "local"),
            )

        return config


def find_moneta_root(start_path: Path = None) -> Optional[Path]:
    """Find Moneta root by looking for moneta.yaml."""
    path = start_path or Path.cwd()

    candidates = [
        path / "moneta.yaml",
        path / "moneta" / "moneta.yaml",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.parent

    for parent in path.parents:
        candidate = parent / "moneta" / "moneta.yaml"
        if candidate.exists():
            return candidate.parent
        candidate = parent / "moneta.yaml"
        if candidate.exists():
            return candidate.parent

    return None


def get_moneta_root() -> Path:
    """Get Moneta root directory or raise error."""
    root = find_moneta_root()
    if root is None:
        raise FileNotFoundError(
            "Moneta not found. Run from within a project with moneta/ directory "
            "or moneta.yaml config file."
        )
    return root


def get_config_path(moneta_root: Path = None) -> Path:
    root = moneta_root or get_moneta_root()
    return root / "moneta.yaml"


def load_config(moneta_root: Path = None) -> MonetaConfig:
    root = moneta_root or get_moneta_root()
    config_path = get_config_path(root)
    return MonetaConfig.from_file(config_path)


def get_sessions_path(moneta_root: Path = None, config: MonetaConfig = None) -> Path:
    root = moneta_root or get_moneta_root()
    cfg = config or load_config(root)
    return root / cfg.paths.sessions


def get_highlights_path(moneta_root: Path = None, config: MonetaConfig = None) -> Path:
    root = moneta_root or get_moneta_root()
    cfg = config or load_config(root)
    return root / cfg.paths.highlights


def get_summaries_path(moneta_root: Path = None, config: MonetaConfig = None) -> Path:
    root = moneta_root or get_moneta_root()
    cfg = config or load_config(root)
    return root / cfg.paths.summaries


def get_current_branch() -> Optional[str]:
    """Get current git branch name."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
