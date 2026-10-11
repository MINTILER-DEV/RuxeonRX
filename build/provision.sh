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
    apt-get install -y --no-install-recommends linux-image-amd64 xserver-xorg xserver-xorg-video-all lightdm openbox python3 python3-tk python3-jsonschema bubblewrap dbus-x11 xterm fonts-dejavu-core xdotool scrot x11-utils x11-xserver-utils xinput e2fsprogs sudo
fi
id rx >/dev/null 2>&1 || useradd -m -s /bin/bash rx
install -d -m 0700 -o rx -g rx /home/rx/.local /home/rx/.local/state /home/rx/.local/share /home/rx/.local/share/applications /home/rx/.local/state/ruxeonrx /home/rx/.config /home/rx/.config/openbox
if [[ ! -f /home/rx/.config/openbox/menu.xml ]]; then
    install -m 0600 -o rx -g rx /opt/RuxeonRX/build/desktop-menu.xml /home/rx/.config/openbox/menu.xml
fi
install -d /usr/share/xsessions /etc/lightdm/lightdm.conf.d /etc/ruxeonrx
cat > /usr/share/xsessions/ruxeonrx.desktop <<EOF
[Desktop Entry]
Name=RuxeonRX
Exec=/opt/RuxeonRX/tools/rx-session
Type=Application
EOF
cat > /etc/lightdm/lightdm.conf.d/50-ruxeonrx.conf <<EOF
[Seat:*]
autologin-user=rx
autologin-user-timeout=0
user-session=ruxeonrx
EOF
chmod +x /opt/RuxeonRX/tools/rxctl /opt/RuxeonRX/tools/rx-session
printf 'rx ALL=(root) NOPASSWD: /sbin/poweroff, /sbin/reboot\n' > /etc/sudoers.d/ruxeonrx-power
chmod 0440 /etc/sudoers.d/ruxeonrx-power
python3 /opt/RuxeonRX/tools/rx-package.py
printf '{"version":"0.5.0-alpha","revision":"%s","architecture":"x86_64","base":"Debian 13"}\n' "$revision" > /etc/ruxeonrx/build.json
cat > /etc/os-release <<EOF
PRETTY_NAME="RuxeonRX 0.5 Alpha (Debian 13)"
NAME=RuxeonRX
ID=ruxeonrx
ID_LIKE=debian
VERSION_ID=0.5
EOF
systemctl set-default graphical.target
systemctl enable lightdm
install -d /etc/systemd/system/lightdm.service.d
printf '[Service]\nExecStartPre=/usr/bin/python3 /opt/RuxeonRX/tools/rx-boot.py\n' > /etc/systemd/system/lightdm.service.d/ruxeonrx.conf
systemctl daemon-reload
dpkg-query -W -f='${Package}=${Version}\n' > /etc/ruxeonrx/packages.lock
apt-get clean
rm -f /tmp/ruxeonrx-source.tar.gz
echo RX_PROVISION=ok
