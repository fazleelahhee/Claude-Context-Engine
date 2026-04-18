"""Git helpers for session-start context — recent commits, working state, modified files."""
import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def get_recent_commits(project_dir: str, count: int = 10) -> list[str]:
    """Return the last N commits as short one-line strings."""
    output = _run_git(
        ["log", f"--oneline", f"-{count}"],
        cwd=project_dir,
    )
    return output.splitlines() if output else []


def get_working_state(project_dir: str) -> list[str]:
    """Return a summary of uncommitted changes and branch info."""
    lines: list[str] = []

    # Current branch
    branch = _run_git(["branch", "--show-current"], cwd=project_dir)
    if branch:
        lines.append(f"Branch: {branch}")

    # Ahead/behind relative to upstream
    tracking = _run_git(
        ["rev-list", "--left-right", "--count", f"{branch}@{{upstream}}...HEAD"],
        cwd=project_dir,
    )
    if tracking:
        parts = tracking.split()
        if len(parts) == 2:
            behind, ahead = parts
            if int(ahead) > 0:
                lines.append(f"Ahead of remote by {ahead} commit(s)")
            if int(behind) > 0:
                lines.append(f"Behind remote by {behind} commit(s)")

    # Staged changes
    staged = _run_git(["diff", "--cached", "--name-status"], cwd=project_dir)
    if staged:
        lines.append("Staged:")
        for line in staged.splitlines()[:10]:
            lines.append(f"  {line}")

    # Unstaged changes
    unstaged = _run_git(["diff", "--name-status"], cwd=project_dir)
    if unstaged:
        lines.append("Modified (unstaged):")
        for line in unstaged.splitlines()[:10]:
            lines.append(f"  {line}")

    # Untracked files (just count, not full list)
    untracked = _run_git(["ls-files", "--others", "--exclude-standard"], cwd=project_dir)
    if untracked:
        count = len(untracked.splitlines())
        lines.append(f"Untracked files: {count}")

    return lines


def get_recently_modified_files(project_dir: str, count: int = 5) -> list[str]:
    """Return file paths recently modified in git (last N commits + working tree)."""
    files: list[str] = []

    # Files changed in working tree
    wt_files = _run_git(["diff", "--name-only"], cwd=project_dir)
    if wt_files:
        files.extend(wt_files.splitlines())

    # Files changed in recent commits
    commit_files = _run_git(
        ["log", f"-{count}", "--pretty=format:", "--name-only"],
        cwd=project_dir,
    )
    if commit_files:
        files.extend(f for f in commit_files.splitlines() if f.strip())

    # Deduplicate, preserve order, filter to existing files
    seen: set[str] = set()
    result: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            if (Path(project_dir) / f).exists():
                result.append(f)
    return result[:15]
