# RX 0.5: Native graphical alpha

The complete guest replaces the old framebuffer demonstration with a Debian
13 desktop disk and interactive RuxeonRX session. It includes real executable
packages, service IPC, portal dialogs and the native lifecycle from RX 0.2/0.3.

The alpha has persistent guest storage, supervised appd/shell processes with
restart budgets, recovery mode, accessibility preferences, device inventory,
checksum-verified source downloads, immutable version caches, repair archives,
atomic update/rollback registry history, exact state snapshots and support
export. Build inputs are locked and package versions recorded.

Acceptance runs in a disposable overlay and boots three times. It requires visible
shell/app windows, keyboard/mouse interaction, denied/allowed file/notification
prompts, actual file selection, app updates, persistence across reboot,
supervised service crash recovery and a safe-mode boot. Unit/integration tests
exercise actual payload output, tamper recovery and package/portal/snapshot
security boundaries. Evidence lives in out/desktop.

Use [the developer/tester guide](../development/desktop-alpha.md) and
[the support/security matrix](../development/test-matrix.md). This release
is scoped to QEMU native apps. External testers must record real feedback;
CI cannot satisfy that human release gate by itself.
