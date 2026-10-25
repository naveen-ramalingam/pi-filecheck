"""Public CLI and interactive menu; automation never depends on terminal prompts."""

import argparse
import json
import platform
import shutil
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

from . import __version__
from . import config as configuration
from .checksums import compare, sha256_file, trusted_digest
from .identify import identify
from .models import Result, exit_code
from .multipart import group
from .paths import absolute, directory, mountpoint, snapshot
from .reporting import (
    csv_text,
    exclusive_write,
    human,
    json_text,
    last_report,
    report,
    safe_text,
    save_bundle,
)
from .scanner import discover, scan_entries, test_file
from .validators import available_tools


def parser():
    root = argparse.ArgumentParser(
        prog="filecheck", description="Read-only integrity checks. No arguments opens the menu."
    )
    root.add_argument("--version", action="version", version=f"Pi FileCheck {__version__}")
    commands = root.add_subparsers(dest="command")
    scan = commands.add_parser("scan", help="Test files in a directory")
    scan.add_argument("directory", nargs="?")
    scan.add_argument("--path", dest="path_override")
    scan.add_argument("--recursive", action="store_true", default=None)
    scan.add_argument(
        "--require-mount", metavar="MOUNTPOINT", help="Refuse a scan if this drive is not mounted"
    )
    single = commands.add_parser("test", help="Test a file or a multipart set (select any volume)")
    single.add_argument("file")
    single.add_argument("--expected-sha256", type=trusted_digest)
    hash_cmd = commands.add_parser(
        "hash", help="Calculate SHA-256 or compare to a supplied trusted digest"
    )
    hash_cmd.add_argument("file")
    hash_cmd.add_argument("--expected-sha256", type=trusted_digest)
    ident = commands.add_parser("identify", help="Identify content; never proves integrity")
    ident.add_argument("file")
    for cmd in (scan, single):
        mode = cmd.add_mutually_exclusive_group()
        mode.add_argument(
            "--quick",
            dest="mode",
            action="store_const",
            const="quick",
            help="Metadata precheck only (default); never proves file contents intact",
        )
        mode.add_argument(
            "--full",
            dest="mode",
            action="store_const",
            const="full",
            help="Explicit full integrity test; can read/decompress the whole file",
        )
        cmd.set_defaults(mode="quick")
        cmd.add_argument("--sha256", action="store_true", help="Also stream a SHA-256 digest")
        cmd.add_argument("--timeout", type=int, metavar="SECONDS")
        cmd.add_argument(
            "--max-expanded-bytes", type=int, help="Expanded-byte limit for stdlib checks"
        )
        cmd.add_argument("--yes", "-y", action="store_true", help="Confirm an expensive test/scan")
    for cmd in (scan, single, hash_cmd, ident):
        cmd.add_argument("--format", choices=("human", "json", "csv"), default="human")
        cmd.add_argument(
            "--output", help="Export stdout format to a NEW file; existing files are refused"
        )
        cmd.add_argument(
            "--report-dir", help="Store JSON, CSV and detailed log in a new run subdirectory"
        )
        cmd.add_argument(
            "--no-report", action="store_true", help="Only emit stdout/explicit export"
        )
    cfg = commands.add_parser("config", help="Show or change user configuration")
    cfg_cmds = cfg.add_subparsers(dest="config_command", required=True)
    cfg_cmds.add_parser("show")
    cfg_set = cfg_cmds.add_parser("set")
    cfg_set.add_argument("key", choices=list(configuration.Config.__dataclass_fields__))
    cfg_set.add_argument("value")
    commands.add_parser("version", help="Show application version")
    doctor = commands.add_parser("doctor", help="Check runtime, scan path, and optional tools")
    doctor.add_argument("--format", choices=("human", "json"), default="human")
    previous = commands.add_parser("report", help="View the last saved report")
    previous.add_argument("--format", choices=("human", "json", "csv"), default="human")
    return root


