"""Shared utilities for CCE."""
import os
import shutil
import sys
from pathlib import Path


def resolve_cce_binary() -> str:
    """Find the globally installed cce binary path.

    Checks user-local then system install paths across both Linux and macOS
    (Homebrew on Apple Silicon installs to /opt/homebrew/bin), then PATH,
    then sys.argv[0] if it looks like cce, then a bare "cce" fallback.
    """
    candidates = [
        Path.home() / ".local" / "bin" / "cce",   # pipx / uv tool default (Linux + macOS)
        Path("/opt/homebrew/bin/cce"),            # macOS Homebrew on Apple Silicon
        Path("/usr/local/bin/cce"),               # macOS Homebrew on Intel + Linux /usr/local
        Path("/opt/local/bin/cce"),               # MacPorts
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    found = shutil.which("cce")
    if found:
        return found
    arg0 = Path(sys.argv[0]).resolve()
    if arg0.name in ("cce", "claude-context-engine"):
        return str(arg0)
    return "cce"
