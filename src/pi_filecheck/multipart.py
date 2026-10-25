"""Name-based grouping detects gaps; the archive tool must establish the final volume."""

import re
from dataclasses import dataclass
from pathlib import Path

from .paths import snapshot


@dataclass
class Volumes:
    first: Path
    paths: list[Path]
    reason: str = ""


def group(path, siblings=None):
    name = path.name
    part = re.fullmatch(r"(.+)\.part(\d+)\.rar", name, re.I)
    split = re.fullmatch(r"(.+\.(?:7z|zip))\.(\d{3})", name, re.I)
    legacy = re.fullmatch(r"(.+)\.(rar|r\d{2,3})", name, re.I)
    if not (part or split or legacy):
        return None
    siblings = list(path.parent.iterdir()) if siblings is None else siblings
    if part:
        regex = re.compile(re.escape(part[1]) + r"\.part(\d+)\.rar", re.I)
        start = 1
        pairs = [(int(m[1]), p) for p in siblings if (m := regex.fullmatch(p.name))]
    elif split:
        regex = re.compile(re.escape(split[1]) + r"\.(\d{3})", re.I)
        start = 1
        pairs = [(int(m[1]), p) for p in siblings if (m := regex.fullmatch(p.name))]
    else:
        regex = re.compile(re.escape(legacy[1]) + r"\.(rar|r\d{2,3})", re.I)
        pairs = [
            (0 if m[1].lower() == "rar" else int(m[1][1:]) + 1, p)
            for p in siblings
            if (m := regex.fullmatch(p.name))
        ]
        if len(pairs) <= 1 and legacy[2].lower() == "rar":
            return None
        start = 0
    pairs.sort(key=lambda x: (x[0], x[1].name))
    paths = [p for _, p in pairs]
    numbers = [n for n, _ in pairs]
    first = paths[0] if paths else path
    if len(numbers) != len(set(numbers)):
        return Volumes(first, paths, "Ambiguous duplicate volume numbers")
    # Do not allocate a range controlled by an arbitrarily long part number.
    if (
        not numbers
        or numbers[0] != start
        or any(b != a + 1 for a, b in zip(numbers, numbers[1:], strict=False))
    ):
        return Volumes(
            first,
            paths,
            "Incomplete multipart collection: first volume or an intermediate volume is missing",
        )
    for volume in paths:
        try:
            snapshot(volume)
        except (OSError, ValueError) as exc:
            return Volumes(first, paths, f"Unsafe or unreadable multipart volume: {exc}")
    return Volumes(first, paths)
