# RX 0.5 support and test matrix

| Dimension | Supported alpha path | Evidence |
| --- | --- | --- |
| CPU | x86_64 host and guest | QEMU generic x86_64 disk |
| Host | Linux build; Windows/Linux QEMU run | portable disk, launcher |
| Acceleration | TCG baseline; KVM/WHPX optional | TCG acceptance required |
| Firmware | BIOS default; UEFI with compatible OVMF | BIOS acceptance required |
| Graphics | QEMU standard VGA with Debian bochs/modesetting | real window and screenshot acceptance |
| Runtime | Curated native `.rxpkg`, reviewed `.desktop` import | executable and portal tests |
| Network | QEMU user NAT | build and source download |
| Storage | Persistent ext4 guest root on VirtIO | second-boot acceptance |
| Hardware installation | Outside 0.5 alpha scope | no hardware ISO/installer claim |

The QEMU alpha exposes file and notification portals. Other declared capability
decisions are visible but are not advertised as complete camera/audio/etc.
portals. Native desktop imports show unrestricted status. X11 permits clients
to observe/interact with each other: Bubblewrap protects private app/service
files and network namespaces, but X11 is not a hostile-app display boundary.
Wayland and broader portal enforcement belong to subsequent hardening.
