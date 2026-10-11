"""Export normalized records into native desktop/MIME integration files."""
import configparser
from pathlib import Path
from system_integration import sync_favorites


def sync_desktop(manager):
    applications = Path.home() / ".local/share/applications"
    applications.mkdir(parents=True, exist_ok=True)
    records = manager.registry.list()
    expected = {"ruxeonrx-" + app["id"] + ".desktop" for app in records}
    for stale in applications.glob("ruxeonrx-*.desktop"):
        if stale.name not in expected: stale.unlink()
    root = Path(__file__).resolve().parents[1]
    for app in records:
        icon = root / "shell/assets/notes.svg"
        if app.get("desktop_icon"): icon = app["desktop_icon"]
        if app.get("icon") and app.get("package", {}).get("root"):
            candidate = Path(app["package"]["root"]) / app["icon"]
            if candidate.is_file(): icon = candidate
        handlers = ["x-scheme-handler/" + item[:-1] if item.endswith(":") else item for item in app.get("handlers", [])]
        content = "\n".join(("[Desktop Entry]", "Type=Application", "Name=" + app["name"].replace("\n", " "), f'Exec=python3 {root}/tools/rxctl launch {app["id"]} %u', "Icon=" + str(icon), "StartupWMClass=" + app.get("startup_wm_class", app["id"]), "Terminal=false", "MimeType=" + ";".join(handlers) + ";", ""))
        (applications / ("ruxeonrx-" + app["id"] + ".desktop")).write_text(content)
    mimeapps = Path.home() / ".config/mimeapps.list"
    mimeapps.parent.mkdir(parents=True, exist_ok=True)
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    if mimeapps.exists(): parser.read(mimeapps)
    if not parser.has_section("Default Applications"): parser.add_section("Default Applications")
    section = parser["Default Applications"]
    for name in list(section):
        if section[name].startswith("ruxeonrx-"): del section[name]
    for handler, app_id in manager.associations.defaults().items():
        key = "x-scheme-handler/" + handler[:-1] if handler.endswith(":") else handler
        section[key] = "ruxeonrx-" + app_id + ".desktop;"
    with mimeapps.open("w") as handle: parser.write(handle)
    sync_favorites(records)
