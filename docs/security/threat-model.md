# RX 1.0 native desktop beta threat model

The beta assumes the desktop user intentionally trusts installed native
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

The X11 desktop is not a hostile-application security boundary: clients can
observe input and interact with other windows. RX 1.0 does not claim clipboard,
camera, microphone or screen-capture isolation. Unsupported permission controls
are explicitly disabled. Network changes require a sandboxed app restart;
file consent mediates brokered reads, not unrestricted system applications.
GNOME settings control trusted base services; native imports run with full user
access. Android, Wine/Windows and VM-backed app runtimes belong to later roadmap
milestones and are not advertised as available in this release.

The development image retains its unique builder SSH public key so automated
acceptance can inspect the guest. Its private key stays under ignored `out/`
and is never bundled with screenshots or support archives. Test SSH forwarding
binds only to host loopback; the Windows run command exposes no SSH forwarding.
Do not redistribute private builder keys or assume this development image is a
production-hardened distribution. Review support bundles before sharing them.

This QEMU development guest autologins the `rx` account without a configured
login password. Automatic idle locking is disabled to avoid an un-unlockable
session. The image builder/root console must run `passwd rx` to configure the
initial password before enabling screen locking; the Users panel alone cannot
authenticate a locked, passwordless account. Do not treat autologin as suitable
physical-device authentication. This developer guest is not a multi-user
installation or a production account-provisioning flow.
