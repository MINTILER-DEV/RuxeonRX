# ADR 0005: RX 1.0 native desktop beta

The roadmap defines 1.0 as a coherent Linux app experience with documented
hardware scope. Android/PWA integration remains 2.0, Windows translation 3.0,
managed VM fallback 4.0, and platform maturity 5.0; their completion is not
implied by renaming the desktop to 1.0.

Use the pinned Debian 13 GNOME 48 desktop, its compositor/window management,
and the packaged Dash to Panel extension for a permanent bottom taskbar with
pinned apps, running windows, app grid, clock and system controls. RX apps use
GTK 4/libadwaita and retain the existing versioned appd/portal contract.
The tested baseline remains an x86_64 QEMU Xorg session with software rendering;
Wayland/physical GPU support requires separate acceptance, not an assumed claim.

The beta includes Files, Terminal, a text editor, a browser, working GNOME
network/audio/display/keyboard settings, real desktop notifications, native
package/source/default-handler management, permission enforcement status,
snapshots/recovery, and richer driver/renderer/service diagnostics. Core native
desktop apps are explicitly trusted and unrestricted; imported apps never gain
a misleading sandbox badge. Permission controls distinguish implemented portal
and launch-time policy from capabilities that are not mediated yet.

The old alpha is preserved as a separate disk. Safe mode retains a minimal
window manager so recovery does not depend on GNOME or its extensions working.
Acceptance must exercise actual taskbar/window switching, GTK permission/file
dialogs, installation/update/recovery, reboot and corrupt-state safe boot.
External tester feedback and physical-device support require recorded human
evidence. CI and automated QEMU tests cannot manufacture those release gates.
