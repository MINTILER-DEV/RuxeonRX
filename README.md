# RuxeonRX

RuxeonRX is a compatibility-first Linux desktop platform.  It presents native
Linux, Windows, Android, web, and virtual-machine applications through one
launcher, permissions model, and application manager.

This repository implements the RX 0.2 desktop spine on top of its Stage 0
foundation:

- `tools/rx-build` builds and smoke-tests a bootable, serial-console Linux
  proof image on a Linux host;
- the boot image starts a minimal framebuffer `rx-shell` session;
- `rx-appd` is the only writer of normalized app registry records;
- `rx-portald` persists explicit capability decisions;
- the App Manager exposes install, launch, inspect, diagnostics, and removal;
- the notification center is permission mediated; and
- native-app integration tests exercise install, discover, launch, deny/allow,
  notification, diagnostics, and cleanup end to end.

## Quick start (Linux build server)

Read [the development guide](docs/development/quickstart.md), then run:

```sh
./tools/rx-build bootstrap
./tools/rx-build build
./tools/rx-build test
python3 -m unittest discover -s tests/unit -v
```

The QEMU image is an early serial-console health image, not yet a desktop ISO.
It emits `RX_HEALTH=ok` only after its embedded manifest has been read.

## Layout

The implementation follows the repository shape described in the roadmap.
Generated artifacts are written to `out/` and are never committed.  Public
contracts live under `sdk/spec/`; architecture choices are recorded in
`docs/architecture/adr/`.
