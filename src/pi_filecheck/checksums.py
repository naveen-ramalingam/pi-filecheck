"""Streaming SHA-256; a hash alone is not an integrity verdict."""

import hashlib
import hmac
import re
import time

from .paths import open_regular, snapshot

CHUNK_SIZE = 1024 * 1024


def trusted_digest(value):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ValueError("Expected SHA-256 must contain exactly 64 hexadecimal characters")
    return value.lower()


def sha256_file(path, timeout=3600):
    before = snapshot(path)
    deadline = time.monotonic() + timeout
    digest = hashlib.sha256()
    with open_regular(path) as stream:
        while chunk := stream.read(CHUNK_SIZE):
            if time.monotonic() > deadline:
                raise TimeoutError("SHA-256 time limit exceeded")
            digest.update(chunk)
    if snapshot(path) != before:
        raise OSError("File changed while calculating SHA-256")
    return digest.hexdigest()


def compare(actual, expected):
    return hmac.compare_digest(actual, trusted_digest(expected))