def confirm_expensive(total, count, config, yes, always=False, quick=False):
    if yes or not (always or (not quick and (total >= config.confirm_bytes or count >= 1000))):
        return
    message = (
        f"Quick-check {count} files, {total / 1024**3:.2f} GiB total? Metadata only; file contents are not verified."
        if quick
        else f"Test {count} files, {total / 1024**3:.2f} GiB? This may read/decompress all data."
    )
    if not sys.stdin.isatty():
        raise ValueError(message + " Rerun with --yes for non-interactive use.")
    print(message, file=sys.stderr)
    if input("Continue [y/N]: ").strip().lower() != "y":
        raise ValueError("Scan cancelled before testing")


def emit(results, args, config, scan_path, interrupted=False):
    document = report(results, scan_path, interrupted)
    fmt = args.format
    output = (
        json_text(document)
        if fmt == "json"
        else csv_text(document)
        if fmt == "csv"
        else human(results)
    )
    # Reserve any requested export before auto-report writes; never overwrite a source/hard link.
    if args.output:
        exclusive_write(args.output, output)
    if not args.no_report:
        folder = save_bundle(document, args.report_dir or config.report_dir)
        print(f"Reports: {safe_text(folder)}", file=sys.stderr)
    sys.stdout.write(output)
    return 130 if interrupted else exit_code(results)


def doctor(config, fmt):
    tools = available_tools()
    path_error = ""
    try:
        path = directory(config.scan_path, config.required_mount)
        disk = shutil.disk_usage(path)
        storage = {"path": str(path), "mountpoint": str(mountpoint(path)), "free_bytes": disk.free}
    except (OSError, ValueError) as exc:
        storage, path_error = {}, str(exc)
    document = {
        "version": __version__,
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "config_file": str(configuration.config_path()),
        "storage": storage,
        "path_error": path_error,
        "tools": tools,
        "builtin_checks": ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "gz", "bz2", "xz"],
        "specialized_validators": "PS5 formats are not integrated; Linux exFAT raw images use verified exfatprogs -n; physical-device/SMART diagnostics are manual only",
    }
    if fmt == "json":
        print(json.dumps(document, indent=2))
    else:
        print(
            f"Pi FileCheck v{__version__} | Python {document['python']} | {document['system']} {document['machine']}"
        )
        print(f"Config: {safe_text(configuration.config_path())}")
        print(
            "Scan path: "
            + (
                safe_text(path_error)
                if path_error
                else f"{safe_text(config.scan_path)} | {storage['free_bytes'] / 1024**3:.2f} GiB free"
            )
        )
        for tool in tools:
            print(f"{tool['name']}: {safe_text(tool['path'] or 'MISSING')} | {tool['install']}")
        print(
            "ZIP/TAR/gzip/bzip2/xz checks are built in. Optional missing tools do not disable them."
        )
        print(document["specialized_validators"])
    return 2 if path_error else 0


