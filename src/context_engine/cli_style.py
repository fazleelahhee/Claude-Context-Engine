"""Shared CLI styling — consistent colorful output across all cce commands."""
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


# ── Prefixes ───────────────────────────────────────────────────────────

CHECK = click.style("✓", fg="green")
CROSS = click.style("✗", fg="red")
DOT = click.style("·", fg="yellow")
ARROW = click.style("→", fg="cyan")
