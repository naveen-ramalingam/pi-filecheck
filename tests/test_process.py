import sys

import pytest

from pi_filecheck.process import Completed, run
from pi_filecheck.validators import validate


def test_timeout_kills_process():
    completed = run([sys.executable, "-c", "import time; time.sleep(20)"], 0.15)
    assert "time limit" in completed.error
    assert completed.code < 0


def test_output_bounded():
    completed = run([sys.executable, "-c", "print('x'*200000)"], 10, output_limit=4096)
    assert "diagnostic limit" in completed.error
    assert len(completed.output) == 4096


def test_discarded_listing_cannot_fill_error_diagnostics():
    code = "import sys; print('x'*200000); print('error details',file=sys.stderr)"
    completed = run([sys.executable, "-c", code], 5, output_limit=32, discard_stdout=True)
    assert completed.code == 0
    assert completed.output.strip() == "error details"
    assert not completed.error


def test_process_keyboardinterrupt_cleanup(monkeypatch):
    import pi_filecheck.process as process_module

    real_popen = process_module.subprocess.Popen
    instances = []

    def tracked(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        instances.append(process)
        return process

    monkeypatch.setattr(process_module.subprocess, "Popen", tracked)

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(process_module.selectors.DefaultSelector, "select", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run([sys.executable, "-c", "import time; time.sleep(20)"], 5)
    assert instances[0].poll() is not None


def test_missing_executable():
    completed = run(["/does/not/exist/filecheck-test"], 1)
    assert completed.code is None
    assert completed.error


def test_silent_process_emits_activity_without_filling_diagnostics():
    activity = []
    completed = run(
        [sys.executable, "-c", "import time; time.sleep(0.35)"],
        5,
        output_limit=16,
        progress=activity.append,
        progress_interval=0.05,
    )
    assert completed.code == 0
    assert completed.output == ""
    assert not completed.error
    assert activity
    assert all(event.elapsed > 0 for event in activity)


def test_activity_continues_when_process_closes_output_early():
    events = []
    completed = run(
        [sys.executable, "-c", "import os,time; os.close(1); os.close(2); time.sleep(0.35)"],
        5,
        progress=events.append,
        progress_interval=0.05,
    )
    assert completed.code == 0
    assert len(events) >= 2


def test_incomplete_archive_has_actionable_reason(root, monkeypatch):
    monkeypatch.setattr("pi_filecheck.validators.shutil.which", lambda _: "/trusted/7zz")
    monkeypatch.setattr(
        "pi_filecheck.validators.run", lambda *a, **k: Completed(2, "Unexpected end of archive")
    )
    outcome = validate(root / "broken.7z", "7z", 1, 100)
    assert outcome[0] == "FAIL"
    assert "truncated or incomplete" in outcome[2]


def test_unusual_names_are_literal_arguments(root, monkeypatch):
    path = root / "- @evil; $(touch owned) 日本語.7z"
    calls = []
    monkeypatch.setattr("pi_filecheck.validators.shutil.which", lambda name: "/trusted/7zz")

    def fake_run(argv, timeout):
        calls.append(argv)
        return Completed(0, "Everything is Ok")

    monkeypatch.setattr("pi_filecheck.validators.run", fake_run)
    outcome = validate(path, "7z", 60, 1024)
    assert outcome[0] == "PASS"
    assert calls[0][-2:] == ["--", str(path)]
    assert "-t7z" in calls[0]
    assert not (root / "owned").exists()


@pytest.mark.parametrize(
    "code,text,status",
    [
        (2, "CRC failed", "FAIL"),
        (8, "out of memory", "ERROR"),
        (2, "Wrong password", "UNKNOWN"),
        (7, "bad syntax", "ERROR"),
    ],
)
def test_tool_exit_semantics(root, monkeypatch, code, text, status):
    monkeypatch.setattr("pi_filecheck.validators.shutil.which", lambda name: "/trusted/7zz")
    monkeypatch.setattr("pi_filecheck.validators.run", lambda *a, **k: Completed(code, text))
    assert validate(root / "file.7z", "7z", 1, 100)[0] == status
