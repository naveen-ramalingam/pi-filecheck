"""Run trusted utilities with bounded diagnostics and a killable process group."""

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass


@dataclass
class Completed:
    code: int | None
    output: str
    error: str = ""


def run(args, timeout, output_limit=65536):
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
    deadline = time.monotonic() + timeout
    error = ""
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() >= deadline:
                    error = f"Validator exceeded {timeout}s time limit"
                    break
                events = selector.select(min(0.1, max(0, deadline - time.monotonic())))
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
