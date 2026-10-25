import hashlib

import pytest

from pi_filecheck.checksums import CHUNK_SIZE, compare, sha256_file, trusted_digest
from pi_filecheck.scanner import test_file as check_file


@pytest.mark.parametrize("payload", [b"", b"abc", b"x" * (CHUNK_SIZE * 3 + 1)])
def test_streamed_sha256(root, payload):
    path = root / "file.pkg"
    path.write_bytes(payload)
    assert sha256_file(path) == hashlib.sha256(payload).hexdigest()


def test_trusted_comparison():
    assert compare("a" * 64, "A" * 64)
    assert not compare("a" * 64, "b" * 64)
    with pytest.raises(ValueError):
        trusted_digest("sha256:no")


def test_hash_match_does_not_upgrade_unsupported_container(root, config):
    path = root / "unsupported.pkg"
    path.write_bytes(b"abc")
    result = check_file(path, config, expected=hashlib.sha256(b"abc").hexdigest())
    assert result.status == "UNKNOWN"
    assert result.checksum_status == "MATCH"
    result = check_file(path, config, expected="0" * 64)
    assert result.status == "FAIL"
    assert result.checksum_status == "MISMATCH"
