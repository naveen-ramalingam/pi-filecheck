"""Path checks shared by CLI, scanner and hash workers. Devices are never inputs."""

import os
import stat
from contextlib import contextmanager
from pathlib import Path


def absolute(value):
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def reject_symlinks(path):
    path = absolute(path)
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Symbolic links are not followed: {part}")
    return path


def directory(value, required_mount=""):
    path = reject_symlinks(value)
    if required_mount and not os.path.ismount(required_mount):
        raise ValueError(f"Required drive is not mounted: {required_mount}")
    if not path.is_dir():
        raise ValueError(f"Directory is missing or is not a directory: {path}")
    if not os.access(path, os.R_OK | os.X_OK):
        raise PermissionError(f"Directory is not readable/searchable: {path}")
    # Actually open it; os.access alone is insufficient for ACLs and races.
    with os.scandir(path):
        pass
    if required_mount and not path.is_relative_to(absolute(required_mount)):
        raise ValueError("Scan path is outside the required mount")
    return path


def mountpoint(path):
    current = absolute(path)
    while not os.path.ismount(current) and current != current.parent:
        current = current.parent
    return current


def snapshot(path):
    p = reject_symlinks(path)
    s = p.stat()
    if not stat.S_ISREG(s.st_mode):
        raise ValueError(f"Only regular files are supported (no devices/FIFOs): {p}")
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


@contextmanager
def open_regular(path):
    path = reject_symlinks(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("Only regular files are supported; no devices or pipes")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            yield stream
    finally:
        os.close(fd)
