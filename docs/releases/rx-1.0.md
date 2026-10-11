# RX 1.0 native desktop beta

The roadmap's 1.0 goal is a coherent native Linux app experience and documented
hardware scope. This release adds GNOME, a permanent bottom taskbar, GTK 4 RX
Apps/Settings/Recovery interfaces, modern native Notes, Files, Terminal, Text
Editor and Firefox. GNOME owns window switching/workspaces, app-grid search,
system status, notifications and network/audio/display/input/printer settings.
RX retains app installation/update/repair/rollback, source trust and checksum
verification, permission records, default handlers, logs, private app data,
snapshots/recovery and diagnostics. Pins synchronize with GNOME's taskbar.

## Scope and safety

- Baseline: x86_64 QEMU, BIOS, standard VGA, VirtIO storage, user NAT, TCG,
  3 GiB guest RAM. Software rendering is a portability baseline, not a gaming
  benchmark or a claim of accelerated physical GPU performance.
- The normal session uses GNOME 48 on Xorg. Safe mode uses a minimal window
  manager and the GTK recovery app, independent of GNOME extensions.
- GNOME desktop applications are deliberately trusted/unrestricted. RX removal
  removes their registration, not the underlying Debian system package.
- Sandboxed RX packages use immutable code, private writable data, scoped RX
  file/notification portals and launch-time network namespaces. Capabilities
  without an implementation are explicitly marked unavailable; an enabled
  switch is not presented as enforcement of a capability RX cannot mediate.
- X11 is not hostile-app display/clipboard isolation. Wayland, physical-device
  support, GPU acceleration and broad hardware certification need their own
  tests. Bluetooth/printer/firmware tools report absent devices honestly.
- Core Debian package versions are snapshot-pinned. RX app updates do not
  update the entire base OS. Base dependency/security changes require a rebuilt
  image or an explicit developer full refresh; system-wide A/B updates are
  later hardening work, not hidden behind the app-update button.
- Android/PWAs remain roadmap 2.0, Windows translation 3.0 and VM fallback 4.0.
  No universal compatibility claim is made by the 1.0 desktop branding.

## Build and run

```sh
./tools/rx-build build
./tools/rx-build test
./tools/rx-build run --vnc
```

The new disk is `out/desktop/ruxeonrx-1.0.qcow2`. The existing 0.5 disk is not
overwritten. Full refresh installs changed OS dependencies; code-only refresh
is permitted only after provisioning all required desktop packages.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run-windows.ps1
```

Use `-SafeMode` for recovery and `-Audio none` if no host sound backend is
available. Headless acceptance disables host audio output but provides an
emulated guest audio device. Interactive Windows uses DirectSound by default.

## Required acceptance

Automated tests must exercise the actual bottom taskbar, GTK package UI,
native windows, file/notification permission denial/approval, real file picker,
private saved notes, update/rollback/repair, pins, persisted preferences,
reboot/removal, supervised service recovery and safe boot with corrupt state.
Keep serial logs, screenshots, build revision and actual disk hash. External
tester feedback, remote CI results and physical hardware observations must be
recorded separately; no automated test manufactures those human release gates.