def run_command(args, config, confirm_scan=False):
    if args.command == "version":
        print(f"Pi FileCheck {__version__}")
        return 0
    if args.command == "config":
        if args.config_command == "set":
            configuration.set_value(config, args.key, args.value)
        print(json.dumps(asdict(config), indent=2))
        return 0
    if args.command == "doctor":
        return doctor(config, args.format)
    if args.command == "report":
        path, document = last_report(config.report_dir)
        print(f"Last report: {safe_text(path)}", file=sys.stderr)
        sys.stdout.write(
            json_text(document)
            if args.format == "json"
            else csv_text(document)
            if args.format == "csv"
            else human([Result(**r) for r in document["results"]])
        )
        return document["exit_code"]
    config = replace(config)
    if getattr(args, "timeout", None) is not None:
        config.timeout_seconds = args.timeout
    if getattr(args, "max_expanded_bytes", None) is not None:
        config.max_expanded_bytes = args.max_expanded_bytes
    config.validate()
    quick = getattr(args, "mode", "full") == "quick"
    if quick and (getattr(args, "sha256", False) or getattr(args, "expected_sha256", None)):
        raise ValueError(
            "Quick checks do not hash file contents. Use filecheck hash explicitly or opt in with --full."
        )
    results = []
    interrupted = False
    scan_path = ""
    current = ""

    def heartbeat(activity):
        elapsed = int(activity.elapsed)
        duration = f"{elapsed // 3600:02}:{elapsed // 60 % 60:02}:{elapsed % 60:02}"
        reads = ""
        if activity.processed_bytes is not None:
            reads = f" | read ~{activity.processed_bytes / 1024**3:.2f} GiB"
        print(
            f"[working] {safe_text(Path(current).name)} | {activity.phase} | elapsed {duration}{reads}",
            file=sys.stderr,
            flush=True,
        )

    def completed(result):
        print(
            f"[{result.status}] {safe_text(Path(result.path).name)} | {safe_text(result.reason)} ({result.duration:.1f}s)",
            file=sys.stderr,
            flush=True,
        )

    try:
        if args.command == "scan":
            if args.directory and args.path_override:
                raise ValueError("Choose a positional directory or --path, not both")
            override = args.directory or args.path_override
            required_mount = args.require_mount or (config.required_mount if not override else "")
            root = directory(override or config.scan_path, required_mount)
            scan_path = str(root)
            recursive = args.recursive if args.recursive is not None else config.recursive
            report_root = absolute(args.report_dir or config.report_dir)
            # Prevent scanning our own reports/config, including when scanning the home folder.
            excluded = [report_root, configuration.config_path()]
            if args.output:
                excluded.append(absolute(args.output))
            entries = list(discover(root, recursive, excluded))
            total = 0
            for entry in entries:
                if isinstance(entry, Path):
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        pass
            free = shutil.disk_usage(root).free
            print(
                f"Scan path: {safe_text(root)} | {free / 1024**3:.2f} GiB free | {len(entries)} entries",
                file=sys.stderr,
            )
            file_count = sum(isinstance(entry, Path) for entry in entries)
            confirm_expensive(total, file_count, config, args.yes, always=confirm_scan, quick=quick)
            if quick:
                print(
                    "Quick precheck: metadata only, 30s limit per checker; readable metadata is UNKNOWN, not full verification.",
                    file=sys.stderr,
                )

            def progress(index, count, entry):
                nonlocal current
                current = str(entry if isinstance(entry, Path) else entry.path)
                print(f"[{index}/{count}] {safe_text(current)}", file=sys.stderr, flush=True)

            scan_entries(
                entries,
                config,
                args.sha256,
                progress,
                results,
                completed=completed,
                heartbeat=heartbeat,
                quick=quick,
            )
        elif args.command == "test":
            current = scan_path = str(absolute(args.file))
            before = snapshot(current)
            volumes = group(absolute(current))
            total = (
                sum(snapshot(p)[2] for p in volumes.paths)
                if volumes and not volumes.reason
                else before[2]
            )
            confirm_expensive(
                total, len(volumes.paths) if volumes else 1, config, args.yes, quick=quick
            )
            print(
                f"{'Quick precheck' if quick else 'Testing'}: {safe_text(current)} | {total / 1024**3:.2f} GiB",
                file=sys.stderr,
                flush=True,
            )
            results.append(
                test_file(
                    current,
                    config,
                    args.sha256,
                    args.expected_sha256,
                    heartbeat=heartbeat,
                    quick=quick,
                )
            )
            completed(results[-1])
        else:
            current = scan_path = str(absolute(args.file))
            start = time.monotonic()
            result = Result(current, check_mode=args.command)
            try:
                result.size = snapshot(current)[2]
                identified = identify(absolute(current))
                result.format, result.detection = identified.format, identified.evidence
                if args.command == "hash":
                    result.validator = (
                        "SHA-256 comparison" if args.expected_sha256 else "SHA-256 calculation"
                    )
                    result.sha256 = sha256_file(current, config.timeout_seconds, progress=heartbeat)
                    result.checksum_status = "CALCULATED"
                    result.reason = "SHA-256 calculated without a trusted reference; integrity/authenticity not established"
                    if args.expected_sha256:
                        matched = compare(result.sha256, args.expected_sha256)
                        result.checksum_status = "MATCH" if matched else "MISMATCH"
                        result.status = "PASS" if matched else "FAIL"
                        result.reason = (
                            "SHA-256 matches the supplied reference; no container or authenticity guarantee"
                            if matched
                            else "SHA-256 does not match the supplied reference"
                        )
                else:
                    result.reason = "Format identified/hinted only; no integrity test performed"
            except (OSError, ValueError) as exc:
                result.status, result.reason = "ERROR", str(exc)
            result.duration = round(time.monotonic() - start, 6)
            results.append(result)
    except KeyboardInterrupt:
        interrupted = True
        results.append(
            Result(
                current or scan_path,
                status="ERROR",
                reason="Interrupted by user; incomplete results",
            )
        )
        print("Interrupted. Saving partial results.", file=sys.stderr)
    except (OSError, ValueError) as exc:
        print(f"filecheck: {safe_text(exc)}", file=sys.stderr)
        results.append(
            Result(current or scan_path or config.scan_path, status="ERROR", reason=str(exc))
        )
    return emit(results, args, config, scan_path, interrupted)


