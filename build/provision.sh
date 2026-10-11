#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
revision="$1"
snapshot="$2"
cat > /etc/apt/sources.list <<EOF
deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/$snapshot trixie main
EOF
rm -f /etc/apt/sources.list.d/debian.sources
if [[ "${RX_SKIP_APT:-0}" != 1 ]]; then
    apt-get update
    apt-get install -y --no-install-recommends dconf-cli dbus-user-session evolution-data-server ibus librsvg2-bin librsvg2-common
    apt-get install -y --no-install-recommends linux-image-amd64 xserver-xorg xserver-xorg-video-all lightdm openbox python3 python3-tk python3-jsonschema python3-gi python3-pyatspi gir1.2-gtk-4.0 gir1.2-adw-1 bubblewrap dbus-x11 xterm fonts-dejavu-core fonts-cantarell xdotool scrot x11-utils x11-xserver-utils xinput e2fsprogs sudo gnome-session gnome-session-xsession gnome-shell gnome-shell-extension-dash-to-panel gnome-control-center gnome-console gnome-text-editor nautilus firefox-esr adwaita-icon-theme libgl1-mesa-dri mesa-utils pipewire-audio wireplumber network-manager network-manager-gnome bluez cups system-config-printer fwupd xdg-desktop-portal-gnome gnome-keyring libpam-gnome-keyring at-spi2-core
fi
id rx >/dev/null 2>&1 || useradd -m -s /bin/bash rx
install -d -m 0700 -o rx -g rx /home/rx/.local /home/rx/.local/state /home/rx/.local/share /home/rx/.local/share/applications /home/rx/.local/state/ruxeonrx /home/rx/.config /home/rx/.config/openbox
if [[ ! -f /home/rx/.config/openbox/menu.xml ]]; then
    install -m 0600 -o rx -g rx /opt/RuxeonRX/build/desktop-menu.xml /home/rx/.config/openbox/menu.xml
fi
python3 - <<'PY'
from pathlib import Path
path = Path('/home/rx/.config/openbox/menu.xml')
old = 'xdotool search --name "^RuxeonRX Desktop$" windowmap windowactivate'
content = path.read_text()
if old in content:
    path.write_text(content.replace(old, 'python3 /opt/RuxeonRX/shell/modern.py --page recovery'))
PY
install -d /usr/share/xsessions /etc/lightdm/lightdm.conf.d /etc/ruxeonrx
cat > /usr/share/xsessions/ruxeonrx.desktop <<EOF
[Desktop Entry]
Name=RuxeonRX
Exec=env XDG_CURRENT_DESKTOP=GNOME /opt/RuxeonRX/tools/rx-session
Type=Application
EOF
cat > /etc/lightdm/lightdm.conf.d/50-ruxeonrx.conf <<EOF
[Seat:*]
autologin-user=rx
autologin-user-timeout=0
user-session=ruxeonrx
EOF
chmod +x /opt/RuxeonRX/tools/rxctl /opt/RuxeonRX/tools/rx-session /opt/RuxeonRX/tools/rx-services
printf 'rx ALL=(root) NOPASSWD: /sbin/poweroff, /sbin/reboot\n' > /etc/sudoers.d/ruxeonrx-power
chmod 0440 /etc/sudoers.d/ruxeonrx-power
python3 /opt/RuxeonRX/tools/rx-package.py
printf '{"version":"1.0.0-beta","revision":"%s","architecture":"x86_64","base":"Debian 13","desktop":"GNOME"}\n' "$revision" > /etc/ruxeonrx/build.json
cat > /etc/os-release <<EOF
PRETTY_NAME="RuxeonRX 1.0 Beta (Debian 13)"
NAME=RuxeonRX
ID=ruxeonrx
ID_LIKE=debian
VERSION_ID=1.0
LOGO=ruxeonrx
EOF
install -d /usr/share/icons/hicolor/scalable/apps /etc/default/grub.d
install -m 0644 /opt/RuxeonRX/shell/assets/ruxeonrx.svg /usr/share/icons/hicolor/scalable/apps/ruxeonrx.svg
printf 'GRUB_DISTRIBUTOR=RuxeonRX\n' > /etc/default/grub.d/99-ruxeonrx.cfg
if command -v update-grub >/dev/null; then update-grub; fi
systemctl set-default graphical.target
systemctl enable lightdm
install -d /etc/systemd/system/lightdm.service.d
printf '[Service]\nExecStartPre=/usr/bin/python3 /opt/RuxeonRX/tools/rx-boot.py\n' > /etc/systemd/system/lightdm.service.d/ruxeonrx.conf
systemctl daemon-reload
install -d /etc/xdg/autostart /etc/dconf/profile /etc/dconf/db/local.d /usr/share/backgrounds/ruxeonrx
install -m 0644 /opt/RuxeonRX/shell/assets/wallpaper.svg /usr/share/backgrounds/ruxeonrx/wallpaper.svg
rsvg-convert /usr/share/backgrounds/ruxeonrx/wallpaper.svg -o /usr/share/backgrounds/ruxeonrx/wallpaper.png
printf 'user-db:user\nsystem-db:local\n' > /etc/dconf/profile/user
cat > /etc/dconf/db/local.d/00-ruxeonrx <<'EOF'
[org/gnome/desktop/background]
picture-uri='file:///usr/share/backgrounds/ruxeonrx/wallpaper.png'
picture-uri-dark='file:///usr/share/backgrounds/ruxeonrx/wallpaper.png'
picture-options='zoom'
[org/gnome/desktop/interface]
color-scheme='prefer-dark'
clock-show-weekday=true
toolkit-accessibility=true
[org/gnome/desktop/screensaver]
lock-enabled=false
[org/gnome/desktop/session]
idle-delay=uint32 0
[org/gnome/desktop/wm/preferences]
button-layout='appmenu:minimize,maximize,close'
[org/gnome/shell]
enabled-extensions=['dash-to-panel@jderose9.github.com']
favorite-apps=['org.ruxeonrx.Apps.desktop','org.gnome.Nautilus.desktop','org.gnome.Console.desktop','firefox-esr.desktop','org.ruxeonrx.Settings.desktop','org.ruxeonrx.Recovery.desktop']
[org/gnome/shell/extensions/dash-to-panel]
panel-position='BOTTOM'
panel-size=52
panel-positions='{"0":"BOTTOM"}'
panel-sizes='{"0":52}'
intellihide=false
hide-overview-on-startup=true
show-apps-icon=true
show-favorites=true
show-running-apps=true
trans-use-custom-bg=true
trans-bg-color='#111827'
trans-use-custom-opacity=true
trans-panel-opacity=0.95
EOF
python3 - <<'PY'
import json
from pathlib import Path
metadata = Path('/usr/share/gnome-shell/extensions/dash-to-panel@jderose9.github.com/metadata.json')
with Path('/etc/dconf/db/local.d/00-ruxeonrx').open('a') as defaults:
    defaults.write('extension-version=' + str(int(json.loads(metadata.read_text())['version'])) + '\n')
