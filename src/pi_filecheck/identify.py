"""Conservative signatures; proprietary formats remain extension hints."""

import re
from dataclasses import dataclass

from .paths import open_regular

EXTENSIONS = {
    ".tar.zstd": "tar.zst",
    ".tar.zst": "tar.zst",
    ".tar.gz": "tar.gz",
    ".tar.bz2": "tar.bz2",
    ".tar.xz": "tar.xz",
    ".tgz": "tar.gz",
    ".tbz2": "tar.bz2",
    ".txz": "tar.xz",
    ".7z": "7z",
    ".zip": "zip",
    ".rar": "rar",
    ".tar": "tar",
    ".gz": "gz",
    ".bz2": "bz2",
    ".xz": "xz",
    ".zstd": "zst",
    ".zst": "zst",
    ".lz4": "lz4",
    **{
        f".{name}": name
        for name in (
            "pkg",
            "pup",
            "ffpfsc",
            "ffpkg",
            "ffpfs",
            "zar",
            "elf",
            "self",
            "sprx",
            "bin",
            "iso",
            "img",
            "exfat",
        )
    },
}
SIGNATURES = (
    (b"7z\xbc\xaf\x27\x1c", "7z"),
    (b"PK\x03\x04", "zip"),
    (b"PK\x05\x06", "zip"),
    (b"PK\x07\x08", "zip"),
    (b"Rar!\x1a\x07", "rar"),
    (b"\x1f\x8b", "gz"),
    (b"BZh", "bz2"),
    (b"\xfd7zXZ\x00", "xz"),
    (b"\x28\xb5\x2f\xfd", "zst"),
    (b"\x04\x22\x4d\x18", "lz4"),
    (b"\x7fELF", "elf"),
)


@dataclass(frozen=True)
class Identification:
    format: str
    evidence: str
    extension_format: str


def identify(path):
    name = path.name.lower()
    name = re.sub(r"\.(7z|zip)\.\d{3}$", r".\1", name)
    hint = next((fmt for ext, fmt in EXTENSIONS.items() if name.endswith(ext)), "unknown")
    with open_regular(path) as stream:
        head = stream.read(512)
    detected = next((fmt for sig, fmt in SIGNATURES if head.startswith(sig)), "")
    if head[3:11] == b"EXFAT   ":
        detected = "exfat"
    elif head[257:262] == b"ustar":
        detected = "tar"
    if detected and hint == f"tar.{detected}":
        detected = hint
    if detected:
        evidence = "magic signature (identification only)"
        if hint != "unknown" and hint != detected:
            evidence += f"; extension suggests {hint}, content suggests {detected}"
        return Identification(detected, evidence, hint)
    return Identification(hint, "extension hint only; content unconfirmed", hint)
