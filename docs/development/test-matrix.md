# RX 1.0 support and test matrix

| Dimension | Native desktop beta baseline | Required evidence |
| --- | --- | --- |
| CPU | x86_64 host and guest | QEMU generic x86_64 disk |
| Host | Linux build; Windows/Linux QEMU run | portable disk, launcher |
| Acceleration | TCG baseline; KVM/WHPX optional | TCG acceptance required |
| Firmware | BIOS default; UEFI with compatible OVMF | BIOS acceptance required |
| Graphics | QEMU standard VGA with Debian bochs/modesetting | real window and screenshot acceptance |
| Desktop | GNOME 48, Xorg, bottom taskbar, GTK 4/libadwaita | taskbar launch/switch and actual widget tests |
| Memory | 3 GiB guest RAM, 2 virtual CPU cores | TCG baseline |
| Audio | Emulated Intel HDA; Windows DirectSound / Linux PulseAudio | guest inventory; physical audio not certified |
| Runtime | Curated native `.rxpkg`, reviewed `.desktop` import | executable and portal tests |
| Network | QEMU user NAT | build and source download |
| Storage | Persistent ext4 guest root on VirtIO | second-boot acceptance |
| Hardware installation | Outside current QEMU beta scope | no hardware ISO/installer claim |

The QEMU beta exposes file and notification portals and sandbox launch-time
network policy. Unsupported camera/audio/etc. controls are disabled. Native
desktop imports show unrestricted status. X11 permits clients
to observe/interact with each other: Bubblewrap protects private app/service
files and network namespaces, but X11 is not a hostile-app display boundary.
Wayland and broader portal enforcement belong to subsequent hardening.

NetworkManager, PipeWire, printer, Bluetooth and firmware utilities provide
native system controls and report unavailable devices honestly. Emulation does
not certify physical Wi-Fi, Bluetooth, printers, GPU drivers or firmware updates.
UEFI/KVM/WHPX remain optional and unverified until their own results are recorded.
See release verification documents for observed results rather than interpreting
this matrix as proof that every optional configuration has passed.
