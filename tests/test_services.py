"""Tests for services.py — PID utilities and status checks."""
import os
import signal
from pathlib import Path

import pytest

from context_engine.services import (
    _pid_dir,
    _read_pid,
    _write_pid,
    _remove_pid,
    _process_alive,
    _check_port_open,
    get_dashboard_status,
)


# ── PID utilities ────────────────────────────────────────────────────────────

def test_write_and_read_pid(tmp_path, monkeypatch):
    monkeypatch.setattr("context_engine.services._pid_dir", lambda: tmp_path)
    _write_pid("testservice", 12345)
    assert _read_pid("testservice") == 12345


def test_read_pid_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("context_engine.services._pid_dir", lambda: tmp_path)
    assert _read_pid("nonexistent") is None


def test_remove_pid(tmp_path, monkeypatch):
    monkeypatch.setattr("context_engine.services._pid_dir", lambda: tmp_path)
    _write_pid("testservice", 99)
    _remove_pid("testservice")
    assert _read_pid("testservice") is None


def test_remove_pid_noop_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("context_engine.services._pid_dir", lambda: tmp_path)
    _remove_pid("nonexistent")  # must not raise


# ── Process alive check ───────────────────────────────────────────────────────

def test_process_alive_self():
    assert _process_alive(os.getpid()) is True


def test_process_alive_dead_pid():
    import subprocess
    proc = subprocess.Popen(["true"])
    proc.wait()
    assert _process_alive(proc.pid) is False


# ── Port check ────────────────────────────────────────────────────────────────

def test_check_port_open_closed():
    # Port 19999 is almost certainly not in use
    assert _check_port_open(19999) is False


# ── Dashboard status when nothing is running ─────────────────────────────────

def test_get_dashboard_status_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr("context_engine.services._pid_dir", lambda: tmp_path)
    status = get_dashboard_status()
    assert status["running"] is False
    assert status["name"] == "dashboard"
