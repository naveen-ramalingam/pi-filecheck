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

## Linux / hardware scope

GitHub CI separately runs Python 3.11–3.14 on Linux x86-64 and ARM64 with 7-Zip,
zstd, lz4 and exfatprogs installed. It includes a disposable 64 MiB exFAT image
created solely as a synthetic fixture; checks assert no source content changes.
CI run evidence is recorded when those jobs complete.

No physical Raspberry Pi, mounted removable-drive unplug, SMART passthrough,
valid RAR fixture, specialized Sony binary validator, or multi-gigabyte full hash
was tested locally. Large-file handling is exercised by sparse 8 GiB identification
and multi-chunk synthetic hashing, not a real PS5 download. A passing cloud ARM64
job is not evidence of a Pi or physical-drive test. Before 1.0, follow the hardware
acceptance criteria in [releasing](releasing.md).
