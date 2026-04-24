"""Shared CLI styling — consistent colorful output across all cce commands."""
import sys
import time

import click


# ── Colors ─────────────────────────────────────────────────────────────
# Cyan for headers/labels, green for success, yellow for warnings,
# dim white for secondary info, bold for emphasis.

def header(text: str) -> str:
    return click.style(text, fg="cyan", bold=True)

def label(text: str) -> str:
    return click.style(text, fg="cyan")

def success(text: str) -> str:
    return click.style(text, fg="green")

def warn(text: str) -> str:
    return click.style(text, fg="yellow")

def error(text: str) -> str:
    return click.style(text, fg="red")

def dim(text: str) -> str:
    return click.style(text, dim=True)

def bold(text: str) -> str:
    return click.style(text, bold=True)

def value(text: str) -> str:
    return click.style(text, fg="white", bold=True)

def magenta(text: str) -> str:
    return click.style(text, fg="magenta")


# ── Prefixes ───────────────────────────────────────────────────────────

CHECK = click.style("✓", fg="green")
CROSS = click.style("✗", fg="red")
DOT = click.style("·", fg="yellow")
ARROW = click.style("→", fg="cyan")
BULLET = click.style("●", fg="green")
BULLET_OFF = click.style("○", fg="yellow")


# ── Section headers ────────────────────────────────────────────────────

def section(title: str, width: int = 50) -> str:
    """Render a styled section divider: ── Title ──────────"""
    bar = "─" * max(1, width - len(title) - 4)
    return f"  {dim('──')} {header(title)} {dim(bar)}"


# ── Animation ──────────────────────────────────────────────────────────

def animate(lines: list[str], delay: float = 0.025) -> None:
    """Print lines with a reveal animation on TTY, instant otherwise."""
    is_tty = sys.stdout.isatty()
    for i, line in enumerate(lines):
        click.echo(line)
        if is_tty and i < 12 and delay > 0:
            time.sleep(delay)
