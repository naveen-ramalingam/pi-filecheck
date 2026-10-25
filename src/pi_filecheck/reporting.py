"""Exclusive report creation. Never truncate or replace an existing report/source."""

import csv
import io
import json
import os
import unicodedata
import uuid
from datetime import UTC, datetime

from . import __version__
from .models import Result, counts, exit_code
from .paths import absolute, reject_symlinks

MEANINGS = {
    "PASS": "The named integrity test succeeded; see its scope. No authenticity or safety guarantee.",
    "FAIL": "Corruption, a failed integrity test, or a trusted checksum mismatch was detected.",
    "UNKNOWN": "No complete compatible test was available; identification or hashing alone is insufficient.",
    "SKIP": "Intentionally skipped, continuation volume, or incomplete multipart set.",
    "ERROR": "The checker could not complete the operation; no integrity conclusion.",
}


def safe_text(value):
    # Preserve printable Unicode, escape controls (including terminal/line and bidi controls).
    return "".join(
        f"\\u{ord(c):04x}" if unicodedata.category(c).startswith("C") or c in "\r\n" else c
        for c in str(value)
    )


def human(results):
    lines = [f"Pi FileCheck v{__version__}"]
    for result in results:
        lines.extend(
            [f"[{result.status}] {safe_text(result.path)}", f"       {safe_text(result.reason)}"]
        )
        if result.sha256:
            lines.append(f"       SHA-256: {result.sha256} ({result.checksum_status})")
    lines.append("Summary: " + " | ".join(f"{k}: {v}" for k, v in counts(results).items()))
    lines.append("PASS applies only to the named test. UNKNOWN/SKIP are not verification.")
    return "\n".join(lines) + "\n"


def report(results, scan_path, interrupted=False):
    return {
        "schema_version": 1,
        "application": "Pi FileCheck",
        "version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "scan_path": str(scan_path),
        "interrupted": interrupted,
        "exit_code": 130 if interrupted else exit_code(results),
        "summary": counts(results),
        "status_meanings": MEANINGS,
        "results": [r.to_dict() for r in results],
    }


def json_text(document):
    return json.dumps(document, ensure_ascii=True, indent=2) + "\n"


def csv_text(document):
    stream = io.StringIO(newline="")
    keys = list(Result("").to_dict())
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    for row in document["results"]:
        clean = {}
        for key in keys:
            value = row[key]
            if isinstance(value, list):
                value = json.dumps(value, ensure_ascii=True)
            if isinstance(value, str):
                value = safe_text(value)
                # Prevent formula execution when CSV is opened by Excel/LibreOffice.
                if value.lstrip().startswith(("=", "+", "-", "@")):
                    value = "'" + value
            clean[key] = value
        writer.writerow(clean)
    return stream.getvalue()


def exclusive_write(path, text):
    path = reject_symlinks(absolute(path))
    # O_EXCL also rejects existing hard links to source files. No --force escape hatch.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
        stream.write(text)
    return path


def save_bundle(document, report_root):
    root = reject_symlinks(absolute(report_root))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:8]
    folder = root / name
    folder.mkdir(mode=0o700)
    exclusive_write(folder / "report.json", json_text(document))
    exclusive_write(folder / "report.csv", "\ufeff" + csv_text(document))
    rows = [Result(**row) for row in document["results"]]
    log = f"UTC: {document['created_at']}\nScan path: {safe_text(document['scan_path'])}\nInterrupted: {document['interrupted']}\n"
    log += human(rows)
    for row in rows:
        log += f"\n{safe_text(row.path)} | {row.format} | {row.size} bytes | {row.validator} | {row.duration}s | tool exit: {row.tool_exit_code}\n"
        if row.diagnostics:
            log += safe_text(row.diagnostics) + "\n"
    exclusive_write(folder / "details.log", log)
    return folder


def last_report(report_root):
    root = reject_symlinks(absolute(report_root))
    candidates = sorted(root.glob("*/report.json"))
    if not candidates:
        raise ValueError("No saved reports yet")
    path = reject_symlinks(candidates[-1])
    if path.stat().st_size > 100 * 1024**2:
        raise ValueError("Last report exceeds 100 MiB; inspect the report directly")
    return path, json.loads(path.read_text(encoding="utf-8"))
