# RuxeonRX

RuxeonRX is a compatibility-first Linux desktop platform.  It presents native
Linux, Windows, Android, web, and virtual-machine applications through one
launcher, permissions model, and application manager.

This repository implements the RX 0.5 usable alpha, including the RX 0.2
desktop spine and RX 0.3 native-app experience:

- `tools/rx-build` builds and smoke-tests a bootable, serial-console Linux
  proof image on a Linux host;
- the boot image starts a minimal framebuffer `rx-shell` session;
- `rx-appd` is the only writer of normalized app registry records;
- `rx-portald` persists explicit capability decisions;
- the App Manager exposes install, launch, inspect, diagnostics, and removal;
- the notification center is permission mediated; and
- native-app integration tests exercise install, discover, launch, deny/allow,
  notification, diagnostics, and cleanup end to end.
- RX 0.3 adds explicit sources, transactional update/rollback/repair, package
  checksum caching, MIME/protocol defaults, per-file grants, storage reporting,
  and removal cleanup.
- RX 0.4 adds supervised services, crash-triggered safe mode, validated
  accessibility/privacy settings, and device diagnostics.
- RX 0.5 adds persistent QEMU state, recovery snapshots, a build doctor, and
  privacy-scrubbed support bundles for external alpha testing.

## Quick start (Linux build server)

Read [the development guide](docs/development/quickstart.md), then run:

```sh
./tools/rx-build bootstrap
./tools/rx-build build
./tools/rx-build test
python3 -m unittest discover -s tests/unit -v
```

The QEMU image is an early framebuffer desktop alpha, not yet an installable
hardware ISO. It emits `RX_HEALTH=ok` only after the session and native-app
smoke flow succeed.

## Layout

The implementation follows the repository shape described in the roadmap.
Generated artifacts are written to `out/` and are never committed.  Public
contracts live under `sdk/spec/`; architecture choices are recorded in
`docs/architecture/adr/`.
