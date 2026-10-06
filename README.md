# RuxeonRX

RuxeonRX is a compatibility-first Linux desktop platform.  It presents native
Linux, Windows, Android, web, and virtual-machine applications through one
launcher, permissions model, and application manager.

This initial repository implements the Stage 0 foundation and a deliberately
small Stage 1 vertical slice:

- `tools/rx-build` builds and smoke-tests a bootable, serial-console Linux
  proof image on a Linux host;
- `rx-appd` is the only writer of normalized app registry records;
- `rx-portald` persists explicit file and notification decisions; and
- the sample native app exercises register, discover, grant, log, and
  uninstall behaviour end to end.

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
