import hashlib
import shutil
import subprocess
import sys

import pytest

from pi_filecheck.identify import identify
from pi_filecheck.process import Completed
from pi_filecheck.scanner import test_file as check_file
from pi_filecheck.validators import validate_exfat_image


def test_exfat_signature_does_not_prove_integrity(root, config, monkeypatch):
    path = root / "disk.img"
    payload = b"\xeb\x76\x90EXFAT   " + b"\x00" * 501
    path.write_bytes(payload)

    def must_not_run(*args, **kwargs):
        raise AssertionError("Filesystem tools must never be run automatically")

    monkeypatch.setattr("pi_filecheck.validators.shutil.which", lambda _: None)
    monkeypatch.setattr("pi_filecheck.validators.run", must_not_run)
    assert identify(path).format == "exfat"
    result = check_file(path, config, hash_requested=True)
    assert result.status == "UNKNOWN"
    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    assert path.read_bytes() == payload


def test_exfat_extension_is_only_a_hint(root, config):
    path = root / "not-really.exfat"
    path.write_bytes(b"random bytes")
    result = check_file(path, config)
    assert result.status == "UNKNOWN"
    assert "extension hint" in result.detection


def test_device_rejected(config):
    result = check_file("/dev/null", config)
    assert result.status == "ERROR"
    assert "regular" in result.reason


@pytest.mark.parametrize("version_code", [0, 16])
def test_exfat_uses_only_verified_read_only_mode(root, monkeypatch, version_code):
    path = root / "volume.exfat"
    path.write_bytes(b"\xeb\x76\x90EXFAT   " + b"\x00" * 501)
    monkeypatch.setattr("pi_filecheck.validators.sys.platform", "linux")
    monkeypatch.setattr("pi_filecheck.validators.shutil.which", lambda _: "/trusted/fsck.exfat")
    calls = []

    def fake_run(argv, timeout):
        calls.append(argv)
        return (
            Completed(version_code, "exfatprogs version : 1.2.2")
            if argv[-1] == "-V"
            else Completed(0, "clean")
        )

    monkeypatch.setattr("pi_filecheck.validators.run", fake_run)
    assert validate_exfat_image(path, 60)[0] == "PASS"
    assert calls == [["/trusted/fsck.exfat", "-V"], ["/trusted/fsck.exfat", "-n", "--", str(path)]]


def test_other_fsck_implementation_is_not_invoked(root, monkeypatch):
    path = root / "volume.exfat"
    path.write_bytes(b"\xeb\x76\x90EXFAT   ")
    monkeypatch.setattr("pi_filecheck.validators.sys.platform", "linux")
    monkeypatch.setattr("pi_filecheck.validators.shutil.which", lambda _: "/trusted/fsck.exfat")
    calls = []

    def fake_run(argv, timeout):
        calls.append(argv)
        return Completed(0, "unknown implementation")

    monkeypatch.setattr("pi_filecheck.validators.run", fake_run)
    assert validate_exfat_image(path, 60)[0] == "UNKNOWN"
    assert len(calls) == 1


@pytest.mark.integration
def test_actual_linux_exfat_image_read_only(root, config):
    mkfs = shutil.which("mkfs.exfat")
    fsck = shutil.which("fsck.exfat")
    if sys.platform != "linux" or not mkfs or not fsck:
        pytest.skip("Linux exfatprogs is not installed")
    # Formatting is strictly test-fixture construction on a new disposable regular file.
    path = root / "synthetic.exfat"
    with path.open("wb") as stream:
        stream.truncate(64 * 1024**2)
    subprocess.run([mkfs, str(path)], check=True, capture_output=True)
    before = hashlib.sha256(path.read_bytes()).digest()
    result = check_file(path, config)
    assert result.status == "PASS", result
    assert hashlib.sha256(path.read_bytes()).digest() == before
    # Corrupt metadata in both boot regions, retaining only the signature.
    with path.open("r+b") as stream:
        stream.seek(64)
        stream.write(b"\xff" * 64)
        stream.seek(12 * 512 + 64)
        stream.write(b"\xff" * 64)
    damaged = hashlib.sha256(path.read_bytes()).digest()
    assert check_file(path, config).status in ("FAIL", "ERROR")
    assert hashlib.sha256(path.read_bytes()).digest() == damaged
