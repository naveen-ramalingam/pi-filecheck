"""Run trusted utilities with bounded diagnostics and a killable process group."""

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .models import Activity


@dataclass
class Completed:
    code: int | None
    output: str
    error: str = ""


def read_count(pid):
    """Linux read() accounting, including cache hits; approximate activity, not percent."""
    try:
        for line in (Path("/proc") / str(pid) / "io").read_text().splitlines():
            if line.startswith("rchar:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return None


def run(args, timeout, output_limit=65536, progress=None, progress_interval=10):
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as exc:
        return Completed(None, "", str(exc))
    captured = bytearray()
    started = time.monotonic()
    deadline = started + timeout
    next_progress = started + progress_interval
    initial_reads = read_count(process.pid) if progress else None
    error = ""
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map() or process.poll() is None:
                now = time.monotonic()
                if now >= deadline:
                    error = f"Validator exceeded {timeout}s time limit"
                    break
                if progress and now >= next_progress:
                    reads = read_count(process.pid)
                    processed = max(0, reads - (initial_reads or 0)) if reads is not None else None
                    progress(Activity(now - started, processed))
                    next_progress = now + progress_interval
                events = selector.select(min(0.1, max(0, deadline - now)))
                for key, _ in events:
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    room = output_limit - len(captured)
                    captured.extend(chunk[:room])
                    if len(chunk) > room:
                        error = f"Validator exceeded {output_limit} byte diagnostic limit"
                        break
                if error:
                    break
            if not error:
                try:
                    process.wait(timeout=max(0.01, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    error = f"Validator exceeded {timeout}s time limit"
    finally:
        # This also runs on Ctrl+C and kills decompressor children of the worker.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        process.stdout.close()
    return Completed(process.returncode, captured.decode("utf-8", errors="replace"), error)
