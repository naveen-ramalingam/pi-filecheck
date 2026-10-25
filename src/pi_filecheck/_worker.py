"""Isolated stdlib validation worker. No archive content is ever written or executed.

Invoked as a script with Python -I, so input directories/PYTHONPATH cannot supply modules.
Exit codes: 0 pass, 1 corrupt, 2 operation/resource failure, 3 unsupported/encrypted.
"""

import bz2
import contextlib
import gzip
import lzma
import os
import stat
import subprocess
import sys
import tarfile
import zipfile

CHUNK = 1024 * 1024


class LimitError(Exception):
    pass


class Unsupported(Exception):
    pass


class BoundedReader:
    def __init__(self, stream, limit):
        self.stream, self.limit, self.total = stream, limit, 0

    def read(self, size=-1):
        if size < 0:
            size = CHUNK
        data = self.stream.read(min(size, CHUNK))
        self.total += len(data)
        if self.total > self.limit:
            raise LimitError("Expanded data exceeds configured byte limit")
        return data


def drain(stream):
    while stream.read(CHUNK):
        pass


@contextlib.contextmanager
def decoded(path, compression, zstd):
    if compression == "zst":
        process = subprocess.Popen(
            [zstd, "-d", "-q", "-c", "--", path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            yield process.stdout
            if process.wait() != 0:
                raise ValueError("Zstandard stream integrity check failed")
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()
    else:
        opener = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open, "": open}[compression]
        with opener(path, "rb") as stream:
            yield stream


def validate(fmt, path, limit, zstd=""):
    # Source checks are repeated in this process. No block devices, FIFOs or symlinks.
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise OSError("Worker input is not a regular file")
    if fmt in ("zip", "zip.quick"):
        total = 0
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 100000:
                raise LimitError("ZIP has more than 100000 members")
            if fmt == "zip.quick":
                return
            if any(m.flag_bits & 1 for m in members):
                raise Unsupported("Encrypted ZIP requires a password; not verified")
            for member in members:
                with archive.open(member) as stream:
                    while data := stream.read(CHUNK):
                        total += len(data)
                        if total > limit:
                            raise LimitError("Expanded data exceeds configured byte limit")
        return
    is_tar = fmt == "tar" or fmt.startswith("tar.")
    compression = fmt.split(".", 1)[1] if fmt.startswith("tar.") else ("" if is_tar else fmt)
    with decoded(path, compression, zstd) as stream:
        bounded = BoundedReader(stream, limit)
        if is_tar:
            with tarfile.open(fileobj=bounded, mode="r|") as archive:
                for number, member in enumerate(archive, start=1):
                    if number > 100000:
                        raise LimitError("TAR has more than 100000 members")
                    if member.isfile():
                        # Reading each entry detects truncated payloads. Never extract paths/links.
                        with archive.extractfile(member) as entry:
                            drain(entry)
            # TAR end markers precede the compressor footer; consume it to verify its checksum.
        drain(bounded)


def main():
    try:
        if sys.platform == "linux":
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        validate(
            sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else ""
        )
        print(
            "ZIP directory metadata readable; contents not checked"
            if sys.argv[1] == "zip.quick"
            else "Integrity check completed"
        )
        return 0
    except (Unsupported, NotImplementedError) as exc:
        print(str(exc)[:16000])
        return 3
    except (MemoryError, LimitError, PermissionError) as exc:
        print(f"Resource or permission limit: {exc}"[:16000])
        return 2
    except OSError as exc:
        print(f"{type(exc).__name__}: {exc}"[:16000])
        # Decoder failures usually have no errno; real read errors have an errno.
        return 2 if exc.errno is not None else 1
    except (
        ValueError,
        EOFError,
        tarfile.TarError,
        zipfile.BadZipFile,
        lzma.LZMAError,
        RuntimeError,
    ) as exc:
        print(f"{type(exc).__name__}: {exc}"[:16000])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
