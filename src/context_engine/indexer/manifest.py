"""Content hash manifest for incremental indexing."""
import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 2


class Manifest:
    def __init__(self, manifest_path: Path) -> None:
        self._path = manifest_path
        self._entries: dict[str, str] = {}
        self._schema_version: int = CURRENT_SCHEMA_VERSION
        self._last_git_sha: str | None = None

        if self._path.exists():
            try:
                with open(self._path) as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    if "__schema_version" in loaded:
                        # New versioned format
                        self._schema_version = loaded["__schema_version"]
                        self._entries = loaded.get("files", {})
                        self._last_git_sha = loaded.get("last_git_sha")
                    else:
                        # Old plain-dict format (pre-v0.2) — treat as version 1
                        self._schema_version = 1
                        self._entries = loaded
                else:
                    log.warning(
                        "Manifest at %s was not a dict (got %s); starting empty.",
                        self._path,
                        type(loaded).__name__,
                    )
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Manifest at %s unreadable (%s); starting empty.", self._path, exc)
                self._entries = {}

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def needs_reindex(self) -> bool:
        return self._schema_version != CURRENT_SCHEMA_VERSION

    @property
    def last_git_sha(self) -> str | None:
        return self._last_git_sha

    @last_git_sha.setter
    def last_git_sha(self, value: str | None) -> None:
        self._last_git_sha = value

    def get_hash(self, file_path: str) -> str | None:
        return self._entries.get(file_path)

    def update(self, file_path: str, content_hash: str) -> None:
        self._entries[file_path] = content_hash

    def remove(self, file_path: str) -> None:
        self._entries.pop(file_path, None)

    def has_changed(self, file_path: str, content_hash: str) -> bool:
        return self._entries.get(file_path) != content_hash

    def save(self) -> None:
        """Atomic save — write to a tempfile in the same dir then rename."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self._path.name + ".", suffix=".tmp", dir=str(self._path.parent)
        )
        payload = {
            "__schema_version": CURRENT_SCHEMA_VERSION,
            "files": self._entries,
            "last_git_sha": self._last_git_sha,
        }
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f)
            os.replace(tmp_name, self._path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
