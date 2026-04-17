"""Content hash manifest for incremental indexing."""
import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


class Manifest:
    def __init__(self, manifest_path: Path) -> None:
        self._path = manifest_path
        self._entries: dict[str, str] = {}
        if self._path.exists():
            try:
                with open(self._path) as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._entries = loaded
                else:
                    log.warning(
                        "Manifest at %s was not a dict (got %s); starting empty.",
                        self._path,
                        type(loaded).__name__,
                    )
            except (json.JSONDecodeError, OSError) as exc:
                # A partial write or corruption shouldn't kill the whole index.
                log.warning("Manifest at %s unreadable (%s); starting empty.", self._path, exc)
                self._entries = {}

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
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._entries, f)
            os.replace(tmp_name, self._path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
