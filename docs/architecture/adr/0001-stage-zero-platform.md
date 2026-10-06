# ADR 0001: Stage 0 platform, compositor boundary, package path, and manifest

**Status:** accepted

## Decision

Stage 0 targets x86_64 Linux hosts and uses Debian stable's package ecosystem
through `debootstrap` for the eventual base image.  The first reproducible boot
artifact is intentionally smaller: a static-BusyBox initramfs launched with the
host's Linux kernel in QEMU.  This proves the build, metadata, serial logging,
and health-test path before desktop packages are introduced.

The first graphical session will sit above an existing, mature Wayland
compositor.  A compositor is a replaceable implementation detail; the shell
communicates with application and portal services through documented IPC/data
contracts rather than compositor-private state.

Native packages initially enter through a curated Debian package source or a
reviewed local package adapter.  `rx-appd` is the sole registry writer.  Other
runtimes submit a normalized manifest and never edit launcher state directly.

The versioned JSON Schema at `sdk/spec/app-manifest.schema.json` is the initial
app-manifest contract.  It requires a stable reverse-DNS-like ID, source,
package/runtime kinds, launch intent, data/diagnostics locations, and requested
permissions.  Additional fields can be added only compatibly.

## Consequences

This choice prioritizes a known security-update cadence and package availability
without pretending that a temporary health image is the final distro image.
It also makes the boundaries needed for later Windows, Android, web, and VM
adapters explicit from the first native-app flow.
