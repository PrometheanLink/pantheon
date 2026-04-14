"""Terminal output utilities for Moneta CLI."""

import sys


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def colored(text: str, color: str, use_color: bool = True) -> str:
    if use_color:
        return f"{color}{text}{Colors.ENDC}"
    return text


def print_success(msg: str, use_color: bool = True):
    print(colored(f"✓ {msg}", Colors.GREEN, use_color))


def print_error(msg: str, use_color: bool = True):
    print(colored(f"✗ {msg}", Colors.FAIL, use_color), file=sys.stderr)


def print_warning(msg: str, use_color: bool = True):
    print(colored(f"! {msg}", Colors.WARNING, use_color))


def print_info(msg: str, use_color: bool = True):
    print(colored(f"→ {msg}", Colors.CYAN, use_color))


def print_header(msg: str, use_color: bool = True):
    print(colored(msg, Colors.BOLD + Colors.HEADER, use_color))
