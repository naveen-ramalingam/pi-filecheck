import hashlib
import json
import os
import pty
import select
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

import pytest

from pi_filecheck import __version__
from pi_filecheck import config as cfg
from pi_filecheck.cli import main
from pi_filecheck.models import Result


def test_version_consistency(capsys):
    repo = Path(__file__).resolve().parents[1]
    assert (repo / "VERSION").read_text().strip() == __version__
    assert version("pi-filecheck") == __version__
    assert main(["version"]) == 0
    assert __version__ in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv", [["--help"], ["scan", "--help"], ["config", "--help"], ["--version"]]
)
def test_help(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 0


def test_menu_opens_in_real_terminal(cli_env):
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [sys.executable, "-m", "pi_filecheck"], stdin=slave, stdout=slave, stderr=slave, env=cli_env
    )
    os.close(slave)
    captured = bytearray()
    try:
        deadline = time.monotonic() + 10
        while b"Choice:" not in captured and time.monotonic() < deadline:
            if select.select([master], [], [], 0.2)[0]:
                captured.extend(os.read(master, 8192))
        assert b"Choose another folder" in captured
        assert b"Free space" in captured or b"missing" in captured
        os.write(master, b"0\n")
        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)


def test_no_tty_menu_gives_guidance(cli_env):
    completed = subprocess.run(
        [sys.executable, "-m", "pi_filecheck"],
        input="",
        text=True,
        capture_output=True,
        env=cli_env,
        check=False,
    )
    assert completed.returncode == 2
    assert "needs a terminal" in completed.stderr


def test_json_stdout_and_reports(root, config, capsys):
    cfg.save(config)
    (root / "game.pkg").write_bytes(b"data")
    assert main(["scan", "--format", "json"]) == 1
    document = json.loads(capsys.readouterr().out)
    assert document["summary"]["UNKNOWN"] == 1
    bundles = list(Path(config.report_dir).iterdir())
    assert len(bundles) == 1
    assert {p.name for p in bundles[0].iterdir()} == {"report.json", "report.csv", "details.log"}
    assert json.loads((bundles[0] / "report.json").read_text()) == document


@pytest.mark.parametrize("command,expected", [("identify", 1), ("test", 1), ("hash", 1)])
def test_inconclusive_exit_codes(root, capsys, command, expected):
    path = root / "game.pkg"
    path.write_bytes(b"data")
    assert main([command, str(path), "--no-report"]) == expected
    assert "UNKNOWN" in capsys.readouterr().out


def test_hash_comparison_exit_codes(root, capsys):
    path = root / "file.pkg"
    path.write_bytes(b"data")
    assert (
        main(
            [
                "hash",
                str(path),
                "--expected-sha256",
                hashlib.sha256(b"data").hexdigest(),
                "--no-report",
            ]
        )
        == 0
    )
    assert "PASS" in capsys.readouterr().out
    assert main(["hash", str(path), "--expected-sha256", "0" * 64, "--no-report"]) == 1


def test_corrupt_exit_and_error_exit(root, capsys):
    path = root / "bad.zip"
    path.write_bytes(b"invalid")
    assert main(["test", str(path), "--no-report"]) == 1
    assert "FAIL" in capsys.readouterr().out
    assert main(["test", str(root / "missing"), "--no-report"]) == 2


def test_operational_error_json_is_parseable(root, capsys):
    assert main(["test", str(root / "missing.zip"), "--format", "json", "--no-report"]) == 2
    document = json.loads(capsys.readouterr().out)
    assert document["results"][0]["status"] == "ERROR"


def test_missing_scan_path(config, capsys):
    cfg.save(config)
    assert main(["scan", str(Path(config.scan_path) / "missing"), "--no-report"]) == 2
    assert "missing" in capsys.readouterr().err


def test_expensive_noninteractive_requires_yes(config, root, capsys):
    config.confirm_bytes = 1
    cfg.save(config)
    (root / "x.pkg").write_bytes(b"data")
    assert main(["scan", str(root), "--no-report"]) == 2
    assert "--yes" in capsys.readouterr().err
    assert main(["scan", str(root), "--yes", "--no-report"]) == 1


def test_interruption_saves_partial_json(config, root, capsys, monkeypatch):
    cfg.save(config)
    (root / "file.pkg").touch()

    def interrupted(entries, config, requested, progress, results):
        results.append(Result(str(root / "done.pkg")))
        raise KeyboardInterrupt

    monkeypatch.setattr("pi_filecheck.cli.scan_entries", interrupted)
    assert main(["scan", str(root), "--format", "json"]) == 130
    document = json.loads(capsys.readouterr().out)
    assert document["interrupted"] is True
    assert len(document["results"]) == 2
    assert document["summary"]["ERROR"] == 1
    assert list(Path(config.report_dir).glob("*/report.json"))


def test_doctor_and_config(config, capsys):
    cfg.save(config)
    assert main(["doctor", "--format", "json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert "machine" in document
    assert "tools" in document
    assert main(["config", "show"]) == 0
    assert json.loads(capsys.readouterr().out)["scan_path"] == config.scan_path


def test_report_source_collision_refused(root, capsys):
    path = root / "source.pkg"
    path.write_bytes(b"original")
    assert main(["identify", str(path), "--output", str(path), "--no-report"]) == 2
    assert path.read_bytes() == b"original"


def test_path_arguments_and_timeout_validation(root, capsys):
    assert main(["scan", str(root), "--path", str(root), "--no-report"]) == 2
    assert main(["scan", str(root), "--timeout", "0", "--no-report"]) == 2


def test_read_last_report(config, root, capsys):
    cfg.save(config)
    (root / "one.pkg").touch()
    assert main(["scan", "--format", "json"]) == 1
    original = json.loads(capsys.readouterr().out)
    assert main(["report", "--format", "json"]) == 1
    assert json.loads(capsys.readouterr().out) == original
