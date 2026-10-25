# Pi FileCheck

Read-only file prechecks and optional integrity checks for Raspberry Pi 5 with DietPi or Raspberry Pi OS
(Debian ARM64). Quickly precheck downloaded archives before extraction, switch between local
folders and external drives, and keep machine-readable reports.

**Version 0.1.1 is a pre-1.0 release.** It never extracts archives,
executes scanned content, mounts images, repairs filesystems, or contacts a network
service. A successful archive test does **not** establish authenticity, malware
safety, successful installation, or playability. This project is independent of Sony.

**Scans and file tests default to quick metadata prechecks.** These can find damaged
headers, missing end records and known missing volumes without decompressing entire
archives. Readable metadata is **UNKNOWN**, never PASS: corruption in the middle of
a file can remain undetected. Full payload testing requires an explicit `--full`.
The interactive menu runs quick checks only.

## Install on DietPi / Raspberry Pi OS

Requires **Python 3.11+**, a POSIX system, and `venv`/`pip`. Debian 12 or newer is
recommended; Debian 11's default Python is too old. No Python runtime packages are
required. System package installation uses sudo; ordinary checks do not.

```bash
sudo apt update
sudo apt install python3 python3-venv git 7zip zstd lz4
git clone https://github.com/naveen-ramalingam/pi-filecheck.git
cd pi-filecheck
git checkout v0.1.1
./install.sh
export PATH="$HOME/.local/bin:$PATH"
filecheck version
filecheck doctor
filecheck
```

On older Debian releases, use `p7zip-full` if `7zip` is unavailable. RAR support
varies by build; optional `unrar` is in Debian's non-free repository. The tool's
actual result is authoritative. `filecheck doctor` reports available executables
and installation guidance. Optional `exfatprogs` enables read-only raw exFAT image
checks on Linux; `smartmontools` is used only in the manual health workflow.

The installer makes a private virtual environment at
`~/.local/share/pi-filecheck/venv`, links `~/.local/bin/filecheck`, and initializes
user config/report directories. It refuses existing commands/installations, even
ones named `filecheck` from another project. Review and uninstall an old Pi
FileCheck version before upgrading. Initial source installation may download the
setuptools build dependency from PyPI; the application itself has no network code.

```bash
# Alternate interpreter/prefix (prefix must be an absolute path)
PYTHON=python3.12 ./install.sh --prefix "$HOME/.local"

# Offline installation of a wheel built from a reviewed checkout
python3 -m pip install build
python3 -m build
./install.sh --offline --wheel "$PWD/dist/pi_filecheck-0.1.1-py3-none-any.whl"

# Remove only the marked installation; preserve configuration and all reports
./uninstall.sh
# Optionally remove the marked Pi FileCheck config file; reports are still preserved
./uninstall.sh --purge-config
```

Keep the checkout for `uninstall.sh`. Alternatively install a built wheel with
`pipx install dist/pi_filecheck-0.1.1-py3-none-any.whl`; manage that installation
using `pipx uninstall pi-filecheck`, not these scripts. No system Python is modified.
If user files were added inside the managed virtual environment, uninstall refuses
removal until those files have been preserved elsewhere.

## Start and switch folders

`filecheck` opens a terminal menu with the configured folder, free space, folder
browser, single-file/multipart checks, checksum comparison, identification, doctor,
last report and settings. Select **2** to browse a drive or enter an absolute path;
select **s** to save that folder. No source edits are needed.

```bash
filecheck config set scan_path /mnt/hdd/downloads
filecheck config show
filecheck scan                          # saved folder, top level
filecheck scan /mnt/usb/downloads       # one-time override
filecheck scan --path /mnt/usb/downloads
filecheck scan --recursive --yes
filecheck scan /mnt/hdd --require-mount /mnt/hdd --yes
filecheck scan --format json --yes > scan-summary.json
filecheck scan --format csv --output /tmp/new-report.csv --yes
filecheck test '/mnt/hdd/game archive.7z' # quick metadata precheck
filecheck test '/mnt/hdd/game.part02.rar' # checks through the first volume
filecheck hash /mnt/hdd/file.pkg
filecheck hash /mnt/hdd/file.pkg --expected-sha256 YOUR_64_HEX_DIGEST
filecheck identify /mnt/hdd/file.pkg --format json
filecheck report
filecheck doctor --format json
filecheck --help
# Optional, only when you deliberately want a full data test:
filecheck test '/mnt/hdd/game archive.7z' --full --sha256 --yes
```

Use `--output` when collision protection is needed. Existing outputs, symlinks and
hard links are refused. A shell's `>` redirection happens before the application
starts and cannot be protected by the application. Keep redirected outputs away
from source files and preferably outside the scanned folder.

