# Local IPC version 1

The desktop controller connects to `$RX_RUNTIME/appd.sock`, mode 0600.
Applications connect only to `$RX_PORTAL_DIR/portal.sock` and present the random
`RX_TOKEN` provided at launch. Both use one JSON line request/response per Unix
socket connection, UTF-8, at most 1 MiB request size.

Request: `{"version":1,"method":"apps","params":{"query":"notes"}}`.
Success: `{"ok":true,"result":[]}`. Failure:
`{"ok":false,"error":"human-readable reason"}`.

Controller methods: apps, install, update, repair, rollback, inspect, import,
remove, launch, pin, reset-data, decide, pending, answer, settings, set, notifications, devices,
defaults, default, open-with, sources, source, catalog, source-install, updates, snapshot,
snapshots, restore, bundle, health. The app endpoint supports only request,
intents and
result; tokens are bound to installed apps and revoked when the process exits.
`request` declares files/notifications and returns a request ID. `result` returns
pending status or the user-approved result. Permission decisions and file-picker
selection happen in the desktop controller, never in the app endpoint.

`intents` returns request IDs for desktop file/link-open actions addressed to
this app. Use `result` to consume each completed response exactly once.
Controller `launch` accepts an optional `path`; `open-with` takes `handler`
and optional `path`. Local files and file URIs still require consent and file
selection. Declared protocol URIs are delivered as text intents, not executed
as commands. The RX Notes sample implements all three app methods.
