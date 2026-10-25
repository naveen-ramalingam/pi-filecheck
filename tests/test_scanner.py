import os
from pathlib import Path

import pytest

from pi_filecheck.identify import identify
from pi_filecheck.models import Result
from pi_filecheck.scanner import discover, scan_entries
from pi_filecheck.scanner import test_file as check_file


def test_spaces_unicode_and_unknown(root, config):
    path = root / "日本語 ; $() space.pkg"
    path.write_bytes(b"plain text")
    result = check_file(path, config, hash_requested=True)
    assert result.status == "UNKNOWN"
    assert result.format == "pkg"
    assert result.sha256
    assert result.checksum_status == "CALCULATED"


@pytest.mark.parametrize(
    "name",
    [
        "a.pup",
        "a.ffpkg",
        "a.ffpfs",
        "a.ffpfsc",
        "a.zar",
        "a.self",
        "a.sprx",
        "a.bin",
        "a.iso",
        "a.img",
        "a.elf",
        "a.what",
    ],
)
def test_proprietary_and_unsupported_never_pass(root, config, name):
    path = root / name
    path.write_bytes(b"data")
    assert check_file(path, config).status == "UNKNOWN"


def test_empty_file(root, config):
    path = root / "empty.zip"
    path.touch()
    assert check_file(path, config).status == "FAIL"
    unknown = root / "empty.bin"
    unknown.touch()
    assert check_file(unknown, config).status == "UNKNOWN"


def test_large_sparse_file_identified_without_reading_all(root, config):
    path = root / "huge.img"
    with path.open("wb") as stream:
        stream.truncate(8 * 1024**3)
    result = check_file(path, config)
    assert result.size == 8 * 1024**3
    assert result.status == "UNKNOWN"
    assert not result.sha256


def test_symlinks_and_recursion(root, config):
    path = root / "real.bin"
    path.write_bytes(b"x")
    (root / "link.bin").symlink_to(path)
    folder = root / "nested"
    folder.mkdir()
    (folder / "inside.bin").write_bytes(b"x")
    (root / "loop").symlink_to(root, target_is_directory=True)
    entries = list(discover(root, recursive=True))
    assert sum(isinstance(e, Result) and e.status == "SKIP" for e in entries) == 2
    assert sum(isinstance(e, Path) for e in entries) == 2
    assert check_file(root / "link.bin", config).status == "ERROR"


def test_symlink_ancestor_rejected(root, config):
    (root / "child").mkdir()
    (root / "alias").symlink_to(root / "child", target_is_directory=True)
    (root / "child/file.bin").touch()
    assert check_file(root / "alias/file.bin", config).status == "ERROR"


def test_fifo_is_not_read(root, config):
    path = root / "pipe.pkg"
    os.mkfifo(path)
    assert check_file(path, config).status == "ERROR"
    records = list(discover(root))
    assert records[0].status == "SKIP"


def test_unreadable_file(root, config, monkeypatch):
    path = root / "blocked.zip"
    path.write_bytes(b"x")

    def denied(_):
        raise PermissionError("denied by ACL")

    monkeypatch.setattr("pi_filecheck.scanner.identify", denied)
    assert check_file(path, config).status == "ERROR"


def test_real_file_permission_failure(root, config):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("Root bypasses chmod permissions")
    path = root / "unreadable.zip"
    path.write_bytes(b"x")
    path.chmod(0)
    try:
        assert check_file(path, config).status == "ERROR"
    finally:
        path.chmod(0o600)


def test_source_mutation_changes_result_to_error(root, config, monkeypatch):
    path = root / "game.7z"
    path.write_bytes(b"x")

    def changing(*args, **kwargs):
        path.write_bytes(b"changed")
        return "PASS", "mock", "passed", "", 0

    monkeypatch.setattr("pi_filecheck.scanner.validate", changing)
    assert check_file(path, config).status == "ERROR"


def test_magic_over_extension(root):
    path = root / "wrong.pkg"
    path.write_bytes(b"\x1f\x8b" + b"x" * 20)
    found = identify(path)
    assert found.format == "gz"
    assert "extension suggests pkg" in found.evidence


def test_scan_retains_completed_records_on_interrupt(root, config, monkeypatch):
    one, two = root / "a.bin", root / "b.bin"
    one.touch()
    two.touch()
    output = []

    def progress(index, count, entry):
        if index == 2:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        scan_entries([one, two], config, progress=progress, results=output)
    assert len(output) == 1
