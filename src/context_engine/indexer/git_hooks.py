"""Git hook installer and handler for triggering re-indexing."""
import os
import stat
from pathlib import Path

HOOK_MARKER = "# claude-context-engine hook"
HOOK_SCRIPT = f"""{HOOK_MARKER}
claude-context-engine index --changed-only 2>/dev/null &
"""
HOOK_NAMES = ["post-commit", "post-checkout", "post-merge"]


def install_hooks(project_dir: str) -> list[str]:
    hooks_dir = Path(project_dir) / ".git" / "hooks"
    if not hooks_dir.exists():
        raise FileNotFoundError(f"Git hooks directory not found: {hooks_dir}")
    installed = []
    for hook_name in HOOK_NAMES:
        hook_path = hooks_dir / hook_name
        _install_single_hook(hook_path)
        installed.append(str(hook_path))
    return installed


def _install_single_hook(hook_path: Path) -> None:
    if hook_path.exists():
        existing = hook_path.read_text()
        if HOOK_MARKER in existing:
            return
        new_content = existing.rstrip() + "\n\n" + HOOK_SCRIPT
    else:
        new_content = "#!/bin/sh\n\n" + HOOK_SCRIPT
    hook_path.write_text(new_content)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)


def get_changed_files_from_hook() -> list[str]:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []
