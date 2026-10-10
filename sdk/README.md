# Native app SDK (RX 0.5)

The public contracts are [the manifest schema](spec/app-manifest.schema.json),
[IPC version 1](spec/ipc-v1.md), and the synchronous Python
[client](bindings/python/rxipc.py). See [RX Notes](samples/desktop_app.py) for
a runnable GUI using asynchronous Tk polling around the portal client.

## Package an app

An `.rxpkg` is a ZIP with `manifest.json` at its root and actual payload files.
Start from `packages/native-test-app/manifest.json`, choose a unique reverse-DNS
ID, name and version, set `package_kind` to `portable`, and set launch to:

```json
{"command": ["python3", "{package}/main.py"]}
```

Add `"sandbox": true` and `"icon": "notes.svg"`. Include `main.py`, the
client as `rxipc.py`, and your icon. Declare only the permissions and MIME or
protocol handlers your app uses. Inside the directory containing those files:

```sh
python3 -m zipfile -c hello.rxpkg manifest.json main.py rxipc.py notes.svg
/opt/RuxeonRX/tools/rxctl install hello.rxpkg
/opt/RuxeonRX/tools/rxctl launch org.example.hello
```

The GUI also installs `.rxpkg` files. Change the version for an update;
same-version replacements are rejected. Installation validates the manifest,
archive paths, bounds and Python entry-point syntax before publishing the
registry record. Launch verifies payload hashes. Updates retain rollback
versions; repair rebuilds from a verified retained archive. Applications run
as the desktop user, never as root.

## Files, notifications and storage

At launch, `RX_APP_ID`, `RX_APP_NAME`, `RX_DATA_DIR`, `RX_TOKEN`, and
`RX_PORTAL_DIR` are supplied. Store private writable files in `RX_DATA_DIR`.
Use the portal socket for file/notification requests; never use the controller
socket to self-authorize. `request` returns an ID; poll `result` until no longer
pending. A file result contains selected UTF-8 text (at most 1 MiB), not arbitrary
filesystem access. `intents` receives desktop file/link-open request IDs. A
completed result is consumed once. Display errors and denials to the user.

Regular native packages may explicitly set `sandbox` to false and use the
same portal API. Imported `.desktop` applications are visibly unrestricted:
they retain ordinary Linux user access, irrespective of the portal preferences.
Read [the alpha security limitations](../docs/security/threat-model.md),
especially the X11 display trust boundary.

## Publish a trusted source

Serve an HTTPS catalog with `{"format":1,"packages":[...]}`. Each entry has
`id`, `version`, absolute `url`, and the package's hexadecimal SHA-256. Entries
for an app are ordered oldest to newest. Users explicitly add/trust the source
in Settings; downloading verifies its checksum and manifest identity/version.
Checksums detect byte changes; they do not establish publisher authenticity.
`tools/rx-package.py` produces the offline example catalog used by acceptance.
