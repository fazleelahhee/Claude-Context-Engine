import os
import tempfile
from pathlib import Path

import yaml

from context_engine.config import Config, load_config


def test_default_config():
    config = Config()
    assert config.compression_level == "standard"
    assert config.embedding_model == "BAAI/bge-small-en-v1.5"
    assert config.retrieval_top_k == 20
    assert config.indexer_watch is True


def test_load_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "compression": {"level": "full", "model": "phi3:mini"},
        "retrieval": {"top_k": 50},
    }))
    config = load_config(global_path=config_file)
    assert config.compression_level == "full"
    assert config.compression_model == "phi3:mini"
    assert config.retrieval_top_k == 50


def test_project_override(tmp_path):
    global_file = tmp_path / "config.yaml"
    global_file.write_text(yaml.dump({
        "compression": {"level": "standard"},
        "indexer": {"ignore": [".git"]},
    }))
    project_file = tmp_path / ".context-engine.yaml"
    project_file.write_text(yaml.dump({
        "compression": {"level": "full"},
        "indexer": {"ignore": [".git", "dist"]},
    }))
    config = load_config(global_path=global_file, project_path=project_file)
    assert config.compression_level == "full"
    assert "dist" in config.indexer_ignore


def test_resource_profile_auto_detect():
    config = Config()
    profile = config.detect_resource_profile()
    assert profile in ("light", "standard", "full")
