"""Optional GNOME integration; no host writes outside an RX desktop session."""
import os
import ast
from pathlib import Path
import shutil
import subprocess

CORE_FAVORITES = ["org.ruxeonrx.Apps.desktop", "org.gnome.Nautilus.desktop", "org.gnome.Console.desktop", "firefox-esr.desktop", "org.ruxeonrx.Settings.desktop", "org.ruxeonrx.Recovery.desktop"]
SETTING_MAP = {
    "appearance.text_scale": ("org.gnome.desktop.interface", "text-scaling-factor"),
    "appearance.high_contrast": ("org.gnome.desktop.a11y.interface", "high-contrast"),
    "appearance.color_scheme": ("org.gnome.desktop.interface", "color-scheme"),
    "input.touchpad_natural_scroll": ("org.gnome.desktop.peripherals.touchpad", "natural-scroll"),
    "input.focus_follows_mouse": ("org.gnome.desktop.wm.preferences", "focus-mode"),
}


def active():
    return os.environ.get("RX_DESKTOP") == "GNOME" and bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS")) and shutil.which("gsettings")


def apply_settings(settings):
    if not active(): return
    for setting, (schema, key) in SETTING_MAP.items():
        value = settings[setting]
        if setting == "input.focus_follows_mouse": value = "sloppy" if value else "click"
        rendered = str(value).lower() if isinstance(value, bool) else str(value) if isinstance(value, (int, float)) else repr(value)
        result = subprocess.run(["gsettings", "set", schema, key, rendered], capture_output=True, text=True, timeout=5)
        if result.returncode: print("RX_SETTINGS_WARNING=" + result.stderr.strip(), flush=True)


def read_favorites():
    rendered = subprocess.check_output(["gsettings", "get", "org.gnome.shell", "favorite-apps"], text=True, timeout=5).strip()
    value = ast.literal_eval(rendered.removeprefix("@as "))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("invalid desktop favorites")
    return value


def reconcile_favorites(manager):
    """Import taskbar pin/unpin actions before returning the app list."""
    if not active(): return
    favorites = read_favorites()
    for app in manager.registry.list():
        pinned = "ruxeonrx-" + app["id"] + ".desktop" in favorites
        if bool(app.get("pinned")) != pinned:
            app["pinned"] = pinned
            manager.registry.replace(app)


def sync_favorites(records):
    if not active(): return
    pinned = ["ruxeonrx-" + app["id"] + ".desktop" for app in records if app.get("pinned")]
    # GNOME's own user pins are preserved; remove only managed entries no longer pinned.
    try:
        current = read_favorites()
    except (ValueError, SyntaxError, subprocess.SubprocessError): current = CORE_FAVORITES
    favorites = [item for item in current if not item.startswith("ruxeonrx-") or item in pinned]
    for item in pinned:
        if item not in favorites: favorites.append(item)
    subprocess.run(["gsettings", "set", "org.gnome.shell", "favorite-apps", repr(favorites)], check=True, timeout=5)


def import_core_apps(manager):
    marker = manager.state_dir / "base-apps-imported"
    if marker.exists() or not active(): return
    for filename in ("org.gnome.Nautilus.desktop", "org.gnome.Console.desktop", "org.gnome.TextEditor.desktop", "firefox-esr.desktop"):
        path = Path("/usr/share/applications") / filename
        if path.is_file():
            record = manager.import_desktop(path)
            record["source"] = "Debian base (trusted)"
            manager.registry.replace(record)
    marker.touch()
