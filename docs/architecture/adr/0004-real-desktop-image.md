# ADR 0004: Package the desktop and services into a conventional Linux guest

**Status:** accepted; supersedes the temporary framebuffer image approach.

The previous initramfs only exercised shell scripts and lacked the Python
service runtime, window manager and interactive desktop. RX 0.5 uses a
checksum-pinned Debian generic cloud disk and pinned APT snapshot. Provisioning
runs in an isolated QEMU builder as guest root without requiring host root.

LightDM starts the RuxeonRX session as an unprivileged rx user. Openbox/Xorg
provides mature window management while a Tk application owns launcher,
App Manager, settings, permissions, notifications and recovery UX. rx-appd is
an actual single-writer process accessed through versioned Unix socket IPC.
Sandboxed apps use a separate token-authorized portal endpoint.

This deliberately adopts X11 for a testable first alpha rather than claiming
that the earlier proposed Wayland shell exists. X11's cross-client trust
limitation is recorded in the threat model. Subsequent hardening can replace
the display layer behind the same app and portal contracts.

Native .rxpkg packages contain manifest, program and optional assets. Payloads
are immutable per content digest, update history commits in the same atomic
registry write, and verified source archives support repair. Normal application
state persists in the guest disk; acceptance uses disposable overlays.
