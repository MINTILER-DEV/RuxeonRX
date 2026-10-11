# Local IPC version 1

The desktop controller connects to `$RX_RUNTIME/appd.sock`, mode 0600.
Applications connect only to `$RX_PORTAL_DIR/portal.sock` and present the random
`RX_TOKEN` provided at launch. Both use one JSON line request/response per Unix
socket connection, UTF-8, at most 1 MiB request size.
Responses are limited to 8 MiB: JSON escaping can expand a brokered 1 MiB
Unicode file beyond the previous 2 MiB reader limit. Incomplete or oversized
responses are rejected explicitly.

Request: `{"version":1,"method":"apps","params":{"query":"notes"}}`.
Success: `{"ok":true,"result":[]}`. Failure:
`{"ok":false,"error":"human-readable reason"}`.

Controller methods: apps, install, update, repair, rollback, inspect, import,
remove, launch, pin, reset-data, decide, pending, answer, settings, set, notifications, devices,
defaults, default, open-with, sources, source, catalog, source-install, updates, snapshot,
snapshots, restore, bundle, health. The app endpoint supports only request,
intents, appearance and result; tokens are bound to installed apps and revoked
when the process exits. `appearance` exposes only the public `color_scheme`
preference; it cannot read private settings or authorize capabilities.
`request` declares files/notifications and returns a request ID. `result` returns
pending status or the user-approved result. Permission decisions and file-picker
selection happen in the desktop controller, never in the app endpoint.

`intents` returns request IDs for desktop file/link-open actions addressed to
this app. Use `result` to consume each completed response exactly once.
Controller `launch` accepts an optional `path`; `open-with` takes `handler`
and optional `path`. For sandboxed RX packages, local files and file URIs require consent and file
selection. Declared protocol URIs are delivered as text intents, not executed
as commands. The GTK 4 RX Notes sample implements all four app methods and
persists documents under its private `RX_DATA_DIR` directory. Trusted native
desktop imports receive file/link intents as an argv argument, never a shell
command; they are unrestricted and do not pretend to require RX file mediation.
Notification records include a unique `id`, so identical repeated messages are
separate events. The Python controller client has a 60-second timeout to allow
hardware diagnostics to complete; UI calls execute off the GTK main thread.
