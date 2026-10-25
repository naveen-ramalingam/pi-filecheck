import io
import json
import shutil
import subprocess
import tarfile
import zipfile

import pytest

from pi_filecheck.cli import main
from pi_filecheck.scanner import test_file as check_file


def test_quick_zip_does_not_read_payload_or_claim_pass(root, config):
    path = root / "file.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("hello.txt", b"synthetic content", compress_type=zipfile.ZIP_STORED)
    data = bytearray(path.read_bytes())
    data[30 + len("hello.txt")] ^= 1
    path.write_bytes(data)
    assert check_file(path, config, quick=True).status == "UNKNOWN"
    assert check_file(path, config).status == "FAIL"


def test_quick_zip_detects_missing_end_metadata(root, config):
    path = root / "truncated.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("hello", b"content")
    path.write_bytes(path.read_bytes()[:-20])
    assert check_file(path, config, quick=True).status == "FAIL"


def test_quick_does_not_use_saved_hash_setting(root, config, monkeypatch):
    path = root / "example.pkg"
    path.write_bytes(b"synthetic")
    config.sha256 = True

    def must_not_hash(*args, **kwargs):
        pytest.fail("Quick mode must not hash payloads")

    monkeypatch.setattr("pi_filecheck.scanner.sha256_file", must_not_hash)
    result = check_file(path, config, quick=True)
    assert result.status == "UNKNOWN"
    assert not result.sha256
    assert result.check_mode == "quick"


def test_cli_defaults_to_quick(root, capsys):
    path = root / "valid.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("hello", b"content")
    assert main(["test", str(path), "--no-report", "--format", "json"]) == 1
    result = json.loads(capsys.readouterr().out)["results"][0]
    assert result["status"] == "UNKNOWN" and result["check_mode"] == "quick"
    assert main(["test", str(path), "--full", "--no-report"]) == 0


def test_quick_rejects_full_hash_flags(root):
    path = root / "data.pkg"
    path.write_bytes(b"data")
    assert main(["test", str(path), "--sha256", "--no-report"]) == 2
    assert main(["test", str(path), "--expected-sha256", "0" * 64, "--no-report"]) == 2


def test_compressed_tar_quick_check_does_not_decompress(root, config):
    path = root / "archive.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        entry = tarfile.TarInfo("content")
        entry.size = 4
        archive.addfile(entry, io.BytesIO(b"data"))
    result = check_file(path, config, quick=True)
    assert result.status == "UNKNOWN"
    assert "No quick structural check" in result.reason


@pytest.mark.integration
def test_native_quick_precheck_never_decompresses_archive_contents(root, config):
    tool = shutil.which("7zz") or shutil.which("7z")
    if not tool:
        pytest.skip("7-Zip is not installed")
    source = root / "source.txt"
    source.write_bytes(b"synthetic content" * 100)
    path = root / "archive.7z"
    subprocess.run([tool, "a", str(path), str(source)], check=True, capture_output=True)
    result = check_file(path, config, quick=True)
    assert result.status == "UNKNOWN"
    assert result.tool_exit_code == 0
    assert "not tested" in result.reason
    path.write_bytes(path.read_bytes()[:-20])
    assert check_file(path, config, quick=True).status == "FAIL"