def choose_directory(config):
    current = (
        directory(config.scan_path) if Path(config.scan_path).is_dir() else directory(Path.home())
    )
    while True:
        print(f"\nFolder: {safe_text(current)}")
        print(f"Free: {shutil.disk_usage(current).free / 1024**3:.2f} GiB")
        children = sorted(p for p in current.iterdir() if not p.is_symlink() and p.is_dir())
        for index, child in enumerate(children[:50], start=1):
            print(f"{index}. {safe_text(child.name)}/")
        print(
            "s: select this folder | u: parent | p: enter absolute path | m: /mnt | v: /media | q: cancel"
        )
        answer = input("Folder choice: ").strip()
        if answer == "s":
            configuration.set_value(config, "scan_path", str(current))
            return
        if answer == "q":
            return
        if answer == "u":
            current = directory(current.parent)
        elif answer == "p":
            value = input("Absolute folder path: ").strip()
            if not Path(value).expanduser().is_absolute():
                raise ValueError("Enter an absolute path")
            current = directory(value)
        elif answer in ("m", "v"):
            current = directory(
                "/mnt" if answer == "m" else ("/Volumes" if sys.platform == "darwin" else "/media")
            )
        elif answer.isdigit() and 1 <= int(answer) <= min(50, len(children)):
            current = directory(children[int(answer) - 1])


def interactive(config):
    if not sys.stdin.isatty():
        raise ValueError(
            "The menu needs a terminal. Use filecheck scan --yes, test, hash, identify or --help for scripts/SSH."
        )
    while True:
        print(f"\nPi FileCheck v{__version__}\nScan path: {safe_text(config.scan_path)}")
        try:
            root = directory(config.scan_path, config.required_mount)
            print(
                f"Free space: {shutil.disk_usage(root).free / 1024**3:.2f} GiB | Mount: {safe_text(mountpoint(root))}"
            )
        except (OSError, ValueError) as exc:
            print(safe_text(exc))
        print(
            "\n1. Quick-check configured folder\n2. Choose another folder\n3. Quick-check a single file\n4. Quick-check a multipart archive\n5. Calculate or compare SHA-256 (reads whole file)\n6. Identify a file\n7. Check tool availability\n8. View last report\n9. Configuration\n0. Exit"
        )
        try:
            choice = input("Choice: ").strip()
            if choice == "0":
                return 0
            if choice == "2":
                choose_directory(config)
                continue
            if choice == "9":
                print(json.dumps(asdict(config), indent=2))
                key = input("Key to change (Enter to return): ").strip()
                if key:
                    configuration.set_value(config, key, input("New value: ").strip())
                continue
            argv = {"1": ["scan"], "7": ["doctor"], "8": ["report"]}.get(choice)
            if choice in ("3", "4", "5", "6"):
                argv = [
                    {"3": "test", "4": "test", "5": "hash", "6": "identify"}[choice],
                    input("File path (any volume for multipart): ").strip(),
                ]
                if choice == "5":
                    expected = input("Trusted SHA-256 (Enter to calculate only): ").strip()
                    if expected:
                        argv.extend(["--expected-sha256", expected])
            if argv:
                run_command(parser().parse_args(argv), config, confirm_scan=choice == "1")
        except (ValueError, OSError) as exc:
            print(f"Error: {safe_text(exc)}", file=sys.stderr)
        except EOFError:
            return 0


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == "version":
            print(f"Pi FileCheck {__version__}")
            return 0
        config = configuration.load()
        return interactive(config) if args.command is None else run_command(args, config)
    except (OSError, ValueError) as exc:
        print(f"filecheck: {safe_text(exc)}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
