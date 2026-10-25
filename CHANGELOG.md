# Changelog

Versions follow Semantic Versioning. This project is pre-1.0.

## 0.1.1 — 2026-10-25

- Make metadata-only quick prechecks the default for scans and file tests. Readable
  metadata is UNKNOWN; detected damage is FAIL. Full payload tests require explicit
  `--full`; the interactive menu uses quick checks only.
- Bound quick checker calls to 30 seconds and avoid automatic SHA-256 reads in quick
  mode, including when hashing is enabled in saved settings.
- Discover files before the interactive scan confirmation, showing the actual file
  count and total size instead of a zero-file placeholder.
- Print each scan result immediately, so failures are visible before later large
  archives finish.
- Show elapsed time every 10 seconds during long checks and hashes, with approximate
  validator read activity on Linux. Keep JSON/CSV stdout machine-readable.
- Explain unexpected-end failures as truncated or incomplete archives.

## 0.1.0 — 2026-10-25

- Initial CLI and interactive folder browser, saved configuration and mount guards.
- Streamed ZIP/TAR/compression checks and optional native archive testers.
- Multipart gap checks and first-volume testing without extraction.
- Conservative Sony/PS5 identification with honest UNKNOWN outcomes.
- Read-only raw exFAT image consistency checks with verified exfatprogs on Linux.
- Streaming SHA-256 and trusted reference comparisons, distinct from format checks.
- Exclusive JSON/CSV/log reports, resource limits and interruption handling.
- Per-user virtualenv installer/uninstaller, synthetic tests and Linux ARM64 CI.

Limitations: no integrated specialized Sony/PS5 validator, password input,
partitioned-image checks, device operations, or Raspberry Pi hardware certification.
