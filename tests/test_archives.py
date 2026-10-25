import bz2
import gzip
import io
import lzma
import shutil
import subprocess
import tarfile
import zipfile

import pytest

from pi_filecheck.scanner import test_file as check_file


def tar_bytes(name="safe.txt"):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        entry = tarfile.TarInfo(name)
        payload = b"synthetic archive content" * 5
        entry.size = len(payload)
        archive.addfile(entry, io.BytesIO(payload))
    return stream.getvalue()


@pytest.mark.parametrize(
    "suffix,encode,payload",
    [
        (".gz", gzip.compress, b"data"),
        (".bz2", bz2.compress, b"data"),
        (".xz", lzma.compress, b"data"),
        (".tar", bytes, tar_bytes()),
        (".tar.gz", gzip.compress, tar_bytes()),
        (".tgz", gzip.compress, tar_bytes()),
        (".tar.bz2", bz2.compress, tar_bytes()),
        (".tbz2", bz2.compress, tar_bytes()),
        (".tar.xz", lzma.compress, tar_bytes()),
        (".txz", lzma.compress, tar_bytes()),
    ],
)
def test_real_builtin_archives(root, config, suffix, encode, payload):
    path = root / ("synthetic 日本語" + suffix)
    original = encode(payload)
    path.write_bytes(original)
    result = check_file(path, config)
    assert result.status == "PASS", result
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "suffix,encode",
    [
        (".gz", gzip.compress),
        (".bz2", bz2.compress),
        (".xz", lzma.compress),
        (".tar.gz", gzip.compress),
    ],
)
def test_corrupt_compressed_archive(root, config, suffix, encode):
    path = root / ("bad" + suffix)
    data = bytearray(encode(tar_bytes() if suffix.startswith(".tar") else b"data" * 100))
    data[-5] ^= 0xFF
    path.write_bytes(data)
    assert check_file(path, config).status == "FAIL"


def test_zip_valid_and_corrupt_crc(root, config):
    path = root / "archive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("content.txt", b"synthetic payload", compress_type=zipfile.ZIP_STORED)
    assert check_file(path, config).status == "PASS"
    damaged = bytearray(path.read_bytes())
    damaged[30 + len("content.txt")] ^= 1
    path.write_bytes(damaged)
    assert check_file(path, config).status == "FAIL"


def test_no_extraction_of_traversal_paths(root, config):
    path = root / "unsafe.tar"
    path.write_bytes(tar_bytes("../must-not-exist.txt"))
    assert check_file(path, config).status == "PASS"
    assert not (root.parent / "must-not-exist.txt").exists()


def test_truncated_tar(root, config):
    path = root / "short.tar"
    path.write_bytes(tar_bytes()[:530])
    assert check_file(path, config).status == "FAIL"


def test_expansion_limit(root, config):
    path = root / "large.gz"
    path.write_bytes(gzip.compress(b"x" * 10000))
    config.max_expanded_bytes = 100
    assert check_file(path, config).status == "ERROR"


def test_missing_optional_tools(root, config, monkeypatch):
    monkeypatch.setattr("pi_filecheck.validators.shutil.which", lambda name: None)
    path = root / "archive.7z"
    path.write_bytes(b"7z\xbc\xaf\x27\x1c")
    result = check_file(path, config)
    assert result.status == "UNKNOWN"
    assert "Missing" in result.reason


@pytest.mark.integration
@pytest.mark.parametrize(
    "tool,suffix", [("zstd", ".zst"), ("lz4", ".lz4"), ("zstd", ".tar.zst"), ("zstd", ".tar.zstd")]
)
def test_actual_external_compressors(root, config, tool, suffix):
    executable = shutil.which(tool)
    if not executable:
        pytest.skip(f"{tool} is not installed")
    payload = tar_bytes() if ".tar." in suffix else b"safe synthetic data"
    path = root / ("compressed" + suffix)
    encoded = subprocess.run(
        [executable, "-c"], input=payload, capture_output=True, check=True
    ).stdout
    path.write_bytes(encoded)
    assert check_file(path, config).status == "PASS"
    path.write_bytes(encoded[:-4])
    assert check_file(path, config).status == "FAIL"


@pytest.mark.integration
def test_actual_sevenzip_and_split(root, config):
    executable = shutil.which("7zz") or shutil.which("7z")
    if not executable:
        pytest.skip("7-Zip is not installed")
    source = root / "payload.txt"
    source.write_text("synthetic content " * 200, encoding="utf-8")
    archive = root / "archive.7z"
    subprocess.run([executable, "a", str(archive), str(source)], check=True, capture_output=True)
    assert check_file(archive, config).status == "PASS"
    data = archive.read_bytes()
    midpoint = len(data) // 2
    first, second = root / "split.7z.001", root / "split.7z.002"
    first.write_bytes(data[:midpoint])
    second.write_bytes(data[midpoint:])
    assert check_file(first, config).status == "PASS"
    assert check_file(second, config).status == "PASS"
    second.unlink()
    assert check_file(first, config).status != "PASS"
    archive.write_bytes(data[:-16])
    assert check_file(archive, config).status == "FAIL"


@pytest.mark.integration
def test_native_sevenzip_literal_wildcards_and_encryption(root, config):
    executable = shutil.which("7zz") or shutil.which("7z")
    if not executable:
        pytest.skip("7-Zip is not installed")
    source = root / "content.txt"
    source.write_text("synthetic content", encoding="utf-8")
    archive = root / "literal*[name].7z"
    subprocess.run(
        [executable, "a", "-spd", "--", str(archive), str(source)], check=True, capture_output=True
    )
    assert check_file(archive, config).status == "PASS"
    protected = root / "password.7z"
    subprocess.run(
        [executable, "a", "-pSYNTHETIC_TEST_PASSWORD", "--", str(protected), str(source)],
        check=True,
        capture_output=True,
    )
    assert check_file(protected, config).status == "UNKNOWN"
    protected_zip = root / "password.zip"
    subprocess.run(
        [
            executable,
            "a",
            "-tzip",
            "-pSYNTHETIC_TEST_PASSWORD",
            "--",
            str(protected_zip),
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    assert check_file(protected_zip, config).status == "UNKNOWN"
