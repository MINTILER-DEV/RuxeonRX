# RuxeonRX

RuxeonRX is a Linux desktop operating system project. RX 1.0 targets a native
x86_64 QEMU native desktop beta; later releases add web, Android and Windows runtimes.

The desktop disk contains a pinned Debian 13 base, Linux kernel, systemd,
GDM login, GNOME window management, a persistent bottom taskbar, modern GTK RX apps, and the app,
portal, notification, package, settings, recovery and diagnostic services.
RX Notes is a real native application installed from an executable package.

## Run on Windows

With the built disk at `out/desktop/ruxeonrx-1.0.qcow2` and QEMU on PATH:

```powershell
.\tools\run-windows.ps1
```

Open RX Apps from the taskbar to install RX Notes, search, launch, update,
repair, roll back and remove it. Its Open file and Send notification controls
request permission through the desktop. Settings, permissions, logs, software
sources, default handlers, recovery and support export are available in the UI.
The bottom taskbar provides pinned/running apps, app grid, clock and system
controls. Alt+Tab switches between windows, including minimized apps.
Ctrl+F searches, Ctrl+L launches the selection, and Ctrl+D opens its logs.

## Build and test on Linux

```sh
./tools/rx-build bootstrap
./tools/rx-build build
./tools/rx-build test
./tools/rx-build run --vnc
```

Read [the complete build/run guide](docs/development/desktop-beta.md),
[the native desktop beta scope](docs/releases/rx-1.0.md),
[the support matrix](docs/development/test-matrix.md), and
[the security model](docs/security/threat-model.md).
The [2026-10-10 verification record](docs/releases/verification-2026-10-10.md)
lists executed checks, the local Windows disk checksum and remaining release gates.

Desktop acceptance requires real windows and permission interaction, then
reboots the guest and verifies persistence. Logs and screenshots stay in
`out/desktop/`. Generated disks, caches and private keys are never committed.
The earlier BusyBox health image is archived as `tools/rx-health-build` and
is not the desktop release.

External tester feedback remains a release gate. The issue template includes
an explicit checklist for documenting that feedback.
