# Development quick start

Run these commands on the Linux build server, not on the Windows control
laptop.  The scripts never require root after dependencies are installed.

## Prerequisites

Install a static BusyBox, QEMU x86 system emulator, a Linux kernel that the
build user can read, GNU cpio, gzip, and Python 3.  On Debian-family hosts:

```sh
sudo apt-get update
sudo apt-get install --yes build-essential busybox-static qemu-system-x86 cpio gzip python3 debootstrap
```

`debootstrap` is pinned by the host's configured Debian stable repository and
is reserved for the next rootfs-composition step.  The image uses no network
downloads during its build and compiles a small static framebuffer shell.

Some distributions protect `/boot/vmlinuz-*` from non-root accounts.  Make a
read-only build copy once, then select it explicitly:

```sh
sudo install -D -m 0644 /boot/vmlinuz-"$(uname -r)" "$HOME/.cache/ruxeonrx/vmlinuz"
export RX_KERNEL_IMAGE="$HOME/.cache/ruxeonrx/vmlinuz"
```

## Build and test

```sh
./tools/rx-build bootstrap  # checks prerequisites; does not install packages
./tools/rx-build build
./tools/rx-build run        # interactive serial console
./tools/rx-build test       # non-interactive QEMU health check
./tools/rx-build bundle     # scrubbed diagnostic archive in out/
```

Set `RX_NO_KVM=1` when hardware virtualization is unavailable.  Artifacts and
logs live under `out/`; `./tools/rx-build clean` removes only that directory.

`run` exposes the framebuffer session over VNC on the Linux server's loopback
port 5901. From Windows, use a second PowerShell window to forward it:

```powershell
ssh -L 5901:127.0.0.1:5901 mntweb@192.168.1.101
```

Then open `localhost:5901` in a VNC viewer. The serial terminal provides the
early session commands, including `rx-demo install`, `rx-demo decide allow`,
`rx-demo launch`, and `rx-demo remove`.

## Native-app vertical slice

```sh
python3 -m unittest discover -s tests/unit -v
python3 -m unittest discover -s tests/integration -v
```

The test creates temporary state, registers the sample manifest, grants a file
and notification capability, verifies launcher discovery and diagnostic logs,
then removes the app and confirms no stale record remains.

## RX 0.2 desktop-spine demonstration

`rxctl` is the command interface used by the early session shell and its tests.
It makes the complete native lifecycle inspectable before the graphical App
Manager gains its final UI toolkit:

```sh
state="$(mktemp -d)"
./tools/rxctl --state "$state" install packages/native-test-app/manifest.json
./tools/rxctl --state "$state" apps --query native
./tools/rxctl --state "$state" decide org.ruxeonrx.native-test-app notifications allow
./tools/rxctl --state "$state" launch org.ruxeonrx.native-test-app
./tools/rxctl --state "$state" inspect org.ruxeonrx.native-test-app
./tools/rxctl --state "$state" remove org.ruxeonrx.native-test-app --purge-data
```
