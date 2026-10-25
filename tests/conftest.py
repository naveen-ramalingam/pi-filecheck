import os
from pathlib import Path

import pytest

from pi_filecheck.config import Config


@pytest.fixture(autouse=True)
def isolated_user(tmp_path, monkeypatch):
    home = tmp_path.resolve() / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))


@pytest.fixture
def config(tmp_path):
    root = tmp_path.resolve() / "downloads"
    root.mkdir()
    return Config(scan_path=str(root), report_dir=str(tmp_path.resolve() / "reports"))


@pytest.fixture
def root(config):
    return Path(config.scan_path)


@pytest.fixture
def cli_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return env
