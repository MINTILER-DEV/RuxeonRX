# RX 0.5 verification: 2026-10-10

The native-QEMU software path through RX 0.5 is implemented. The release is
an x86_64 Linux desktop alpha, not a hardware installer or a finished Android,
web-app, or Windows-compatibility release.

| Milestone | Implemented software |
| --- | --- |
| RX 0.1 | Checksum-pinned Debian 13/kernel image, locked APT snapshot, isolated builder, boot/health checks, desktop CI workflow |
| RX 0.2 | LightDM/Openbox session, interactive shell, real executable native packages, launcher/registry, app logs and lifecycle |
| RX 0.3 | Install/update/repair/rollback/remove, verified sources, desktop/default-handler integration, scoped file/notification portals, permission UI |
| RX 0.4 bridge | Real process supervision/restart budgets, safe boot, validated persistent settings, accessibility controls and device inventory |
| RX 0.5 | Persistent desktop disk, exact state snapshots/restoration, diagnostics/support export, Windows launcher, automated graphical/reboot acceptance and tester documentation |

## Executed checks

Runtime source revision: `109d96e22f9ffabe96afa83757fd036cd02b0744`.
Subsequent documentation-only commits do not change the tested runtime.

- Linux: all 8 unit and 13 integration tests passed; Python compilation passed.
- Windows: all 8 unit tests and 10 applicable integration tests passed;
  3 Linux-only integration tests skipped; Python compilation passed.
- Windows QEMU 11.1.1: final three-boot acceptance passed, using TCG,
  2 virtual CPUs, 2 GiB RAM, BIOS, standard VGA and VirtIO storage.
- Linux QEMU 8.2.2: three-boot acceptance passed at `9607f39` with the final
  sandbox/registry fixes; the `109d96e` rebuild, which adds readable
  high-contrast tab labels, is undergoing final acceptance.

Graphical acceptance operates actual windows with keyboard/mouse input. It
tests sandbox read-only code/broker directories, writable private app data,
network namespace separation, search/install/launch, denied/allowed file and
notification dialogs, native file selection/open-with, regular native apps,
logs, executable updates/repair/rollback, launcher pins, text scale/contrast,
reboot persistence, remove/purge, exact snapshot restore, real appd/shell
process termination and supervised recovery, and safe boot with intentionally
corrupted registry/settings/source files followed by recovery.

## Local Windows handoff

The self-contained disk is `out/desktop/ruxeonrx-0.5.qcow2` (12 GiB virtual
capacity; approximately 766 MiB stored; no backing disk).

SHA-256: `1e9a02d2e4f72946ad8e995dcd2e8b9bfefe734cabd02c8b1fd4d5f3a685d003`.
`qemu-img check` found no errors. Its actual hash matches both the artifact
manifest and the successful acceptance report.

Run from the repository in PowerShell with QEMU on PATH:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run-windows.ps1
```

No Linux server is needed to run this local disk. Screenshots, serial logs,
`artifact.json` and `acceptance.json` are in `out/desktop/`; the reviewed host
evidence export is `out/support.zip`. Disks, private builder keys and generated
evidence are intentionally not committed.

## Remaining release gates and boundaries

External tester feedback is still pending and cannot be replaced with automated
tests. The GitHub CI workflow is implemented, but a remote GitHub run was not
performed in this session; local Linux build/boot/test execution is not claimed
as a GitHub CI result. KVM/WHPX, UEFI and physical installation were not tested.
X11 is not a hostile-app display-isolation boundary; imported desktop apps are
explicitly unrestricted. File/notification portals are supported, not arbitrary
camera/audio/device portals. See the [support matrix](../development/test-matrix.md)
and [security model](../security/threat-model.md).
