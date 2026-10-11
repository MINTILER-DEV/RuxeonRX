# RX 1.0 verification

## Status

Graphical acceptance is in progress. This record does not certify a completed
1.0 release until both host runs have passed initial, resume and safe phases.
The previous 0.5 verification is not evidence for the new GNOME desktop.

## Executed source checks

Source revision `09fbaebd883b0c7d0277d725c2938ecdb9967e8f`:

- Linux: 22 unit tests and 15 integration tests passed, no skips.
- Windows: 22 unit tests and 10 integration tests passed; five Unix-only tests
  were explicitly skipped, not counted as Windows passes.
- Windows Python compilation of build/services/shell/SDK/tests/tools passed.

Subsequent commits correct and preserve graphical acceptance tooling only;
the OS runtime under test remains the revision above. Each `acceptance.json`
records its separate test revision and SHA-256 hashes of the deployed scripts.

## Images under test

Both images contain Debian 13 snapshot-pinned dependencies, GNOME 48 on Xorg,
GDM, GTK 4/libadwaita and Dash to Panel. Baseline is BIOS x86_64, TCG, 3 GiB RAM,
two virtual CPUs, standard VGA, VirtIO storage and user-mode NAT.

| Host | Base disk SHA-256 |
| --- | --- |
| Linux QEMU 8.2.2 | `e48cd0b0db279d05806a3b08421fa8f5354b2a04df63142a7cc6a8108fae63a4` |
| Windows QEMU 11.1.1 | `22960ce6d586529ec6c9e06a3ff05853bef1fe2c05ddd4f72ce9641237c00094` |

Different hashes are expected: these are independently refreshed development
disks, not byte-identical exports. Runtime revision is identical. Generated
disks, logs, screenshots and private builder keys remain ignored under
`out/desktop/`; never publish the private key with an image.

## Observations and remaining checks

Observed: GDM autologin, rendered dark RX Apps and bottom taskbar; focused
Windows checks activated the real Notes and permission widgets, denied and
approved notification permission, delivered a notification, opened a real GTK
file picker, delivered selected file contents, and saved a private note.

Full clean-overlay acceptance remains required for both hosts: actual taskbar
launch/minimize/restore, all native windows, package update/rollback/repair,
persisted settings/private data, reboot/removal, service restart supervision,
and corrupt-state safe recovery. Reports must have `passed: true` and all three
completed phases. Cold software-rendered GNOME initialization takes several
minutes; readiness markers alone do not establish a usable desktop.

Physical GPU/network/audio/Bluetooth/printer/firmware support, Wayland,
UEFI/KVM/WHPX, interactive host sound playback, configured-password lock/unlock,
external tester feedback and an external CI run are not certified by these
local checks. The development image autologins with locking disabled; it is not
a production multiuser installer or an X11 hostile-app security boundary.
