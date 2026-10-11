# RX 1.0 verification

## Status

Windows and Linux graphical acceptance passed all three phases: initial,
resume and safe, each on a fresh disposable overlay with real clean shutdowns.
This completes local native-desktop beta acceptance, not physical hardware,
production multiuser installation, external feedback or external CI certification.
The previous 0.5 verification is not evidence for the new GNOME desktop.

## Executed source checks

Source revision `f0a50e5b` (2026-10-11):

- Linux: 29 unit tests and 16 integration tests passed, no skips.
- Windows: 29 unit tests and 10 integration tests passed; six Unix-only tests
  were explicitly skipped, not counted as Windows passes.
- Windows and Linux Python compilation of build/services/shell/SDK/tests/tools passed.

The runtime includes managed-process retirement and obsolete portal-token
revocation after update, repair and rollback. Later commits correct acceptance
tooling and add regression tests; the image revisions below contain equivalent
runtime code. Each `acceptance.json` records the independent test revision and
SHA-256 hashes of the scripts frozen and deployed into its disposable overlay.

## Images under test

Both images contain Debian 13 snapshot-pinned dependencies, GNOME 48 on Xorg,
GDM, GTK 4/libadwaita and Dash to Panel. Baseline is BIOS x86_64, TCG, 3 GiB RAM,
two virtual CPUs, standard VGA, VirtIO storage and user-mode NAT.

| Host | Base disk SHA-256 |
| --- | --- |
| Linux QEMU 8.2.2 | `ca271b3302e027eb8dd560aa5e71033c1152760abd64a0b020503714ac07d8ed` |
| Windows QEMU 11.1.1 | `5997ddb2ac07dee78db83b5d90aecf63c3c67347fd5833055bd47cce7d3a534c` |

Different hashes are expected: these are independently refreshed development
disks, not byte-identical exports. Windows image revision is
`e834c05680d0606e8da5cc34f32d3d170159eb6e`; Linux image revision is
`77864264b2e649b724e2f07cd6b6231aa2170e92`. Differences after the Windows
revision are acceptance scripts and regression fixtures, not runtime changes. Generated
disks, logs, screenshots and private builder keys remain ignored under
`out/desktop/`; never publish the private key with an image.

## Observations and remaining checks

Both clean-overlay reports have `passed: true` and completed
`initial`, `resume`, `safe`. Windows used test revision
`8c23c66a993c6d564f84d2471acbf987ea8563c6`; Linux used
`f0a50e5bdf98cc52b0bbd3b930d3eee83d3c5c9c`, including the native-chooser
search/navigation correction. Both exercised GDM autologin,
the bottom taskbar, actual native Notes/Files/Console/Text Editor/Firefox/Settings
windows, minimize/restore and closed-window taskbar reopening, hidden permission
brokering, notification/file denial and approval, the actual file picker and
private saved notes. It also verified update/rollback/repair and stopped-old-app
relaunch, pins, 1.25 text scaling/high contrast, snapshots, support export,
reboot/persistence/removal, supervised service restart and corrupt-state safe
recovery through real GTK Restore/Continue controls.

Linux focused checks additionally opened the expected file after chooser search
input; the subsequent fresh full run also passed the exact file-grant/content
assertions. Both hosts retain `acceptance.json`,
`default-desktop.png`, per-phase `*-acceptance.log`, `*-guest.log`,
`*-serial.log`, `*-qemu.log` and `*-desktop.png` in ignored `out/desktop/`.
Earlier failed runs are archived without overwriting their reports or disks.
Historical overlays depend on their original backing image and must not be
booted against a subsequently refreshed base; their saved reports remain history.
Every successful acceptance phase requires actual guest poweroff, not forced
termination. Cold software-rendered GNOME initialization takes several minutes;
readiness markers alone do not establish a usable desktop.

Windows screenshots were inspected: the default desktop renders modern dark
RX Apps and the bottom taskbar; the updated native Notes shows the opened
document with scaled/high-contrast controls; the recovery screenshot shows the
named snapshot and completed restore. The resume screenshot shows the desktop
and taskbar, not additional visual proof of app-window contents.

Linux screenshots were also inspected: default RX Apps and the bottom taskbar
render correctly, the initial capture shows scaled/high-contrast RX Apps,
the resume capture shows the taskbar and a native notification, and safe recovery
shows the named snapshot and completed restore. Its initial screenshot still
contains an asynchronously stale 0.1.0 row; use the actual package/relaunch and
subsequent reboot assertions for version evidence, not that captured row.

Frozen script SHA-256 values:

| Script | Windows | Linux |
| --- | --- | --- |
| `guest_beta.py` | `89ebaa8ca78eb13cce76614e288bef609822e80898329fe3c5b781f77eb22e10` | `f7e5104b6ece397a6eea9b4836e10c7f7c88ffbdaff1584e5c705205a963c7f8` |
| `guest_desktop.py` | `6534f0588de626d406a42c09c1041a61ce3de36b30b29f2e4d2238fe19f9ce59` | `6534f0588de626d406a42c09c1041a61ce3de36b30b29f2e4d2238fe19f9ce59` |

Physical GPU/network/audio/Bluetooth/printer/firmware support, Wayland,
UEFI/KVM/WHPX, interactive host sound playback, configured-password lock/unlock,
external tester feedback and an external CI run are not certified by these
local checks. The development image autologins with locking disabled; it is not
a production multiuser installer or an X11 hostile-app security boundary.
