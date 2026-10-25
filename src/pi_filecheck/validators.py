"""Explicit validator registry. No signature or hash is itself a container PASS."""

import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .paths import open_regular, snapshot
from .process import run


@dataclass(frozen=True)
class Validator:
    name: str
    formats: tuple[str, ...]
    tools: tuple[str, ...] = ()
    success: str = ""


REGISTRY = (
    Validator("stdlib ZIP", ("zip",), success="ZIP member CRC/decompression checks succeeded"),
    Validator(
        "stdlib TAR",
        ("tar", "tar.gz", "tar.bz2", "tar.xz", "tar.zst"),
        success="TAR header/readability checks succeeded; raw TAR has no payload checksum",
    ),
    Validator(
        "stdlib compression",
        ("gz", "bz2", "xz"),
        success="Full compressed stream test succeeded (checksums where present)",
    ),
    Validator(
        "7-Zip",
        ("7z", "rar", "multipart"),
        ("7zz", "7z"),
        "7-Zip full archive integrity test succeeded",
    ),
    Validator("Zstandard", ("zst",), ("zstd",), "Zstandard full stream test succeeded"),
    Validator(
        "LZ4", ("lz4",), ("lz4",), "LZ4 full stream test succeeded (checksums where present)"
    ),
    Validator("exfatprogs (read-only image)", ("exfat",), ("fsck.exfat",)),
)

OPTIONAL_TOOLS = {
    "7-Zip": (("7zz", "7z"), "7zip (older Debian: p7zip-full; RAR support varies)"),
    "RAR alternative": (("unrar",), "unrar (Debian non-free, optional)"),
    "Zstandard": (("zstd",), "zstd"),
    "LZ4": (("lz4",), "lz4"),
    "exFAT image checks (Linux, read-only)": (("fsck.exfat",), "exfatprogs"),
    "SMART diagnostics (manual only)": (("smartctl",), "smartmontools"),
}


def available_tools():
    return [
        {
            "name": name,
            "path": next((shutil.which(t) for t in tools if shutil.which(t)), None),
            "install": f"sudo apt install {package}",
        }
        for name, (tools, package) in OPTIONAL_TOOLS.items()
    ]


def validate(path, fmt, timeout, max_expanded_bytes, multipart=False, progress=None):
    if fmt == "exfat" and not multipart:
        return validate_exfat_image(path, timeout, progress)
    key = "multipart" if multipart else fmt
    spec = next((s for s in REGISTRY if key in s.formats), None)
    if spec is None:
        reasons = {
            "pkg": "No verified PS5/PS4 package validator integrated; a PKG is not assumed to be ZIP",
            "pup": "No verified firmware-specific validator integrated; identification cannot validate a PUP",
        }
        return (
            "UNKNOWN",
            "none",
            reasons.get(
                fmt,
                f"No compatible integrity validator integrated for {fmt}; see docs/validators.md",
            ),
            "",
            None,
        )
    tools = spec.tools
    tool = next((shutil.which(t) for t in tools if shutil.which(t)), None)
    # UnRAR is a read-only alternative for RAR when 7-Zip is absent.
    is_split = multipart and bool(re.search(r"\.(?:7z|zip)\.\d{3}$", path.name, re.I))
    if multipart and ((is_split and fmt not in ("7z", "zip")) or (not is_split and fmt != "rar")):
        return (
            "UNKNOWN",
            spec.name,
            "Multipart naming and detected content have no compatible full-set validator",
            "",
            None,
        )
    is_rar = fmt == "rar" and not is_split
    unrar = shutil.which("unrar") if key in ("rar", "multipart") and is_rar and not tool else None
    if tools and not tool and not unrar:
        return (
            "UNKNOWN",
            spec.name,
            f"Missing compatible tool: {' or '.join(tools)}; run filecheck doctor",
            "",
            None,
        )
    zstd = shutil.which("zstd") if fmt == "tar.zst" else None
    if fmt == "tar.zst" and not zstd:
        return (
            "UNKNOWN",
            spec.name,
            "Missing zstd for compressed TAR verification; run filecheck doctor",
            "",
            None,
        )
    if unrar:
        args, name = [unrar, "t", "-idq", "-p-", "--", str(path)], "unrar"
    elif key in ("7z", "rar", "multipart"):
        # A nonempty dummy password prevents prompts; encrypted failures stay UNKNOWN.
        if is_split:
            archive_type = f"{fmt}.split"
        elif is_rar:
            with open_regular(path) as stream:
                archive_type = "rar5" if stream.read(8) == b"Rar!\x1a\x07\x01\x00" else "rar"
        else:
            archive_type = "7z"
        args, name = (
            [
                tool,
                "t",
                f"-t{archive_type}",
                "-bd",
                "-bb0",
                "-spd",
                "-y",
                "-pPI_FILECHECK_NO_PASSWORD",
                "--",
                str(path),
            ],
            spec.name,
        )
    elif key in ("zst", "lz4"):
        args, name = [tool, "-t", "--", str(path)], spec.name
    else:
        args, name = (
            [
                sys.executable,
                "-I",
                str(Path(__file__).with_name("_worker.py")),
                fmt,
                str(path),
                str(max_expanded_bytes),
            ],
            spec.name,
        )
        if zstd:
            args.append(zstd)
    completed = run(args, timeout, progress=progress) if progress else run(args, timeout)
    diagnostics = completed.output.strip()
    if completed.error or completed.code is None or completed.code < 0:
        return (
            "ERROR",
            name,
            completed.error or "Validator terminated unexpectedly",
            diagnostics,
            completed.code,
        )
    if completed.code == 0:
        reason = spec.success
        if name == "unrar":
            reason = "UnRAR full archive integrity test succeeded"
        if fmt.startswith("tar."):
            reason += "; enclosing compression stream also checked"
        return "PASS", name, reason, diagnostics, 0
    if any(
        word in diagnostics.lower()
        for word in ("password", "encrypted", "unsupported", "not supported")
    ):
        return (
            "UNKNOWN",
            name,
            "Encrypted archive or unsupported method; full integrity not verified",
            diagnostics,
            completed.code,
        )
    if key in ("7z", "rar", "multipart"):
        # 7-Zip: 1 warning, 2 fatal, 7 syntax, 8 memory, 255 cancelled.
        if name != "unrar" and completed.code not in (1, 2):
            state = "ERROR"
        elif name == "unrar" and completed.code not in (1, 2, 3):
            state = "ERROR"
        else:
            state = "FAIL"
    elif key in ("zst", "lz4"):
        state = "FAIL"
    else:
        state = {1: "FAIL", 2: "ERROR", 3: "UNKNOWN"}.get(completed.code, "ERROR")
    if multipart and any(
        w in diagnostics.lower()
        for w in ("missing volume", "cannot find volume", "unexpected end", "missing volume :")
    ):
        state = "SKIP"
    reason = "Integrity check did not succeed; see diagnostics"
    if "unexpected end" in diagnostics.lower():
        reason = "Archive is truncated or incomplete (unexpected end of archive)"
    elif any(w in diagnostics.lower() for w in ("crc failed", "crc error", "data error")):
        reason = "Archive CRC/data integrity check failed; see diagnostics"
    return (
        state,
        name,
        reason,
        diagnostics,
        completed.code,
    )


