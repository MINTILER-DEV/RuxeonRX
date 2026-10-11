# RX 1.0 desktop development

RX 1.0 uses the roadmap's native desktop beta scope. Read
[the release scope](../releases/rx-1.0.md) before interpreting compatibility
or hardware claims. The GNOME desktop/taskbar is not a replacement kernel.

## Build host

```sh
sudo apt-get install qemu-system-x86 qemu-utils xorriso openssh-client python3
./tools/rx-build bootstrap
./tools/rx-build build
./tools/rx-build test
```

Provisioning runs inside an isolated guest without host root. Inputs come from
the checksum-pinned Debian base and APT snapshot in `build/base.lock.json`.
Allow 12 GiB virtual disk capacity, 3 GiB guest RAM and several GiB of actual
free storage for the desktop, test overlays and the preserved old alpha disk.
The first desktop dependency download is larger than the old minimal alpha.

The disk is `out/desktop/ruxeonrx-1.0.qcow2`. Build refuses to overwrite an
existing disk. `build --refresh` explicitly updates the development image;
run it only when that VM is stopped. This preserves managed user state, but
updates image-owned session configuration. `--refresh --code-only` skips APT
and is valid only after a complete desktop dependency install. A changed base
lock requires a full rebuild. Package versions, source revision and disk hash
are recorded in `/etc/ruxeonrx/` and `out/desktop/artifact.json`.

## Run

```sh
./tools/rx-build run --vnc
```

VNC binds to host loopback port 5901. From Windows:

```powershell
ssh -L 5901:127.0.0.1:5901 mntweb@192.168.1.101
```

Connect a VNC viewer to `localhost:5901`. Alternatively, copy the self-contained
1.0 disk to this repository's `out/desktop/` and run locally:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run-windows.ps1
```

The local Windows GUI does not need the server. DirectSound is the default
host audio backend; `-Audio none` disables it. `-SafeMode` selects minimal
recovery independent of the GNOME taskbar extension. Host microphone capture is
off by default; `-Microphone` (or `--microphone` with the Python runner) explicitly
enables that bridge. TCG is the tested baseline;
WHPX/KVM need separate validation. Use the desktop power controls to shut down
cleanly, rather than killing QEMU while it writes the disk.

## Acceptance and evidence

Acceptance uses a disposable overlay and three real boots: initial desktop,
reboot persistence/crash recovery, and corrupt-state safe-mode restore. It
uses X11 input and AT-SPI controls to operate actual GNOME/GTK windows and
taskbar items. Screenshots and serial logs are preserved on failures, and the
report starts with `passed: false` to avoid stale success. Archive the exact
`out/desktop/acceptance.qcow2` before rerunning; do not delete user disks.

`./tools/rx-build bundle` exports host evidence without disks/private keys.
Review screenshots/logs before sharing. Guest recovery snapshots cover
RX-managed state, not whole-disk/OS rollback. Existing 0.5 disks are preserved;
their data is not silently copied into a separate 1.0 guest.
