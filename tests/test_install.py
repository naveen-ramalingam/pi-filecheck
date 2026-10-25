import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.install
def test_clean_install_cli_and_uninstall(tmp_path, cli_env):
    """Build a local wheel then install offline into a disposable per-user prefix."""
    wheels = tmp_path.resolve() / "wheels"
    wheels.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheels),
            str(REPO),
        ],
        check=True,
        capture_output=True,
        env=cli_env,
    )
    wheel = next(wheels.glob("pi_filecheck-*.whl"))
    prefix = tmp_path.resolve() / "install space"
    downloads = tmp_path.resolve() / "downloads"
    downloads.mkdir()
    (downloads / "data.pkg").write_bytes(b"data")
    env = {**cli_env, "PYTHON": sys.executable}
    installed = subprocess.run(
        [str(REPO / "install.sh"), "--prefix", str(prefix), "--offline", "--wheel", str(wheel)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    command = prefix / "bin/filecheck"
    assert command.is_symlink()
    smoke_env = env.copy()
    smoke_env.pop("PYTHONPATH", None)

    def invoke(*argv):
        return subprocess.run(
            [str(command), *argv], env=smoke_env, capture_output=True, text=True, check=False
        )

    assert invoke("version").returncode == 0
    assert invoke("config", "set", "scan_path", str(downloads)).returncode == 0
    assert invoke("scan", "--yes", "--format", "json").returncode == 1
    reports = Path(env["XDG_STATE_HOME"]) / "pi-filecheck/reports"
    assert list(reports.glob("*/report.json"))
    # Reinstall must refuse an existing command instead of overwriting it.
    again = subprocess.run(
        [str(REPO / "install.sh"), "--prefix", str(prefix), "--offline", "--wheel", str(wheel)],
        env=env,
        capture_output=True,
        check=False,
    )
    assert again.returncode == 2
    unrelated = prefix / "keep-me"
    unrelated.write_text("unrelated", encoding="utf-8")
    extra = prefix / "share/pi-filecheck/venv/user-note.txt"
    extra.write_text("user-added file", encoding="utf-8")
    refused = subprocess.run(
        [str(REPO / "uninstall.sh"), "--prefix", str(prefix)],
        env=env,
        capture_output=True,
        check=False,
    )
    assert refused.returncode == 2
    assert command.is_symlink()
    assert extra.read_text() == "user-added file"
    extra.unlink()  # Remove only this test's newly created fixture, then retry.
    removed = subprocess.run(
        [str(REPO / "uninstall.sh"), "--prefix", str(prefix)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert removed.returncode == 0, removed.stderr
    assert not os.path.lexists(command)
    assert unrelated.read_text() == "unrelated"
    assert list(reports.glob("*/report.json"))
    assert (Path(env["XDG_CONFIG_HOME"]) / "pi-filecheck/config.toml").exists()


def test_uninstall_without_marker_refused(tmp_path, cli_env):
    prefix = tmp_path.resolve() / "unmanaged"
    prefix.mkdir()
    original = prefix / "keep-me"
    original.write_text("safe", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/manage_install.py"),
            "uninstall",
            "--prefix",
            str(prefix),
        ],
        env=cli_env,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert original.read_text() == "safe"
