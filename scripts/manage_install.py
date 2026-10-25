#!/usr/bin/env python3
"""Conservative per-user installer, with no sudo and no unrelated path replacement."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

APP_ID = "pi-filecheck-managed-venv-v1"


def checked_path(value):
    path = Path(os.path.abspath(os.path.expanduser(str(value))))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Refusing symlink in installation path: {part}")
    return path


def execute(argv):
    # A caller's source tree must not masquerade as an installed venv package.
    environment = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    subprocess.run(argv, check=True, env=environment)


def install(args):
    source = checked_path(args.source)
    if not Path(args.prefix).expanduser().is_absolute():
        raise ValueError("Installation prefix must be absolute")
    prefix = checked_path(args.prefix)
    target = prefix / "share/pi-filecheck/venv"
    marker = target / ".pi-filecheck-install.json"
    link = prefix / "bin/filecheck"
    # Existing installations require explicit removal; never silently replace a command.
    if target.exists() or link.exists() or link.is_symlink():
        raise ValueError(
            "Installation path or filecheck command already exists; review it and uninstall first"
        )
    if args.offline and not args.wheel:
        raise ValueError("--offline requires --wheel /path/to/pi_filecheck-*.whl")
    wheel = checked_path(args.wheel) if args.wheel else None
    if wheel and (
        not wheel.is_file() or not wheel.name.startswith("pi_filecheck-") or wheel.suffix != ".whl"
    ):
        raise ValueError("--wheel must name an existing pi_filecheck wheel")
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    # Reserve exactly the directory we own, to make failed-install cleanup precise.
    target.mkdir(mode=0o700)
    linked = False
    try:
        execute([sys.executable, "-m", "venv", str(target)])
        python = target / "bin/python"
        command = [
            str(python),
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
        ]
        if args.offline:
            command.append("--no-index")
        execute([*command, str(wheel or source)])
        execute([str(target / "bin/filecheck"), "version"])
        metadata = {"application": APP_ID, "prefix": str(prefix), "target": str(target)}
        with marker.open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream)
        link.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        # symlink() is exclusive; it cannot replace an unrelated command.
        link.symlink_to(target / "bin/filecheck")
        linked = True
        # Create app-owned config/report directories in the current user's XDG locations.
        execute(
            [
                str(python),
                "-c",
                "from pi_filecheck.config import load,save; c=load(); save(c); "
                "from pi_filecheck.paths import reject_symlinks; "
                "reject_symlinks(c.report_dir).mkdir(mode=0o700,parents=True,exist_ok=True)",
            ]
        )
        metadata["installed_paths"] = sorted(str(p.relative_to(target)) for p in target.rglob("*"))
        # This is our just-created marker. Include it in the installed-path manifest.
        marker.write_text(json.dumps(metadata), encoding="utf-8")
    except BaseException:
        if linked and link.is_symlink() and os.readlink(link) == str(target / "bin/filecheck"):
            link.unlink()
        shutil.rmtree(target)
        raise
    print(f"Installed for {platform.system()} {platform.machine()}: {link}")
    print(f'Add to PATH if needed: export PATH="{prefix / "bin"}:$PATH"')
    print("Run filecheck doctor for optional utilities. No system packages were installed.")


def uninstall(args):
    if not Path(args.prefix).expanduser().is_absolute():
        raise ValueError("Installation prefix must be absolute")
    prefix = checked_path(args.prefix)
    target = checked_path(prefix / "share/pi-filecheck/venv")
    marker = checked_path(target / ".pi-filecheck-install.json")
    if not marker.is_file():
        raise ValueError("No Pi FileCheck installation marker; refusing removal")
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    expected = {"application": APP_ID, "prefix": str(prefix), "target": str(target)}
    if {k: metadata.get(k) for k in expected} != expected:
        raise ValueError("Installation marker does not match this prefix; refusing removal")
    installed_paths = metadata.get("installed_paths")
    if not isinstance(installed_paths, list) or not all(
        isinstance(p, str) for p in installed_paths
    ):
        raise ValueError("Installation manifest missing; refusing removal")
    present = {str(p.relative_to(target)) for p in target.rglob("*")}
    added = present - set(installed_paths)
    if added:
        raise ValueError(
            "Unrecognized files were added inside the virtual environment; preserve/move them before uninstalling: "
            + ", ".join(sorted(added)[:5])
        )
    link = prefix / "bin/filecheck"
    expected_target = str(target / "bin/filecheck")
    if link.is_symlink():
        if os.readlink(link) != expected_target:
            raise ValueError("filecheck command points elsewhere; refusing removal")
        link.unlink()
    elif link.exists():
        raise ValueError("filecheck command was replaced by another file; refusing removal")
    shutil.rmtree(target)
    # Never recursively delete a prefix, reports directory, home or user configuration tree.
    if args.purge_config:
        config_root = checked_path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        config = checked_path(config_root / "pi-filecheck/config.toml")
        if config.exists():
            if not config.read_text(encoding="utf-8").startswith(
                "# Pi FileCheck user configuration\n"
            ):
                raise ValueError("Configuration ownership marker missing; config was preserved")
            config.unlink()
    print(
        "Pi FileCheck uninstalled. Reports preserved. "
        + ("Configuration removal requested." if args.purge_config else "Configuration preserved.")
    )


def main():
    if sys.version_info < (3, 11):  # noqa: UP036 - check runs before package installation
        print(
            "Pi FileCheck requires Python 3.11+. On Debian 12+ install python3 and python3-venv.",
            file=sys.stderr,
        )
        return 2
    if platform.system() not in ("Linux", "Darwin"):
        print("Supported installation systems: Linux, macOS (development).", file=sys.stderr)
        return 2
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("action", choices=("install", "uninstall"))
    root.add_argument("--prefix", default=str(Path.home() / ".local"))
    root.add_argument("--source")
    root.add_argument("--wheel")
    root.add_argument("--offline", action="store_true")
    root.add_argument(
        "--purge-config",
        action="store_true",
        help="Remove only the marked app config; always preserve reports",
    )
    args = root.parse_args()
    try:
        install(args) if args.action == "install" else uninstall(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Pi FileCheck installer: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