def validate_exfat_image(path, timeout, progress=None):
    """Only raw-volume regular files, verified exfatprogs, and the upstream -n mode.

    Physical devices are never accepted, mounted or unmounted by this adapter.
    exfatprogs opens the source O_RDONLY with -n (see upstream lib/libexfat.c).
    """
    name = "exfatprogs fsck.exfat -n (image)"
    snapshot(path)
    with open_regular(path) as stream:
        if stream.read(11)[3:11] != b"EXFAT   ":
            return (
                "UNKNOWN",
                name,
                "No exFAT raw-volume signature; partitioned/unsupported images require manual identification",
                "",
                None,
            )
    if sys.platform != "linux":
        return (
            "UNKNOWN",
            name,
            "Read-only exfatprogs image adapter is supported on Linux only",
            "",
            None,
        )
    tool = shutil.which("fsck.exfat")
    if not tool:
        return "UNKNOWN", name, "Missing fsck.exfat from exfatprogs; run filecheck doctor", "", None
    version = run([tool, "-V"], min(timeout, 5))
    # Upstream fsck prints the version, then returns its usage/syntax code (16)
    # when -V has no device. This is an identity query, not the integrity result.
    if version.error or version.code not in (0, 16) or "exfatprogs" not in version.output.lower():
        return (
            "UNKNOWN",
            name,
            "Could not confirm exfatprogs implementation; no filesystem check was attempted",
            version.output.strip(),
            version.code,
        )
    argv = [tool, "-n", "--", str(path)]
    completed = run(argv, timeout, progress=progress) if progress else run(argv, timeout)
    if completed.error or completed.code is None or completed.code < 0:
        return (
            "ERROR",
            name,
            completed.error or "Filesystem checker terminated unexpectedly",
            completed.output.strip(),
            completed.code,
        )
    if completed.code == 0:
        return (
            "PASS",
            name,
            "Read-only exFAT filesystem consistency check succeeded; no archive payload or physical-health guarantee",
            completed.output.strip(),
            0,
        )
    # fsck bitmask: 4=errors remain; 8/16/32/128=operational/syntax/cancel/library.
    # Repair/reboot codes 1/2 are impossible in the intended -n workflow: fail closed.
    state = "FAIL" if completed.code == 4 else "ERROR"
    return (
        state,
        name,
        "Read-only exFAT consistency check did not succeed; see diagnostics",
        completed.output.strip(),
        completed.code,
    )