The initial default is `~/Downloads`; a missing default is reported, never silently
changed to a whole-home scan. The menu requires a TTY (`ssh -t` for a menu over
SSH). Named subcommands work without one. Explicit full scans of at least 10 GiB or 1,000
entries require confirmation; use `--yes` in scripts. The menu confirms every
folder scan, after discovering the actual count and total size. Each result is
printed as it completes. Long checks and hashes emit an activity line every 10
seconds with elapsed time. On Linux, native checks also show approximate bytes
read by the validator (including cached/repeated reads or decompressor-pipe reads);
this is activity, not a completion percentage or disk benchmark. All live output
goes to stderr, so JSON/CSV on stdout stays parseable. A 90 GiB archive can take
many minutes to test even when the application is working normally; wait for the
final result. Quick checks have a 30-second limit per checker and do not hash
payloads, even if saved `sha256` is true. Compressed TAR and standalone compression
streams without an efficient metadata-only adapter receive UNKNOWN in quick mode.
ZIP, 7-Zip and RAR receive directory/header checks; raw exFAT images can receive
read-only metadata consistency checks. Ctrl+C stops a check and saves partial results.

## Results and exit codes

| State | Meaning |
| --- | --- |
| PASS | The named test succeeded, within its documented scope. |
| FAIL | Corruption/test failure or a supplied checksum mismatch was detected. |
| UNKNOWN | No complete compatible test was available. Never treat this as verified. |
| SKIP | Symlink/special file, continuation volume, or incomplete multipart set. |
| ERROR | Permission, I/O, tool/resource, timeout, or other operational failure. |

Exit codes: **0** all results PASS (also an empty scan, whose zero counts are
explicit); **1** any FAIL, UNKNOWN or SKIP; **2** operational or usage error;
**130** interrupted. Informational `version`, `config`, and successful `doctor`
commands return 0. `identify` and a hash without a reference return 1 with UNKNOWN
because they intentionally make no integrity claim. A continuation SKIP makes a
multipart folder scan return 1 even when its first-volume result passes; consult
the per-set first-volume result or use `test` for a whole-set decision.

## Supported full checks (`--full`)

| Formats | Test | Limits |
| --- | --- | --- |
| ZIP | Stream every member with Python `zipfile`; decompression/CRC | Encrypted or unsupported methods UNKNOWN; no extraction. |
| TAR | Stream headers and regular-file payloads | Structural/readability test only; TAR has no payload checksum. |
| TAR.GZ/TGZ, TAR.BZ2/TBZ2, TAR.XZ/TXZ | TAR test plus consume compression stream through its end | No authenticity guarantee. |
| TAR.ZST/TAR.ZSTD | Same TAR test with installed `zstd` decompressor | Missing tool UNKNOWN. |
| GZ, BZ2, XZ | Fully decompress to discarded chunks, checking stream integrity | Checksums depend on the stream format/options. |
| 7Z, RAR | `7zz t` / `7z t`; RAR fallback `unrar t` | Missing tool/method or password requirements UNKNOWN. |
| ZST/ZSTD, LZ4 | Native `-t` full-stream test | Some streams omit optional content checksums. |
| `.part1.rar`, `.part01.rar`, `.rar` + `.r00`, `.7z.001`, `.zip.001` | Detect first volume/gaps and invoke full-set native test | Consecutive filenames alone never prove completeness. |
| PKG, PUP, FFPFSC, FFPKG, FFPFS, ZAR | Format/extension identification and optional hashing | **UNKNOWN**: specialized validators are not integrated. |
| ELF, SELF, SPRX, BIN, ISO, IMG | Identification and optional hashing | **UNKNOWN**: no generic full integrity test. |
| exFAT raw-volume images | Linux `fsck.exfat -n`, after confirming exfatprogs and a raw-volume signature | Filesystem consistency only. Missing/unrecognized tools, other systems and partitioned images UNKNOWN. |

Content signatures take priority over extension hints; both evidence and any
mismatch appear in the report. A ZIP renamed to `.pkg` is tested as ZIP, with a
reported mismatch; this says nothing about Sony package validity. Proprietary
extensions have no guessed binary parser. See [validator research](docs/validators.md)
for sources, licenses, candidate tools and integration limitations.

Keep multipart sets in one folder, unchanged during testing. Missing known first
or intermediate volumes yield SKIP. The native tester must verify the final volume;
an absent last volume can instead appear as FAIL when the tool cannot distinguish
truncation from a missing part. No incomplete set is reported PASS. Hashes on a
multipart test cover **only the first volume**, never the implicit joined data.
Use `hash` on individual volumes for a trusted per-volume manifest. Filenames and
directory snapshots cannot protect against a malicious actor racing the checker;
check stable downloads in directories you control.

## Checksums and trusted references

SHA-256 is streamed in 1 MiB chunks. A digest alone is a fingerprint, not evidence
that the download is correct. Compare to a reference obtained independently from
a publisher you trust. Even a matching digest cannot make a malicious file safe,
and a reference downloaded alongside a compromised file may share the compromise.

