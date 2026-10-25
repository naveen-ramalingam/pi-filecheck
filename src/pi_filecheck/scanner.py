"""Discovery, multipart decisions, file-change detection and progress."""

import os
import time
from pathlib import Path

from .checksums import compare, sha256_file, trusted_digest
from .identify import identify
from .models import Result
from .multipart import group
from .paths import absolute, directory, reject_symlinks, snapshot
from .validators import validate


def discover(root, recursive=False, exclude=()):
    """Yield paths or explicit error/skip records. Never descend through symlinks."""
    root = directory(root)
    excluded = [absolute(p) for p in exclude]
    pending = [root]
    while pending:
        folder = pending.pop()
        try:
            reject_symlinks(folder)
            with os.scandir(folder) as entries:
                children = sorted(entries, key=lambda e: e.name)
            for child in children:
                path = Path(child.path)
                if any(path == p or path.is_relative_to(p) for p in excluded):
                    continue
                if child.is_symlink():
                    yield Result(str(path), status="SKIP", reason="Symbolic link not followed")
                elif child.is_dir(follow_symlinks=False):
                    if recursive:
                        pending.append(path)
                elif child.is_file(follow_symlinks=False):
                    yield path
                else:
                    yield Result(
                        str(path),
                        status="SKIP",
                        reason="Not a regular file (device, socket or pipe)",
                    )
        except OSError as exc:
            yield Result(str(folder), status="ERROR", reason=f"Directory could not be read: {exc}")


def test_file(
    path,
    config,
    hash_requested=False,
    expected=None,
    siblings=None,
    single=True,
    heartbeat=None,
    quick=False,
):
    path = absolute(path)
    result = Result(str(path), check_mode="quick" if quick else "full")
    start = time.monotonic()
    try:
        if quick and (hash_requested or expected):
            raise ValueError("Quick checks do not hash contents; use the hash command explicitly")
        if expected:
            trusted_digest(expected)
        before = snapshot(path)
        result.size = before[2]
        identified = identify(path)
        result.format, result.detection = identified.format, identified.evidence
        volumes = group(path, siblings)
        if volumes:
            result.volumes = [str(p) for p in volumes.paths]
            if volumes.reason:
                result.status, result.reason = "SKIP", volumes.reason
                return result
            if path != volumes.first:
                if single:
                    return test_file(
                        volumes.first,
                        config,
                        hash_requested,
                        expected,
                        siblings,
                        single,
                        heartbeat,
                        quick,
                    )
                result.status, result.reason = (
                    "SKIP",
                    f"Continuation volume; full set tested through {volumes.first.name}",
                )
                return result
        tracked = {p: snapshot(p) for p in (volumes.paths if volumes else [path])}
        outcome = validate(
            path,
            identified.format,
            config.timeout_seconds,
            config.max_expanded_bytes,
            multipart=volumes is not None,
            progress=heartbeat,
            quick=quick,
        )
        (
            result.status,
            result.validator,
            result.reason,
            result.diagnostics,
            result.tool_exit_code,
        ) = outcome
        if quick and result.status == "PASS":
            result.status = "UNKNOWN"
            result.reason = "Quick precheck completed; file contents were not verified"
        if not quick and (hash_requested or config.sha256 or expected):
            result.sha256 = sha256_file(path, config.timeout_seconds, progress=heartbeat)
            result.checksum_status = "CALCULATED"
            if expected:
                matched = compare(result.sha256, expected)
                result.checksum_status = "MATCH" if matched else "MISMATCH"
                if not matched:
                    result.status, result.reason = (
                        "FAIL",
                        "SHA-256 does not match the supplied trusted reference",
                    )
                else:
                    result.reason += (
                        "; SHA-256 matches supplied reference (no additional format guarantee)"
                    )
        if any(snapshot(p) != state for p, state in tracked.items()):
            result.status, result.reason = (
                "ERROR",
                "Source file or multipart volume changed during validation",
            )
    except (OSError, ValueError, TimeoutError) as exc:
        result.status, result.reason = "ERROR", str(exc)
    finally:
        result.duration = round(time.monotonic() - start, 6)
    return result


def scan_entries(
    entries,
    config,
    hash_requested=False,
    progress=None,
    results=None,
    completed=None,
    heartbeat=None,
    quick=False,
):
    # Caller owns results, so completed records survive Ctrl+C for partial reports.
    results = [] if results is None else results
    siblings = {}
    for entry in entries:
        # Include skipped symlinks in the index: an external archive tool could otherwise
        # discover a continuation volume that our regular-file-only index concealed.
        path = entry if isinstance(entry, Path) else Path(entry.path)
        siblings.setdefault(path.parent, []).append(path)
    for index, entry in enumerate(entries, start=1):
        if progress:
            progress(index, len(entries), entry)
        result = (
            entry
            if isinstance(entry, Result)
            else test_file(
                entry,
                config,
                hash_requested,
                siblings=siblings.get(entry.parent),
                single=False,
                heartbeat=heartbeat,
                quick=quick,
            )
        )
        results.append(result)
        if completed:
            completed(result)
    return results
