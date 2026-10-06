# ADR 0003: Alpha state is recoverable and diagnostics are allowlisted

**Status:** accepted

RX 0.5 stores mutable guest state on a separate ext4 image so rebuilding the
boot image cannot silently destroy user state. Session failures are counted;
three failures select safe mode until explicit recovery.

Recovery snapshots exclude other snapshots and reject absolute or parent-path
archive members during restore. Support bundles use an allowlist instead of
copying the state tree, omit cached packages and file-grant records, and scrub
personal paths and likely secrets before writing the archive.
