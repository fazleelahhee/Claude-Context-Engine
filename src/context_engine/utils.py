"""Shared utilities for CCE."""
import os
import shutil
import sys
from pathlib import Path


def resolve_cce_binary() -> str:
    """Find the globally installed cce binary path.

    Checks ~/.local/bin/cce, /usr/local/bin/cce, shutil.which,
    then falls back to sys.argv[0] if it looks like cce, or bare "cce".
    """
    for candidate in [
        Path.home() / ".local" / "bin" / "cce",
        Path("/usr/local/bin/cce"),
    ]:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    found = shutil.which("cce")
    if found:
        return found
    arg0 = Path(sys.argv[0]).resolve()
    if arg0.name in ("cce", "claude-context-engine"):
        return str(arg0)
    return "cce"
