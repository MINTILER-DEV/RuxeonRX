# ADR 0002: Native package transactions are manifest-cached and reversible

**Status:** accepted

RX 0.3 treats a native application manifest as the install contract. The App
Manager copies every accepted manifest to per-app/version cache storage and
records its SHA-256 digest. An update fully validates and caches its candidate
before atomically replacing the app record; the prior record becomes a rollback
snapshot. Repair accepts only an intact cached manifest.

This is intentionally not a replacement for a signed repository format. It
establishes the transaction and recovery boundary first, while package-source
trust and signature verification remain future work. Sources are recorded as
configuration only and never fetched implicitly.
