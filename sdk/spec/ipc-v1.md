# Local IPC version 1

The desktop controller connects to `$RX_RUNTIME/appd.sock`, mode 0600.
Applications connect only to `$RX_PORTAL_DIR/portal.sock` and present the random
`RX_TOKEN` provided at launch. Both use one JSON line request/response per Unix
socket connection, UTF-8, at most 1 MiB request size.

Request: `{"version":1,"method":"apps","params":{"query":"notes"}}`.
Success: `{"ok":true,"result":[]}`. Failure:
`{"ok":false,"error":"human-readable reason"}`.

Controller methods: apps, install, update, repair, rollback, inspect, import,
remove, launch, decide, pending, answer, settings, set, notifications, devices,
defaults, default, open-with, sources, source, catalog, source-install, updates, snapshot,
snapshots, restore, bundle, health. The app endpoint supports only request and
result; tokens are bound to installed apps and revoked when the process exits.
`request` declares files/notifications and returns a request ID. `result` returns
pending status or the user-approved result. Permission decisions and file-picker
selection happen in the desktop controller, never in the app endpoint.
