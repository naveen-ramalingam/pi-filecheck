# Release procedure

1. Review Git status/history/remotes and preserve unrelated work. Update
   `src/pi_filecheck/__init__.py`, `VERSION`, changelog and release notes together.
2. Run every check below in a clean virtual environment. Examine integration
   skips and confirm actual native tools on supported Linux architectures.
3. Review source safety, source/export collisions, generated files, secrets,
   licenses, docs and dependency changes. Commit only project sources.
4. Verify Git identity and remote ownership/write permissions. Never overwrite a
   tag, and never push to an unverified remote. The maintainer must authorize
   remote publication for that release.

```bash
git status
git diff --check
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m build
git diff --stat
# After review and commit, only if the tag does not already exist:
git tag -a v0.1.0 -m "Pi FileCheck v0.1.0"
git show v0.1.0 --stat
# Only after verifying remote and authorization:
git push origin main
git push origin v0.1.0
```

Publish the checked tag and [release notes](releases/v0.1.0.md), clearly describing
this pre-1.0 release and actual tested platforms. Never claim Raspberry Pi hardware
testing based on ARM64 cloud CI alone.

Before **1.0.0**: all supported Python/Linux CI jobs must pass; complete a real
Raspberry Pi 5/DietPi ARM64 install, menu, removable-drive mount loss and large-file
exercise; validate every advertised native adapter with valid/corrupt fixtures;
review partial-volume/encryption outcomes and read-only safety; test clean upgrade
and uninstall; resolve outstanding security defects. Specialized Sony formats may
remain explicitly unsupported, but must never produce a misleading PASS.
