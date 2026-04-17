"""Configuration loading — global + per-project with defaults."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml


DEFAULT_GLOBAL_PATH = Path.home() / ".claude-context-engine" / "config.yaml"
PROJECT_CONFIG_NAME = ".context-engine.yaml"

DEFAULT_IGNORE = [".git", "node_modules", "__pycache__", ".venv", ".env"]


@dataclass
class Config:
    # Compression
    compression_level: str = "standard"
    compression_model: str = "phi3:mini"

    # Output compression
    output_compression: str = "standard"  # off | lite | standard | max

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Retrieval
    retrieval_confidence_threshold: float = 0.5
    retrieval_top_k: int = 20
    bootstrap_max_tokens: int = 10000

    # Indexer
    indexer_watch: bool = True
    indexer_debounce_ms: int = 500
    indexer_ignore: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE))
    indexer_languages: list[str] = field(default_factory=list)

    # Storage
    storage_path: str = str(Path.home() / ".claude-context-engine" / "projects")

    def detect_resource_profile(self) -> str:
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        except ImportError:
            ram_gb = 16
        if ram_gb >= 32:
            return "full"
        if ram_gb >= 12:
            return "standard"
        return "light"


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


_EXPECTED_TYPES: dict[str, type | tuple[type, ...]] = {
    "compression_level": str,
    "compression_model": str,
    "output_compression": str,
    "embedding_model": str,
    "retrieval_confidence_threshold": (int, float),
    "retrieval_top_k": int,
    "bootstrap_max_tokens": int,
    "indexer_watch": bool,
    "indexer_debounce_ms": int,
    "indexer_ignore": list,
    "indexer_languages": list,
    "storage_path": str,
}


def _apply_dict_to_config(config: Config, data: dict) -> None:
    mapping = {
        ("compression", "level"): "compression_level",
        ("compression", "model"): "compression_model",
        ("compression", "output"): "output_compression",
        ("embedding", "model"): "embedding_model",
        ("retrieval", "confidence_threshold"): "retrieval_confidence_threshold",
        ("retrieval", "top_k"): "retrieval_top_k",
        ("retrieval", "bootstrap_max_tokens"): "bootstrap_max_tokens",
        ("indexer", "watch"): "indexer_watch",
        ("indexer", "debounce_ms"): "indexer_debounce_ms",
        ("indexer", "ignore"): "indexer_ignore",
        ("indexer", "languages"): "indexer_languages",
        ("storage", "path"): "storage_path",
    }
    for (section, key), attr in mapping.items():
        if section in data and isinstance(data[section], dict) and key in data[section]:
            value = data[section][key]
            expected = _EXPECTED_TYPES.get(attr)
            if expected is not None and not isinstance(value, expected):
                # `bool` is a subclass of `int`, so guard against that edge case.
                if expected is int and isinstance(value, bool):
                    raise ValueError(
                        f"Config {section}.{key} must be int, got bool ({value!r})"
                    )
                raise ValueError(
                    f"Config {section}.{key} must be "
                    f"{getattr(expected, '__name__', expected)}, "
                    f"got {type(value).__name__} ({value!r})"
                )
            setattr(config, attr, value)


def load_config(
    global_path: Path | None = None,
    project_path: Path | None = None,
) -> Config:
    global_path = global_path or DEFAULT_GLOBAL_PATH
    config = Config()

    global_data: dict = {}
    if global_path.exists():
        with open(global_path) as f:
            global_data = yaml.safe_load(f) or {}

    project_data: dict = {}
    if project_path and project_path.exists():
        with open(project_path) as f:
            project_data = yaml.safe_load(f) or {}

    merged = _deep_merge(global_data, project_data)
    _apply_dict_to_config(config, merged)
    return config
