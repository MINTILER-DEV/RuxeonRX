# Desktop alpha build and acceptance

The complete guest uses a checksum-pinned Debian 13 generic disk and a pinned
APT snapshot, with a conventional kernel, systemd, LightDM, Xorg, Openbox and
the RuxeonRX Tk shell. It contains the Python services and actual native app
payloads. The former BusyBox/framebuffer image is retained only as
`tools/rx-health-build`; its success is not desktop acceptance.

## Linux build host

Install host tools once (Debian/Ubuntu):

```sh
sudo apt-get install qemu-system-x86 qemu-utils xorriso openssh-client python3
./tools/rx-build bootstrap
./tools/rx-build build
./tools/rx-build test
./tools/rx-build run --vnc
```

`./tools/rx-build bundle` exports host build/test logs, screenshots and metadata
to `out/support.zip`, excluding disks and SSH keys. Guest support bundles are
exported separately from Diagnostics. Review screenshots/logs before sharing.
`clean` removes only regenerable source/seed staging files; it preserves disks,
keys and evidence. Run clean only while the builder/VM is stopped.

Building needs no host root: project provisioning runs as root inside the
isolated builder guest. The first download is approximately 416 MiB; allow
12 GiB of virtual disk capacity and at least 2 GiB of guest RAM. TCG is the
default and runs without KVM; `--accel kvm` can be used with KVM access.
The guest's APT package versions are captured at `/etc/ruxeonrx/packages.lock`.
The pinned inputs and artifact SHA-256 are recorded in `out/desktop/artifact.json`.
Disk timestamps, SSH keys and filesystem identifiers vary; reproducibility
means locked input versions, not identical disk bytes.

Existing disks are never overwritten by build. `build --refresh` explicitly
updates the development guest's project files and package configuration while
preserving user state. Run it only when the VM is stopped. Acceptance creates
its own overlay; archive `out/desktop/acceptance.qcow2` before rerunning.
After a successful full build, `build --refresh --code-only` redeploys project
code without rerunning APT. Changes to OS dependencies require a full refresh.
Code-only refresh also runs on Windows with Python/QEMU/OpenSSH, the original
artifact manifest and that image's private development builder key. Keep the
key local; ordinary testers only need the disk and Windows launcher.

## Windows

Copy the single disk to `out/desktop/ruxeonrx-0.5.qcow2`, then run:

```powershell
.\tools\run-windows.ps1
```

The graphical session appears directly in the QEMU window. `-SafeMode` requests
the recovery session. `-Acceleration whpx` is optional where Windows Hypervisor
Platform is enabled. The Windows launcher does not expose guest SSH ports.
If your PowerShell policy blocks scripts, launch with a process-scoped override:
`powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run-windows.ps1`.

## Acceptance evidence

`test` boots a disposable overlay three times. It requires an actual visible Tk
desktop and native application, sends keyboard/mouse input through X11, denies
then allows file and notification requests through visible permission dialogs
and the actual file picker, checks file-open intents and a regular native app,
updates/repairs/rolls back an executable package, writes recovery/diagnostic
artifacts, reboots, verifies version/permission/settings persistence, relaunches
the app, verifies uninstall cleanup and exact restore, kills real services to
check supervised recovery, and boots into safe mode with corrupted saved state
before restoring the known-good snapshot. Screenshots/logs are retained on
failure. The host integration suite additionally verifies executable output,
tamper rejection/repair, checksummed source downloads, portal authorization,
snapshot traversal rejection and exact restoration.
Acceptance records the actual disk SHA-256 and guest build revision and starts
with `passed: false`, so a failed rerun cannot leave a stale success result.

## Tester checklist

1. Install RX Notes, search it, launch it, and move/resize its window.
2. Open a UTF-8 file through the permission prompt and file picker; also deny it.
3. Deny then allow a notification and inspect the Permissions tab.
4. Apply the sample update, repair it, roll back, and inspect logs/storage.
5. Change contrast/text size and navigate with Tab, Enter and Ctrl+F.
6. Create a snapshot, change app state, restore it, and export a support bundle.
7. Shut down/restart, verify persistence, then remove an app and verify cleanup.

Report observed and expected behavior using the alpha feedback issue template,
including the image revision and a reviewed support bundle. External tester
feedback is a release gate; automated tests cannot manufacture that feedback.
