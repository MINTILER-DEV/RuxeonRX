# RX 0.5: Usable alpha

RX 0.5 provides a repeatable daily-QEMU workflow and recovery/diagnostic tools
for early testers.

- The image identifies itself as `0.5.0-alpha` and boots normal, test, or safe
  sessions.
- A 64 MiB ext4 state disk persists guest state across QEMU runs. If it cannot
  mount, the session clearly reports volatile fallback state.
- `rx-build doctor` reports prerequisites, kernel selection, and KVM access.
- Named recovery snapshots preserve service/application state and restore only
  path-safe archive members.
- Support bundles include a narrow allowlist of service state and diagnostics;
  home/state paths, usernames, and common secret fields are redacted.
- Automated tests cover the complete RX 0.2–0.5 lifecycle and QEMU requires
  session, persistence-state, app-launch, and health signals.

This remains an alpha image: the framebuffer shell and command-backed App
Manager are functional prototypes, not the final compositor or visual design.
