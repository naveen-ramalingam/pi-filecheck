# Validation evidence

The automated suite covers configuration/overrides, Unicode and unusual filenames,
empty and sparse 8 GiB files, chunked SHA-256, trusted comparisons, valid/corrupt
archives, unsupported Sony formats, missing multipart volumes, symlinks/FIFOs,
permission failures, source mutation, exFAT identification, missing tools,
timeouts/output limits, interruptions, terminal menu startup, JSON/CSV validity,
source/export collisions, version agreement and disposable installation/removal.
Fixtures are generated synthetically. No scanned payloads are executed.

## Local evidence (2026-10-25)

- Host: macOS ARM64, Python 3.12.15. This is not a Raspberry Pi test.
- `python -m pytest -q` with native 7-Zip on PATH: **132 passed, 1 skipped**.
  The skipped integration needs Linux exfatprogs.
- Actual archive utilities exercised: 7-Zip 26.05 (ARM64, isolated Homebrew bottle
  under the ignored development environment), zstd 1.5.7 and lz4 1.10.0.
  Tests include valid/corrupt compressed streams, TAR/ZIP, split 7-Zip,
  literal wildcard names and encrypted 7-Zip/ZIP outcomes.
- `python -m ruff check .`, `python -m ruff format --check .`, Python bytecode
  compilation and `git diff --check` passed; sdist and universal wheel built.
- A wheel was installed offline into a fresh disposable prefix containing spaces;
  CLI/config/scan and guarded uninstall ran there. Real user installations were
  not changed. The installer rejected the system Python 3.9.6 with guidance.

## Raspberry Pi hardware validation (2026-10-25)

The tagged v0.1.0 release at commit `39e6846` was subsequently installed and
tested on a **Raspberry Pi 5 with 4 GiB RAM**, DietPi 10.8.2, Debian 13 (trixie)
ARM64, and Python 3.13.5. The release wheel and source archive matched their
published SHA-256 checksums before installation.

- The complete suite ran as a normal, non-root user: **133 passed in 8.00 seconds**,
  with no skips. Ruff lint/format checks and source/wheel builds also passed.
- Native utilities included Debian's 7-Zip 25.01, RAR plugin and UnRAR 7.1.8,
  zstd 1.5.7, lz4 1.10.0, and exfatprogs 1.2.9. The suite exercised actual
  archive utilities and read-only checks on disposable exFAT images.
- The installed command's menu, valid ZIP/7-Zip checks, corrupt ZIP rejection,
  missing-volume handling, Unicode filenames, symlink skipping, trusted digest
  comparison, unsupported PKG outcomes, export collision protection, mount guards,
  and JSON/CSV/log reports were checked separately from the development checkout.
- A shared, root-owned installation ran successfully as both the administrator
  and a normal user. Saved folder configuration, one-time overrides, report
  creation, and last-report retrieval worked. Ordinary checks required no root
  privileges.
- A newly created **1 GiB sparse zero-file on the mounted external ext4 HDD**
  matched an independently generated SHA-256 reference. Hashing took 1.08 seconds,
  with a sampled peak RSS of 22,752 KiB. This checks large-file streaming; sparse
  zero reads are not a physical disk throughput benchmark.
- The synthetic HDD file and its empty test directory were removed afterward.
  Existing downloads were not scanned or modified, and source fixture hashes
  remained unchanged. The live installation was preserved; uninstall tests used
  disposable prefixes.

Credentials, device addresses, private directory names, and generated reports
are not included in the repository.

## Linux CI

GitHub CI separately runs Python 3.11–3.14 on Linux x86-64 and ARM64 with 7-Zip,
zstd, lz4 and exfatprogs installed. It includes a disposable 64 MiB exFAT image
created solely as a synthetic fixture; checks assert no source content changes.
[CI run 40203697265](https://github.com/naveen-ramalingam/pi-filecheck/actions/runs/40203697265)
passed all eight jobs at commit `59f1b2a`, including the actual exFAT image check
on both architectures and all four Python versions. This validates Linux ARM64
compatibility separately from the macOS development host. Release tags are
created only after the final commit's CI also passes.

## Remaining coverage limits

Live removable-drive unplug/unmount behavior, physical exFAT partition checks,
SMART passthrough, valid RAR fixtures, specialized Sony binary validators, and
multi-gigabyte full hashes have not been tested. Large-file evidence consists of
sparse 8 GiB identification, the 1 GiB HDD hash above, and multi-chunk synthetic
hashing, not a real PS5 download. Cloud ARM64 CI and physical Pi testing are
separate evidence. Before 1.0, complete the remaining acceptance criteria in
[releasing](releasing.md).
