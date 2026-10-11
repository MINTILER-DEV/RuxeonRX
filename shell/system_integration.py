"""Optional GNOME integration; no host writes outside an RX desktop session."""
import os
import ast
from pathlib import Path
import shutil
import subprocess

CORE_FAVORITES = ["org.ruxeonrx.Apps.desktop", "org.gnome.Nautilus.desktop", "org.gnome.Console.desktop", "firefox-esr.desktop", "org.ruxeonrx.Settings.desktop", "org.ruxeonrx.Recovery.desktop"]
GSETTINGS_TIMEOUT = 20
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
        result = subprocess.run(["gsettings", "set", schema, key, rendered], capture_output=True, text=True, timeout=GSETTINGS_TIMEOUT)
        if result.returncode: print("RX_SETTINGS_WARNING=" + result.stderr.strip(), flush=True)


def reconcile_settings(settings):
    """Preserve changes made through native System Settings, including reboot."""
    if not active(): return settings.all()
    stored = settings.all()
    for setting, (schema, key) in SETTING_MAP.items():
        rendered = subprocess.check_output(["gsettings", "get", schema, key], text=True, timeout=GSETTINGS_TIMEOUT).strip()
        if setting == "input.focus_follows_mouse": value = ast.literal_eval(rendered) in ("mouse", "sloppy")
        elif isinstance(stored[setting], bool):
            if rendered not in ("true", "false"): raise ValueError("invalid native boolean preference")
            value = rendered == "true"
        elif isinstance(stored[setting], float): value = float(rendered)
        else: value = ast.literal_eval(rendered)
        if value != stored[setting]:
            try: stored = settings.set(setting, value)
            except ValueError: print("RX_SETTINGS_WARNING=unsupported native value for " + setting, flush=True)
    return stored


def read_favorites():
    rendered = subprocess.check_output(["gsettings", "get", "org.gnome.shell", "favorite-apps"], text=True, timeout=GSETTINGS_TIMEOUT).strip()
    value = ast.literal_eval(rendered.removeprefix("@as "))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("invalid desktop favorites")
    return value


def favorite_id(app):
    return app.get("desktop_id") or "ruxeonrx-" + app["id"] + ".desktop"


def reconcile_favorites(manager):
    """Import taskbar pin/unpin actions before returning the app list."""
    if not active(): return
    favorites = read_favorites()
    for app in manager.registry.list():
        pinned = favorite_id(app) in favorites
        if bool(app.get("pinned")) != pinned:
            app["pinned"] = pinned
            manager.registry.replace(app)


def sync_favorites(records):
    if not active(): return
    pinned = [favorite_id(app) for app in records if app.get("pinned")]
    managed = {favorite_id(app) for app in records}
    # GNOME's own user pins are preserved; remove only managed entries no longer pinned.
    try:
        current = read_favorites()
    except (ValueError, SyntaxError, subprocess.SubprocessError): current = CORE_FAVORITES
    favorites = [item for item in current if not (item.startswith("ruxeonrx-") or item in managed) or item in pinned]
    for item in pinned:
        if item not in favorites: favorites.append(item)
    if favorites != current:
        subprocess.run(["gsettings", "set", "org.gnome.shell", "favorite-apps", repr(favorites)], check=True, timeout=GSETTINGS_TIMEOUT)


def import_core_apps(manager):
    marker = manager.state_dir / "base-apps-imported"
    if marker.exists() or not active(): return
    for filename in ("org.gnome.Nautilus.desktop", "org.gnome.Console.desktop", "org.gnome.TextEditor.desktop", "firefox-esr.desktop"):
        path = Path("/usr/share/applications") / filename
        if path.is_file():
            defaults = manager.associations.defaults()
            record = manager.import_desktop(path)
            # Adding the trusted base suite must not replace an existing user
            # default or make Terminal the default directory handler.
            for handler, app_id in defaults.items():
                manager.associations.set_default(handler, app_id)
            record["source"] = "Debian base (trusted)"
            record["desktop_id"] = filename
            record["pinned"] = filename in read_favorites()
            manager.registry.replace(record)
    marker.touch()
