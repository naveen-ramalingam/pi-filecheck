# exFAT images, partitions and drive health

Pi FileCheck has **no device-level command** and never invokes `mount`, `umount`,
repair, formatting or SMART automatically. `test /dev/...` is refused.
An image file is a regular file; a physical partition is a block device. Do not
substitute one for the other without knowing what you selected.

## Image files

`filecheck identify image.exfat` checks the filesystem name at offset 3 when
present. `filecheck hash image.exfat` streams a fingerprint. Neither proves
filesystem consistency. `filecheck test image.exfat` can perform a read-only
consistency test on Linux when the input is a regular file with a raw exFAT
signature and `fsck.exfat -V` confirms exfatprogs. It invokes only
`fsck.exfat -n -- /absolute/path/image.exfat`, never a repair option, and reports
the exact validator and exit code. A missing tool, unconfirmed implementation or
non-Linux system gives UNKNOWN. Partitioned disk images may have an exFAT filesystem
at a nonzero offset; these require manual identification and are not supported.

Upstream [exfatprogs fsck manual](https://github.com/exfatprogs/exfatprogs/blob/master/manpages/fsck.exfat.8)
documents `-n` as checking without repair. Upstream
[file-opening code](https://github.com/exfatprogs/exfatprogs/blob/master/lib/libexfat.c)
uses `O_RDONLY` when write mode is disabled and obtains regular-file sizes by
seeking. The scanner requires a regular file and detects source changes.
The Linux integration test builds a new disposable synthetic image, checks it,
corrupts test metadata and verifies source SHA-256 remains unchanged after each
check. Do not add `-a`, `-p`, `-r`, `-y`, `-s`, `-b`, `--put-mbr` or `--clear-mbr`.
Keep images unmounted and stable during checks. Do not mount unknown images
automatically or run repair commands on the original.

## Physical partitions: explicit manual workflow

All commands below are for a human operator. Inspect the output before choosing
the next command; do not copy a device path from an example blindly.

```bash
lsblk -o NAME,PATH,TYPE,FSTYPE,SIZE,MOUNTPOINTS,MODEL
findmnt -t exfat
```

Select the exact exFAT **partition** by path, size, model and mountpoint. Filesystem
checks normally require an unmounted partition: close programs using it and decide
whether it is safe to unmount. FileCheck will never unmount it for you. Unmounting
is a separate system administration action requiring the drive owner's consent.

After the selected partition is unmounted, verify it is still the same device:

```bash
# Replace /dev/SELECTED_PARTITION only after positively identifying it above.
findmnt --source /dev/SELECTED_PARTITION
lsblk -o NAME,PATH,TYPE,FSTYPE,SIZE,MOUNTPOINTS /dev/SELECTED_PARTITION
# Only if unmounted and confirmed, read-only consistency diagnostics:
sudo fsck.exfat -n /dev/SELECTED_PARTITION
```

`findmnt` normally exits 1 when no mount is found; inspect both output and device
selection. `-n` is mandatory here. Do not repair, mount, format or otherwise write
to the partition as part of validation. A clean filesystem result checks metadata
consistency; it does not prove every archive payload is intact.

## Optional physical health diagnostics

After choosing the exact **whole disk**, read `smartctl` documentation for its
interface/enclosure. A manual read-only request is
`sudo smartctl -a /dev/SELECTED_DISK`. Some USB bridges require an explicitly
selected `-d` type, and some provide no SMART passthrough. Do not guess parameters,
start tests or change drive settings automatically. SMART may reveal failing
hardware even if a filesystem or archive check passes; a clean SMART report does
not guarantee a drive will not fail.
