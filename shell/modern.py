#!/usr/bin/env python3
"""GTK 4/libadwaita RX desktop applications and always-running permission UI."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk/bindings/python"))
from rxipc import Client


class Desktop(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.ruxeonrx.Desktop", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.client = Client(Path(os.environ.get("RX_RUNTIME", str(Path(os.environ["XDG_RUNTIME_DIR"]) / "ruxeonrx"))) / "appd.sock")
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.window = None; self.selection = None; self.apps = []; self.prompting = set(); self.poll_busy = False
        self.pages = {}; self.settings_loaded = False; self.notifications_seen = set()
        self.notification_cache = Path.home() / ".local/state/ruxeonrx/notifications-delivered.json"
        try:
            delivered = json.loads(self.notification_cache.read_text())
            if isinstance(delivered, list): self.notifications_seen = {item for item in delivered[-100:] if isinstance(item, str)}
        except (OSError, ValueError): pass
        self.safe_mode = (Path.home() / ".local/state/ruxeonrx/safe-mode").exists()
        self.connect("command-line", self.command_line)

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.hold()
        self.set_accels_for_action("app.refresh", ["F5"])
        self.set_accels_for_action("app.search", ["<Control>f"])
        self.set_accels_for_action("app.launch", ["<Control>l"])
        self.set_accels_for_action("app.sample", ["<Control>i"])
        self.set_accels_for_action("app.logs", ["<Control>d"])
        for name, callback in (("refresh", self.refresh), ("search", self.focus_search), ("launch", lambda: self.operation("launch")), ("sample", self.install_sample), ("logs", self.view_logs)):
            action = Gio.SimpleAction.new(name, None); action.connect("activate", lambda action, parameter, cb=callback: cb()); self.add_action(action)
        GLib.timeout_add(750, self.poll)

    def command_line(self, app, command):
        arguments = command.get_arguments()
        page = arguments[arguments.index("--page") + 1] if "--page" in arguments else "apps"
        self.show(page)
        return 0

    def call(self, method, done=None, **params):
        future = self.executor.submit(self.client.call, method, **params)
        def finished(result):
            def deliver():
                try:
                    value = result.result()
                    if done: done(value)
                except Exception as error: self.error(str(error))
                return False
            GLib.idle_add(deliver)
        future.add_done_callback(finished)

    def error(self, message):
        if self.window: self.toast.add_toast(Adw.Toast.new(message[:300]))
        print("RX_UI_ERROR=" + message, flush=True)

    @staticmethod
    def box(spacing=12):
        return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)

    def button(self, text, callback, suggested=False, destructive=False):
        button = Gtk.Button(label=text)
        if suggested: button.add_css_class("suggested-action")
        if destructive: button.add_css_class("destructive-action")
        button.connect("clicked", lambda unused: callback())
        return button

    def group(self, parent, title, description=None):
        group = Adw.PreferencesGroup(title=title)
        if description: group.set_description(description)
        parent.append(group)
        return group

    def row(self, group, title, subtitle="", button=None):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        if button: row.add_suffix(button); row.set_activatable_widget(button)
        group.add(row)
        return row

    def show(self, page):
        if self.window is None:
            self.window = Adw.ApplicationWindow(application=self, title="RX Apps", default_width=1040, default_height=700)
            # Keep the permission broker alive and allow taskbar launchers to
            # reopen the same application after the management window closes.
            self.window.connect("close-request", lambda window: (window.set_visible(False), True)[1])
            toolbar = Adw.ToolbarView(); self.toast = Adw.ToastOverlay(); self.toast.set_child(toolbar); self.window.set_content(self.toast)
            header = Adw.HeaderBar(); header.set_title_widget(Adw.WindowTitle(title="RuxeonRX", subtitle="1.0 · Native desktop beta"))
            header.pack_end(self.button("System settings", lambda: self.system_settings()))
            toolbar.add_top_bar(header)
            self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
            sidebar = Gtk.StackSidebar(stack=self.stack); sidebar.set_size_request(175, -1)
            body = Gtk.Box(spacing=0); body.append(sidebar); body.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)); body.append(self.stack)
            self.stack.set_hexpand(True); self.stack.set_vexpand(True); toolbar.set_content(body)
            for key, title in (("apps", "Applications"), ("permissions", "Permissions"), ("sources", "Software sources"), ("settings", "Preferences"), ("notifications", "Notifications"), ("recovery", "Recovery"), ("devices", "Diagnostics")):
                content = self.box(20)
                for edge in ("top", "bottom", "start", "end"): getattr(content, "set_margin_" + edge)(24)
                scroller = Gtk.ScrolledWindow(child=content, hexpand=True, vexpand=True)
                self.stack.add_titled(scroller, key, title); self.pages[key] = content
            self.build_apps(); self.build_sources(); self.build_settings(); self.build_recovery(); self.build_diagnostics()
            self.notification_view = Gtk.Label(wrap=True, xalign=0, selectable=True); self.pages["notifications"].append(self.notification_view)
            self.permission_group = self.group(self.pages["permissions"], "Application access", "Select an app in Applications. Changes to network access take effect after stopping and relaunching the app.")
            self.refresh()
            GLib.timeout_add(500, self.ready)
        self.stack.set_visible_child_name(page if page in self.pages else "apps")
        self.window.set_title("RX " + {"apps": "Apps", "settings": "Settings", "recovery": "Recovery"}.get(page, "Apps"))
        self.window.present()

    def build_apps(self):
        parent = self.pages["apps"]
        title = Gtk.Label(label="Your applications", xalign=0); title.add_css_class("title-1"); parent.append(title)
        controls = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry(placeholder_text="Search installed applications", hexpand=True)
        self.search.connect("search-changed", lambda unused: self.refresh()); controls.append(self.search)
        controls.append(self.button("Install package", lambda: self.choose_file("Install package", lambda path: self.mutate("install", path=path)), True))
        controls.append(self.button("RX Notes", self.install_sample))
        parent.append(controls)
        self.app_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE); self.app_list.add_css_class("boxed-list")
        self.app_list.connect("row-selected", self.selected)
        parent.append(self.app_list)
        self.detail_group = self.group(parent, "Application details")
        self.detail_row = self.row(self.detail_group, "Select an application")
        self.detail_label = Gtk.Label(wrap=True, selectable=True, xalign=0); parent.append(self.detail_label)
        actions = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=2, max_children_per_line=4, column_spacing=8, row_spacing=8)
        for text, callback in (("Launch", lambda: self.operation("launch")), ("Pin / unpin", self.pin), ("Update package", lambda: self.choose_file("Update package", lambda path: self.mutate("update", path=path))), ("Sample update", lambda: self.mutate("update", path=str(ROOT / "packages/catalog/rx-notes-0.2.0.rxpkg"))), ("Repair", lambda: self.operation("repair")), ("Roll back", lambda: self.operation("rollback")), ("View logs", self.view_logs), ("Reset app data", lambda: self.confirm("Reset app data?", "Managed data will be erased and the app stopped.", lambda: self.operation("reset-data"))), ("Remove", lambda: self.confirm("Remove this application?", "The RX registration and managed package/data will be removed. System applications remain installed in the base OS.", lambda: self.operation("remove", purge_data=True))), ("Import desktop app", self.import_desktop)):
            actions.insert(self.button(text, callback), -1)
        parent.append(actions)

    def refresh(self):
        self.call("apps", self.render_apps, query=self.search.get_text())

    def render_apps(self, records):
        old = self.selection; self.apps = records
        child = self.app_list.get_first_child()
        while child:
            following = child.get_next_sibling(); self.app_list.remove(child); child = following
        for app in sorted(records, key=lambda item: (not item.get("pinned", False), item["name"].casefold())):
            row = Adw.ActionRow(title=("★ " if app.get("pinned") else "") + app["name"], subtitle=f"{app['version']} · Native Linux · {app['source']}")
            row.app_id = app["id"]
            icon_path = Path(app.get("package", {}).get("root", "")) / app.get("icon", "")
            icon = Gtk.Image.new_from_file(str(icon_path)) if app.get("icon") and icon_path.is_file() else Gtk.Image(icon_name=app.get("desktop_icon", "application-x-executable-symbolic"))
            icon.set_pixel_size(36); row.add_prefix(icon)
            self.app_list.append(row)
            if app["id"] == old: self.app_list.select_row(row)
        if self.app_list.get_selected_row() is None and records: self.app_list.select_row(self.app_list.get_row_at_index(0))
        if not records:
            self.selection = None; self.detail_row.set_title("No matching applications" if self.search.get_text() else "Install RX Notes or a trusted native package")
            self.detail_label.set_label("")

    def selected(self, unused, row):
        self.selection = row.app_id if row else None
        if self.selection: self.call("inspect", self.render_detail, app_id=self.selection)

    def render_detail(self, details):
        app = details["app"]
        if app["id"] != self.selection: return
        self.detail_row.set_title(app["name"])
        unrestricted = app.get("unrestricted") or not app.get("sandbox")
        self.detail_row.set_subtitle("Trusted / unrestricted native app" if unrestricted else "Sandboxed native package · scoped RX portals")
        self.detail_label.set_label(f"{app['id']}\nManaged storage: {details['storage_bytes']:,} bytes\n" + "\n".join(details["logs"][-3:]))
        for row in list(getattr(self, "permission_rows", [])): self.permission_group.remove(row)
        self.permission_rows = []
        for capability in app["requested_permissions"]:
            supported = capability in ("files", "notifications", "network") and not unrestricted
            switch = Gtk.Switch(active=details["permissions"].get(capability, False), valign=Gtk.Align.CENTER, sensitive=supported)
            switch.connect("notify::active", lambda widget, parameter, c=capability, identifier=app["id"]: self.call("decide", app_id=identifier, capability=c, allowed=widget.get_active()))
            explanation = "Unrestricted app: this control cannot constrain native access" if unrestricted else "Not mediated by RX 1.0" if not supported else "Per-request consent" if capability == "files" else "Launch-time namespace policy" if capability == "network" else "Desktop policy"
            row = self.row(self.permission_group, capability.replace("-", " ").title(), explanation, switch); self.permission_rows.append(row)

    def mutate(self, method, **params):
        self.call(method, lambda result: (self.toast.add_toast(Adw.Toast.new("Completed")), self.refresh()), **params)

    def operation(self, method, **params):
        if self.selection: self.mutate(method, app_id=self.selection, **params)

    def pin(self):
        app = next((item for item in self.apps if item["id"] == self.selection), None)
        if app: self.operation("pin", pinned=not app.get("pinned", False))

    def install_sample(self):
        self.mutate("install", path=str(ROOT / "packages/catalog/rx-notes-0.1.0.rxpkg"))

    def focus_search(self):
        self.stack.set_visible_child_name("apps"); self.search.grab_focus()

    def choose_file(self, title, callback, save=False, suggested=None):
        dialog = Gtk.FileDialog(title=title)
        if suggested: dialog.set_initial_file(Gio.File.new_for_path(str(suggested)))
        def finish(dialog, result):
            try: file = dialog.save_finish(result) if save else dialog.open_finish(result)
            except GLib.Error: return
            if file and file.get_path(): callback(file.get_path())
        (dialog.save if save else dialog.open)(self.window, None, finish)

    def confirm(self, title, message, callback):
        dialog = Adw.MessageDialog(transient_for=self.window, heading=title, body=message)
        dialog.add_response("cancel", "_Cancel"); dialog.add_response("continue", "_Continue")
        dialog.set_response_appearance("continue", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda unused, response: callback() if response == "continue" else None); dialog.present()

    def import_desktop(self):
        self.choose_file("Import desktop app", lambda path: self.confirm("Trust this native app?", "It runs with your full user access. RX permission switches cannot sandbox it.", lambda: self.mutate("import", path=path)))

    def text_window(self, title, text):
        window = Adw.Window(transient_for=self.window, title=title, default_width=740, default_height=480)
        toolbar = Adw.ToolbarView(); toolbar.add_top_bar(Adw.HeaderBar())
        view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR); view.get_buffer().set_text(text)
        toolbar.set_content(Gtk.ScrolledWindow(child=view)); window.set_content(toolbar); window.present()

    def view_logs(self):
        if self.selection: self.call("inspect", lambda info: self.text_window("Application diagnostics", "\n".join(info["logs"])), app_id=self.selection)

    def build_sources(self):
        parent = self.pages["sources"]
        group = self.group(parent, "Trusted software sources", "Catalogs require HTTPS or local file URLs. Package identity and checksums are verified before installation.")
        self.row(group, "Review sources", button=self.button("View", lambda: self.call("sources", lambda data: self.text_window("Software sources", json.dumps(data, indent=2)))))
        self.source_name = Gtk.Entry(placeholder_text="Source name"); self.source_url = Gtk.Entry(placeholder_text="https://example.org/catalog.json")
        parent.append(self.source_name); parent.append(self.source_url)
        parent.append(self.button("Add trusted source", lambda: self.mutate("source", name=self.source_name.get_text(), url=self.source_url.get_text())))
        self.source_app = Gtk.Entry(placeholder_text="Application ID to install from this source"); parent.append(self.source_app)
        parent.append(self.button("Install from source", lambda: self.mutate("source-install", name=self.source_name.get_text(), app_id=self.source_app.get_text())))
        parent.append(self.button("Check updates", lambda: self.call("updates", self.show_updates), True))
        self.handler = Gtk.Entry(placeholder_text="Default MIME type or protocol, e.g. text/plain"); parent.append(self.handler)
        parent.append(self.button("Use selected app as default", lambda: self.operation("default", handler=self.handler.get_text())))

    def show_updates(self, updates):
        if not updates: self.toast.add_toast(Adw.Toast.new("Managed apps are up to date")); return
        for update in updates:
            self.confirm("Update " + update["app_id"] + "?", update["installed"] + " → " + update["available"], lambda item=update: self.mutate("source-install", name=item["source"], app_id=item["app_id"], update=True))

    def build_settings(self):
        parent = self.pages["settings"]
        self.settings_group = self.group(parent, "Appearance and accessibility", "Preferences persist across login. System settings provide display, sound, network, keyboard, privacy and printer controls.")
        self.call("settings", self.render_settings) if not self.safe_mode else self.render_settings({"appearance.high_contrast": False, "appearance.text_scale": 1.0, "input.touchpad_natural_scroll": True})
        integrations = self.group(parent, "System controls")
        for name, panel in (("Display", "display"), ("Sound", "sound"), ("Network", "network"), ("Bluetooth", "bluetooth"), ("Keyboard", "keyboard"), ("Mouse and touchpad", "mouse"), ("Printers", "printers"), ("Privacy", "privacy"), ("User accounts", ("system", "users"))):
            self.row(integrations, name, button=self.button("Open", lambda p=panel: self.system_settings(p)))

    def render_settings(self, settings):
        for key, label in (("appearance.high_contrast", "High contrast"), ("input.touchpad_natural_scroll", "Natural touchpad scrolling")):
            switch = Gtk.Switch(active=settings[key], valign=Gtk.Align.CENTER)
            switch.connect("notify::active", lambda widget, unused, k=key: self.mutate("set", key=k, value=widget.get_active()))
            self.row(self.settings_group, label, button=switch)
        adjustment = Gtk.Adjustment(value=settings["appearance.text_scale"], lower=0.75, upper=3.0, step_increment=0.25)
        scale = Gtk.SpinButton(adjustment=adjustment, digits=2, valign=Gtk.Align.CENTER)
        scale.connect("value-changed", lambda widget: self.mutate("set", key="appearance.text_scale", value=widget.get_value()))
        self.row(self.settings_group, "Text scale", button=scale)
        scheme = Gtk.DropDown.new_from_strings(["System", "Light", "Dark"])
        values = ["default", "prefer-light", "prefer-dark"]; scheme.set_selected(values.index(settings.get("appearance.color_scheme", "prefer-dark")))
        scheme.connect("notify::selected", lambda widget, unused: self.mutate("set", key="appearance.color_scheme", value=values[widget.get_selected()]))
        self.row(self.settings_group, "Color scheme", button=scheme)

    def system_settings(self, panel=None):
        try: subprocess.Popen(["gnome-control-center"] + ([panel] if isinstance(panel, str) else list(panel or [])))
        except OSError as error: self.error(str(error))

    def build_recovery(self):
        parent = self.pages["recovery"]
        group = self.group(parent, "Recovery snapshots", "Snapshots replace RX-managed app state; they do not roll back the entire Debian base or your personal home folder.")
        self.snapshot_name = Gtk.Entry(placeholder_text="Snapshot name, e.g. before-update"); parent.append(self.snapshot_name)
        self.row(group, "Create snapshot", button=self.button("Create", lambda: self.mutate("snapshot", name=self.snapshot_name.get_text()), True))
        self.row(group, "List saved snapshots", button=self.button("View", lambda: self.call("snapshots", lambda names: self.text_window("Recovery snapshots", "\n".join(names)))))
        self.row(group, "Restore snapshot", "Enter an existing name above. Running managed apps will be stopped.", self.button("Restore", lambda: self.confirm("Replace RX-managed state?", "A before-restore backup is created. Current managed state is then replaced.", lambda: self.mutate("restore", name=self.snapshot_name.get_text()))))
        self.row(group, "Safe mode on next login", "Minimal desktop recovery independent of GNOME extensions", self.button("Enable", lambda: self.safe_marker(True)))
        self.row(group, "Return to normal mode", button=self.button("Disable safe mode", lambda: self.safe_marker(False)))
        self.row(group, "Restart the system", button=self.button("Restart", lambda: self.confirm("Restart RuxeonRX?", "Save your work before restarting.", lambda: subprocess.Popen(["sudo", "/sbin/reboot"])) ))

    def safe_marker(self, enabled):
        marker = Path.home() / ".local/state/ruxeonrx/safe-mode"
        marker.touch() if enabled else marker.unlink(missing_ok=True)
        self.toast.add_toast(Adw.Toast.new("Login mode saved; restart to apply"))

    def build_diagnostics(self):
        parent = self.pages["devices"]
        group = self.group(parent, "Hardware and service diagnostics")
        self.row(group, "Device and renderer inventory", button=self.button("Inspect", lambda: self.call("devices", lambda info: self.text_window("Device diagnostics", json.dumps(info, indent=2)))))
        self.row(group, "Live service health", button=self.button("Inspect", lambda: self.call("health", lambda info: self.text_window("Service health", json.dumps(info, indent=2)))))
        self.row(group, "Export support bundle", "Review logs before sharing. Private app documents, grants and SSH keys are excluded.", self.button("Export", lambda: self.choose_file("Export support bundle", lambda path: self.mutate("bundle", path=path), save=True, suggested=Path.home() / "ruxeonrx-support.zip")))
        self.row(group, "Native desktop beta", "x86_64 QEMU, BIOS, standard VGA, TCG baseline. Physical hardware and accelerated configurations require separate validation.")

    def poll(self):
        if self.poll_busy or self.window is None: return True
        self.poll_busy = True
        def fetch(): return self.client.call("pending"), self.client.call("notifications")
        future = self.executor.submit(fetch)
        def finish(result):
            def deliver():
                self.poll_busy = False
                try:
                    pending, notifications = result.result()
                    for request in pending:
                        if request["id"] not in self.prompting: self.permission(request)
                    self.notification_view.set_label("\n\n".join(item["title"] + "\n" + item["body"] for item in notifications) or "No notifications yet.")
                    current_ids = set()
                    for item in notifications:
                        identity = item.get("id", json.dumps(item, sort_keys=True))
                        current_ids.add(identity)
                        if identity not in self.notifications_seen:
                            self.notifications_seen.add(identity)
                            notification = Gio.Notification.new(item["title"])
                            notification.set_body(item["body"])
                            notification.set_icon(Gio.ThemedIcon.new("dialog-information-symbolic"))
                            self.send_notification(None, notification)
                    self.notifications_seen.intersection_update(current_ids)
                    cached = json.dumps(sorted(self.notifications_seen))
                    if not self.notification_cache.exists() or self.notification_cache.read_text() != cached:
                        temporary = self.notification_cache.with_suffix(".tmp")
                        temporary.write_text(cached); temporary.replace(self.notification_cache)
                except Exception as error: self.error(str(error))
                return False
            GLib.idle_add(deliver)
        future.add_done_callback(finish)
        return True

    def permission(self, request):
        self.prompting.add(request["id"])
        dialog = Adw.MessageDialog(transient_for=self.window, heading="Application permission", body=request["app_id"] + " requests " + request["capability"] + ". Allow this request?")
        dialog.set_title("RuxeonRX permission"); dialog.add_response("deny", "_Deny"); dialog.add_response("allow", "_Allow")
        dialog.set_default_response("deny"); dialog.set_close_response("deny")
        def respond(unused, response):
            if response == "allow" and request["capability"] == "files":
                chooser = Gtk.FileDialog(title="Open")
                if request.get("suggested_path"): chooser.set_initial_file(Gio.File.new_for_path(request["suggested_path"]))
                def chosen(chooser, result):
                    try: file = chooser.open_finish(result); path = file.get_path() if file else ""
                    except GLib.Error: path = ""
                    self.call("answer", id=request["id"], allowed=bool(path), path=path)
                chooser.open(self.window, None, chosen)
            else: self.call("answer", id=request["id"], allowed=response == "allow", path="")
        dialog.connect("response", respond); self.window.present(); dialog.present()

    def ready(self):
        if self.window.get_visible():
            Path(os.environ.get("RX_RUNTIME", str(Path(os.environ["XDG_RUNTIME_DIR"]) / "ruxeonrx")), "graphical-ready").write_text("ready\n")
            print("RX_GRAPHICAL_SESSION=ready GTK4", flush=True)
            return False
        return True


if __name__ == "__main__":
    raise SystemExit(Desktop().run(sys.argv))
