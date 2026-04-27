"""Shared utilities for CCE."""
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Iterator, TypeVar

T = TypeVar("T")

# SQLite has a hard limit on bound parameters per statement
# (SQLITE_MAX_VARIABLE_NUMBER, historically 999, modernly 32766). We default
# to 500 — well under both — so that delete/select-by-file paths don't fail
# on full-project prunes that touch hundreds of files. Two stores often need
# 2× the placeholder count (e.g. node_ids appearing in source + target),
# which 500 still keeps under 999.
SQLITE_PARAM_BATCH = 500


def chunked(items: Iterable[T], size: int = SQLITE_PARAM_BATCH) -> Iterator[list[T]]:
    """Yield `items` as lists of up to `size`. Empty iterables yield nothing."""
    if size <= 0:
        raise ValueError("size must be positive")
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def atomic_write_text(path: Path, data: str) -> None:
    """Write `data` to `path` durably, via tempfile + fsync + os.replace.

    A plain `path.write_text(data)` truncates the target before writing, so a
    crash mid-write leaves a zero-byte or partial file. The next load reads
    that as `{}` and silently loses everything.

    Sequence (POSIX):
      1. write to a tempfile in the same directory (so rename stays on the
         same filesystem and can be atomic),
      2. flush + fsync the tempfile so the bytes are on durable media,
      3. os.replace — atomic on POSIX,
      4. fsync the parent directory so the rename itself is durable across
         crashes (otherwise on ext4/xfs the directory entry can still be
         lost on power-loss, leaving the old file).

    Encoding is pinned to UTF-8 — relying on the locale-default makes
    cross-platform behaviour unstable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
        # fsync the parent dir so the rename is durable. Best-effort: not all
        # platforms support directory fds (Windows in particular), and some
        # filesystems return EINVAL — neither should fail the write.
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except (OSError, AttributeError):
            pass
    except Exception:
        # Best-effort cleanup if anything went wrong before the rename.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


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
