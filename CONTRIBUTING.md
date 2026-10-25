# Contributing

Open an issue with the command, Python/OS/architecture, tool version, expected
behavior, and sanitized report. Do not attach firmware, game packages, secrets,
device identifiers or personal paths. Use tiny synthetic fixtures.

Create a branch, install `.[dev]` in a virtual environment, and run `make check
PYTHON=.venv/bin/python` plus `python -m build`. Include tests that demonstrate
integrity failures and operational errors, not only successful identification.
Keep runtime dependencies minimal and compatible with Debian ARM64.

Each new validator needs an upstream reference, verified license, supported
platforms, exact read-only argv and exit semantics, documented validation scope,
timeouts/output limits, corruption fixtures, and tests with an actual tool on
Linux ARM64. Add a `Validator` entry and dispatch in `validators.py`; no scanner
rewrite is needed. Never execute scanned files, extract protected content,
decrypt packages, mount images, repair source files or introduce false PASS.

MIT covers this repository's original code. External tools are separate programs,
not bundled libraries; do not copy their source without reviewing its license.
See [SECURITY.md](SECURITY.md) for private vulnerability reporting and
[docs/releasing.md](docs/releasing.md) for release criteria.