PY
dconf update
cat > /etc/xdg/autostart/ruxeonrx-services.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=RuxeonRX Services
Exec=/opt/RuxeonRX/tools/rx-services
OnlyShowIn=GNOME;
X-GNOME-Autostart-enabled=true
EOF
for page in Apps Settings Recovery; do
    case "$page" in Apps) section=apps;; Settings) section=settings;; Recovery) section=recovery;; esac
    cat > "/usr/share/applications/org.ruxeonrx.$page.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=RX $page
Exec=python3 /opt/RuxeonRX/shell/modern.py --page $section
Icon=/opt/RuxeonRX/shell/assets/ruxeonrx.svg
StartupWMClass=org.ruxeonrx.Apps
Categories=System;
EOF
done
cp /usr/share/applications/org.ruxeonrx.Apps.desktop /usr/share/applications/org.ruxeonrx.Desktop.desktop
printf 'NoDisplay=true\n' >> /usr/share/applications/org.ruxeonrx.Desktop.desktop
systemctl enable NetworkManager cups bluetooth
install -d /etc/NetworkManager/conf.d /etc/NetworkManager/system-connections
printf '[ifupdown]\nmanaged=true\n' > /etc/NetworkManager/conf.d/10-ruxeonrx.conf
if [[ ! -f /etc/NetworkManager/system-connections/ruxeonrx-wired.nmconnection ]]; then
    cat > /etc/NetworkManager/system-connections/ruxeonrx-wired.nmconnection <<'EOF'
[connection]
id=RuxeonRX Wired
type=ethernet
autoconnect=true
[ipv4]
method=auto
[ipv6]
method=auto
EOF
    chmod 0600 /etc/NetworkManager/system-connections/ruxeonrx-wired.nmconnection
fi
# The next boot uses NetworkManager; do not interrupt the builder's live SSH lease.
if command -v netplan >/dev/null; then
    install -d /etc/netplan
    if [[ ! -f /etc/netplan/99-ruxeonrx-desktop.yaml ]]; then
        printf 'network:\n  version: 2\n  renderer: NetworkManager\n' > /etc/netplan/99-ruxeonrx-desktop.yaml
        chmod 0600 /etc/netplan/99-ruxeonrx-desktop.yaml
    fi
    netplan generate
fi
# Netplan's generator can create runtime wants even after disable. Masking the
# competing guest units takes effect on the next boot, without stopping SSH now.
systemctl mask systemd-networkd.service systemd-networkd.socket
if systemctl cat networking.service >/dev/null 2>&1; then systemctl disable networking.service; fi
dpkg-query -W -f='${Package}=${Version}\n' > /etc/ruxeonrx/packages.lock
apt-get clean
rm -f /tmp/ruxeonrx-source.tar.gz
echo RX_PROVISION=ok
