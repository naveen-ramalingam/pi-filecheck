# Validator research and scope

Reviewed 2026-10-25. Upstream feature claims below are **not** local integration
certifications. No third-party code, binaries, firmware or keys are bundled.

## Sony and PS5 candidates

| Upstream | Evidence and license | Decision for 0.1.0 |
| --- | --- | --- |
| [Packwright](https://github.com/itsmemac/Packwright) | README at observed commit `39c8675` (2026-10-07) advertises `packwright verify game.ffpkg`, package verification, and exFAT/FFPKG/FFPFSC/ZArchive read/verify. GPL-3.0. Windows, macOS and Linux; documented Linux downloads/build commands target x64, macOS ARM64 is listed. Upstream explicitly calls real-console behavior experimental. | Active candidate; no verified Linux ARM64 build or independently tested read-only exit contract here. Do not auto-install or invoke; PKG/FFPKG/FFPFSC/ZAR remain UNKNOWN. `.ffpfs` coverage is unconfirmed. |
| [LibOrbisPkg](https://github.com/maxton/LibOrbisPkg) | Upstream README declares LGPL-3.0 and documents `pkg_validate` checking hashes/signatures of **PS4** PKG. .NET Core solution exists; observed repository has older history (README 2020). | PS4 support is not PS5 support. No adapter or ARM64 integration test in this release. UNKNOWN. |
| [PS5-Firmware-Checker](https://github.com/pearlxcore/PS5-Firmware-Checker) | Search/upstream description identifies a Windows Forms app for checking/downloading the **latest firmware version**. This does not demonstrate binary PUP integrity validation. No code from it is used; its license/build compatibility is not accepted for integration. | Not evidence of a read-only PS5 PUP validator on Debian ARM64. PUP UNKNOWN. |

No official public Sony package/firmware integrity CLI compatible with this target
was verified during this review. This is a scoped research finding, not a claim
that no such tool can ever exist. Encrypted retail packages and debug packages
need different handling; package names and magic cannot establish validity.
FFPFS/FFPFSC/FFPKG/ZAR are not assigned guessed specifications. ELF identification
uses the conventional ELF magic only; SELF/SPRX/BIN/ISO/IMG receive no integrity
claim. Trusted checksum comparison remains a separately recorded byte test.

Future adapters must first verify upstream license, release health, Linux ARM64
builds, safe read-only arguments, no extraction/network/repair side effects,
failure exit codes and complete coverage on synthetic legal fixtures. An installed
executable by name is insufficient. Candidate tools with write/conversion features
must never be invoked through those features by FileCheck.

## Implemented archive tests and optional utilities

| Component | License/source | Integration |
| --- | --- | --- |
| Python stdlib ZIP/TAR/gzip/bz2/lzma | [PSF license](https://docs.python.org/3/license.html) (system runtime, not redistributed) | Stream content; worker timeout, expanded-byte/member limits; Linux 512 MiB address-space cap. TAR structure is distinct from payload checksums. |
| 7-Zip | [Official license](https://www.7-zip.org/license.txt): LGPL, BSD portions, unRAR restriction in relevant components | `7zz t` or `7z t` with the intended archive handler forced (including inner format + split chain) and wildcard matching disabled; no extraction. Linux ARM64 binaries are an upstream distribution option; actual codec availability is build-specific. Not bundled. |
| UnRAR | [RARLAB source/license](https://www.rarlab.com/rar_add.htm), restrictive unRAR license | Optional RAR-only `t` fallback. Not a requirement for the MIT code; not bundled. |
| Zstandard | [facebook/zstd](https://github.com/facebook/zstd), BSD-3-Clause or GPL-2.0 | `zstd -t`, or streamed `-dc` to TAR worker. Packaged for Debian ARM64. |
| LZ4 | [lz4/lz4](https://github.com/lz4/lz4), CLI GPL-2.0; library BSD-2-Clause | `lz4 -t`; stream may omit optional content checksums. Packaged for Debian ARM64. |
| exfatprogs | [upstream](https://github.com/exfatprogs/exfatprogs), GPL-2.0-or-later; observed update 2026-08-14 | Linux regular raw-volume images only: verify implementation with `-V`, then `fsck.exfat -n -- image`. [fsck source](https://github.com/exfatprogs/exfatprogs/blob/master/fsck/fsck.c) maps `-n` to no-write mode; [library source](https://github.com/exfatprogs/exfatprogs/blob/master/lib/libexfat.c) opens `O_RDONLY` and uses file size. Devices/partitioned images are excluded. Exit 4 is FAIL; unexpected repair or operational codes ERROR. |
| smartmontools | [upstream](https://www.smartmontools.org/), GPL-2.0-or-later | Optional manual diagnostics; no automatic execution or USB passthrough assumption. |

[Microsoft's exFAT specification](https://learn.microsoft.com/en-us/windows/win32/fileio/exfat-specification#312-filesystemname-field)
defines the filesystem-name field at offset 3 as 8 bytes, `EXFAT` and three spaces.
Reading that field identifies a candidate raw-volume image; it is not a consistency
test. No partition table or filesystem implementation is invented by this project.

Native utilities are separate installed programs. Their licenses remain applicable
to any redistribution of those programs. This MIT repository neither bundles nor
links their code. All named binaries should be installed from trusted OS/upstream
sources, maintained and patched. `doctor` detects availability, not provenance,
version security, codec compatibility or support for every possible archive.
