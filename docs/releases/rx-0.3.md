# RX 0.3: Native app management

RX 0.3 completes the native-app policy loop introduced by RX 0.2. It is a
deterministic reference implementation intended to become the backing contract
for the graphical App Manager.

## Included behaviour

- Native manifests are cached with SHA-256 records on installation.
- Package sources are explicitly recorded; adding a source does not silently
  download or execute content.
- Updates validate a candidate before registry replacement and retain a
  rollback snapshot.
- Repair restores the cached manifest only when its checksum matches.
- Removing an app clears its portal decisions, file grants, notifications, and
  default file/protocol handlers. `--purge-data` also removes diagnostics.
- The permission center lists decisions by installed app. File grants require
  an allowed `files` capability and are explicit absolute paths.
- App inspection reports package metadata, diagnostics, grants, permissions,
  and managed storage usage.

## Acceptance checks

Run both suites on the Linux server:

```sh
python3 -m unittest discover -s tests/unit -v
python3 -m unittest discover -s tests/integration -v
```

The RX 0.3 integration suite proves install, source registration, permission
grant, MIME default, update, launch, repair, rollback, removal cleanup, and an
invalid update that leaves the prior version intact.