`hash --expected-sha256` can PASS the **byte comparison** only. `test --full
--expected-sha256` records that comparison separately and retains UNKNOWN if the
container has no validator. A mismatch is FAIL. Hashing and archive validation are
separate reads, so stop active downloads before testing.

## Configuration and missing drives

TOML lives at `$XDG_CONFIG_HOME/pi-filecheck/config.toml`, default
`~/.config/pi-filecheck/config.toml`. Set keys through the CLI:

```bash
filecheck config set recursive true
filecheck config set sha256 true
filecheck config set timeout_seconds 7200
filecheck config set max_expanded_bytes 1099511627776
filecheck config set report_dir /mnt/reports/pi-filecheck
```

Additional keys: `confirm_bytes` (positive integer) and `required_mount` (absolute
mountpoint or empty string to clear). Saving `scan_path` records its current
non-root mountpoint. Saved scans refuse to proceed if that mount is absent.
One-time path overrides do not change the default and use only an explicitly
supplied `--require-mount` guard. An ordinary empty directory at `/mnt/hdd` does
not establish that a disk is mounted: use the guard. A mountpoint guard cannot
identify whether the **same** physical disk was reattached; confirm the device
with `findmnt`/`lsblk` when identity matters. Paths and symlink components are
checked; devices, FIFOs and symlinks are never followed as input files.

## Reports, resources and privacy

Each operation creates a fresh timestamp/UUID directory with `report.json`,
UTF-8 BOM `report.csv` (Excel), and `details.log` under
`$XDG_STATE_HOME/pi-filecheck/reports` (default `~/.local/state/pi-filecheck/reports`).
Records include path, size, format/evidence, validator, duration, SHA-256 and
comparison state, result, explanation, bounded diagnostics, tool exit code and
volume paths. JSON includes status definitions, summary counts, UTC timestamp,
version and interruption flag. CSV neutralizes spreadsheet formulas. Terminal
and log output escapes control characters. Reports are private user files but
contain names/hashes; review before sharing. No automatic report pruning occurs.

Use `--no-report` to avoid saved bundles; `--output` still writes its explicit new
export. Reports and config are excluded from recursive scans of their parent.
No file data, hashes or names are sent to external services.

Every validator has a timeout (default 3,600 seconds; maximum 86,400). Diagnostics
are capped at 64 KiB; excessive output is ERROR. Ctrl+C terminates validator process
groups and saves partial results with exit 130. Discovery interruption produces
an incomplete report rather than an all-clear result.

Built-in workers limit expanded bytes (default 1 TiB) and archive members (100,000);
on Linux they also cap virtual memory at 512 MiB. A limit is ERROR, not proof of
corruption. Native 7-Zip/UnRAR/zstd/lz4/exfatprogs use their own memory/expansion behavior;
the parent enforces time/output limits, but **does not sandbox these utilities**.
Keep Python and utilities patched. Choose a shorter `--timeout` for untrusted
archives and resource-limited hosts. Discovery/report records are held in memory;
split scans of directories with millions of entries. exFAT images, physical
filesystem consistency, archive integrity, and SMART health are distinct checks:
see [exFAT and device safety](docs/exfat-safety.md).

## Troubleshooting

- `UNKNOWN / Missing tool`: run `filecheck doctor`; install the named utility,
  then repeat. A detected executable does not prove every codec is available.
- Password/encryption: this version does not accept passwords. An encrypted
  failure remains UNKNOWN; it never bypasses encryption.
- Permission denied: grant the normal user read/search access to the exact
  file/folder. Avoid running the checker as root.
- Drive missing: check the cable and mount with normal system administration;
  FileCheck never mounts/unmounts a drive. Use a stable mountpoint in `/etc/fstab`.
- FAIL: retain the original, compare a trusted digest or download again. The tool
  never deletes, fixes, or overwrites the download.
- Timeout/expansion limit: adjust documented limits deliberately; a timeout is
  not a corruption finding. Native tools may report an I/O problem as test failure;
  inspect the saved diagnostics.
- `python3` is too old on macOS: use `PYTHON=python3.12 ./install.sh` or a newer
  interpreter. macOS is a development platform, not evidence of Pi compatibility.

## Development, tests and releases

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m build
git diff --check
```

Tests generate small synthetic archives; none include games, firmware, keys or
proprietary packages. Integration tests use actual installed compressors/7-Zip
and explicitly skip missing utilities. Installation tests build a wheel locally,
install offline into a disposable prefix, exercise the CLI, then verify uninstall
preserves unrelated files and reports. CI has Linux x86-64 and ARM64 jobs for
Python 3.11–3.14. ARM64 CI is not a Raspberry Pi 5 hardware test. Actual validation
evidence and remaining hardware checks are recorded in [testing](docs/testing.md).

The project uses Semantic Versioning; package version, `VERSION`, CLI, changelog,
and tags must agree. See [releasing](docs/releasing.md). The initial release was v0.1.0;
v1.0.0 requires the documented Linux/ARM64, hardware and safety release criteria.
See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the
[MIT license](LICENSE).
