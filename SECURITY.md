# Security policy

0.1.x receives best-effort security fixes; there is no security certification.
Use current Python and native utilities. Archive parsers process untrusted data;
timeouts and memory limits are not a sandbox. Do not run as root, use unstable
download files, or scan directories writable by untrusted users.

The application opens regular files for reading, does not execute content, and
never extracts, mounts, repairs, formats, deletes or overwrites source data.
It refuses symlink inputs and existing export paths, caps diagnostic output,
and kills validator process groups on interruption. A malicious concurrent
rename/replacement can still race path-based external utilities. Work from
stable sources in directories you control. Shell output redirection occurs
outside the application and can overwrite files before FileCheck runs.

PASS proves only the named check succeeded. Hash calculation, magic, a matching
filename, or an unsupported format does not establish integrity. A trusted digest
comparison proves a byte match to that supplied digest, not safe or authentic
content by itself. Filesystem consistency is separate from data integrity and
physical drive health.

Use the repository's GitHub **Security → Report a vulnerability** if private
reporting is enabled. If unavailable, open a minimal issue requesting a private
contact without exploit details or personal files. Include a synthetic reproducer
once a private channel is established. No response-time SLA is offered.

Reports contain local paths and hashes. No telemetry or network calls occur in
the application. Installation/build tools may access PyPI and system package
repositories; offline wheel installation is supported. No secrets, copyrighted
fixtures, firmware, decryption keys or scanned-file artifacts belong in Git.
