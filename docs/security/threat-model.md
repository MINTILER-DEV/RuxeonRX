# RX 0.5 threat model

The alpha assumes the desktop user intentionally trusts installed native
software and software sources. It guards against corrupted packages, accidental
state loss, path traversal in packages/snapshots, unauthorized portal methods,
and app requests for undeclared capabilities. Package extraction is size-limited;
launch verifies payload hashes; update/rollback commits use one atomic registry
record with history; a single local daemon serializes mutations. App-facing
requests use short-lived random tokens on a separate restricted socket.

Sandboxed Notes receives read-only runtime/package files, an app-specific data
directory, an isolated network namespace and the portal socket. It receives
selected file content via the broker. Imported system apps are unrestricted and
are labeled accordingly. No unsigned-source trust is inferred from a checksum:
the user must trust the source catalog. Remote sources require HTTPS.

The development image retains its unique builder SSH public key so automated
acceptance can inspect the guest. Its private key stays under ignored `out/`
and is never bundled with screenshots or support archives. Test SSH forwarding
binds only to host loopback; the Windows run command exposes no SSH forwarding.
Do not redistribute private builder keys or assume this development image is a
production-hardened distribution. Review support bundles before sharing them.
