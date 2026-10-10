#!/usr/bin/env python3
"""Interactive RuxeonRX desktop, backed exclusively by the appd IPC contract."""
import json
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk/bindings/python"))
from rxipc import Client


class Desktop:
    def __init__(self):
        self.client = Client(Path(os.environ["RX_RUNTIME"]) / "appd.sock")
        self.root = tk.Tk()
        self.root.title("RuxeonRX Desktop")
        self.root.geometry("1024x720+0+0")
        self.root.minsize(800, 560)
        self.status = tk.StringVar(value="Welcome to RuxeonRX 0.5 Alpha")
        self.query = tk.StringVar()
        self.selection = None
        self.prompting = set()
        self.apps = []
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TButton", padding=8)
        style.configure("Treeview", rowheight=36, font=("DejaVu Sans", 11))
        header = ttk.Frame(self.root, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="RuxeonRX", font=("DejaVu Sans", 22, "bold")).pack(side="left")
        ttk.Label(header, text="0.5 Alpha • Native desktop", padding=12).pack(side="left")
        ttk.Button(header, text="Power", command=self.power).pack(side="right")
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=12)
        self.app_frame = ttk.Frame(self.tabs, padding=12)
        self.permission_frame = ttk.Frame(self.tabs, padding=12)
        self.settings_frame = ttk.Frame(self.tabs, padding=12)
        self.support_frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.app_frame, text="Applications")
        self.tabs.add(self.permission_frame, text="Permissions")
        self.tabs.add(self.settings_frame, text="Settings")
        self.tabs.add(self.support_frame, text="Diagnostics & recovery")
        self.build_apps()
        self.build_permissions()
        self.build_settings()
        self.build_support()
        ttk.Label(self.root, textvariable=self.status, padding=10).pack(fill="x")
        self.root.bind("<Control-f>", lambda event: self.focus_search())
        self.root.bind("<Control-i>", lambda event: self.install_sample())
        self.root.bind("<Control-l>", lambda event: self.launch())
        self.root.bind("<Control-u>", lambda event: self.update_sample())
        self.root.bind("<Control-r>", lambda event: self.remove())
        self.root.bind("<F5>", lambda event: self.refresh())
        self.query.trace_add("write", lambda *args: self.refresh())
        self.refresh()
        self.root.after(300, self.poll)
        self.root.after(500, self.ready)
        self.root.protocol("WM_DELETE_WINDOW", self.root.iconify)

    def call(self, method, **params):
        try:
            result = self.client.call(method, **params)
            self.status.set(method.replace("-", " ").capitalize() + " completed")
            return result
        except Exception as error:
            self.status.set(str(error))
            messagebox.showerror("RuxeonRX", str(error), parent=self.root)
            return None

    def build_apps(self):
        toolbar = ttk.Frame(self.app_frame)
        toolbar.pack(fill="x", pady=6)
        self.search = ttk.Entry(toolbar, textvariable=self.query, width=28)
        self.search.pack(side="left", padx=4)
        ttk.Label(toolbar, text="Search apps (Ctrl+F)").pack(side="left")
        ttk.Button(toolbar, text="Install package…", command=self.install).pack(side="right")
        ttk.Button(toolbar, text="Install RX Notes", command=self.install_sample).pack(side="right", padx=4)
        self.tree = ttk.Treeview(self.app_frame, columns=("name", "version", "source"), show="headings", selectmode="browse", height=7)
        for key, title in (("name", "Application"), ("version", "Version"), ("source", "Source")):
            self.tree.heading(key, text=title)
        self.tree.column("name", width=360)
        self.tree.column("version", width=100)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.tree.bind("<Return>", lambda event: self.launch())
        self.tree.bind("<Double-1>", lambda event: self.launch())
        controls = ttk.Frame(self.app_frame)
        controls.pack(fill="x", pady=8)
        for label, command in (("Launch", self.launch), ("Update…", self.update), ("Sample update", self.update_sample), ("Repair", lambda: self.operation("repair")), ("Roll back", lambda: self.operation("rollback")), ("Remove", self.remove), ("Import .desktop…", self.import_desktop)):
            ttk.Button(controls, text=label, command=command).pack(side="left", padx=2)
        self.details = tk.Text(self.app_frame, height=6, wrap="word", state="disabled", font=("DejaVu Sans", 10))
        self.details.pack(fill="x")

    def focus_search(self):
        self.tabs.select(self.app_frame)
        self.search.focus_set()

    def refresh(self):
        old = self.selection
        self.apps = self.client.call("apps", query=self.query.get())
        for item in self.tree.get_children(): self.tree.delete(item)
        for app in self.apps:
            self.tree.insert("", "end", iid=app["id"], values=(app["name"], app["version"], app["source"]))
        if self.apps:
            self.selection = old if old in [app["id"] for app in self.apps] else self.apps[0]["id"]
            self.tree.selection_set(self.selection)
        else:
            self.selection = None
        self.select()
        self.refresh_permissions()

    def select(self, event=None):
        selected = self.tree.selection()
        self.selection = selected[0] if selected else None
        details = self.client.call("inspect", app_id=self.selection) if self.selection else {}
        self.details.configure(state="normal")
        if details:
            app = details["app"]
            content = f"{app['name']} • Native Linux {'(unrestricted)' if app.get('unrestricted') else '(managed package)'}\nID: {app['id']} • Storage: {details['storage_bytes']} bytes\nPermissions: {json.dumps(details['permissions'])}\n" + "\n".join(details["logs"][-4:])
        else:
            content = "No apps installed. Install RX Notes or choose a native .rxpkg package."
        self.details.delete("1.0", "end"); self.details.insert("1.0", content); self.details.configure(state="disabled")

    def install(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("RuxeonRX package", "*.rxpkg"), ("Manifest", "*.json")])
        if path: self.call("install", path=path); self.refresh()

    def install_sample(self):
        self.call("install", path=str(ROOT / "packages/catalog/rx-notes-0.1.0.rxpkg"))
        self.refresh()

    def update(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("RuxeonRX package", "*.rxpkg")])
        if path: self.call("update", path=path); self.refresh()

    def update_sample(self):
        self.call("update", path=str(ROOT / "packages/catalog/rx-notes-0.2.0.rxpkg")); self.refresh()

    def launch(self):
        if self.selection: self.call("launch", app_id=self.selection); self.refresh()

    def operation(self, method):
        if self.selection: self.call(method, app_id=self.selection); self.refresh()

    def remove(self):
        if self.selection and messagebox.askyesno("Remove app", "Remove this app and its managed data?", parent=self.root):
            self.call("remove", app_id=self.selection, purge_data=True); self.refresh()

    def import_desktop(self):
        path = filedialog.askopenfilename(parent=self.root, initialdir="/usr/share/applications", filetypes=[("Desktop entry", "*.desktop")])
        if path and messagebox.askyesno("Native application", "This regular native application runs with your user access. Register it?", parent=self.root):
            self.call("import", path=path); self.refresh()

    def build_permissions(self):
        ttk.Label(self.permission_frame, text="Select an app and review its declared capabilities.", font=("DejaVu Sans", 12)).pack(anchor="w", pady=12)
        self.permission_controls = ttk.Frame(self.permission_frame)
        self.permission_controls.pack(fill="x")
        self.notification_text = tk.Text(self.permission_frame, height=10, wrap="word", state="disabled")
        self.notification_text.pack(fill="both", expand=True, pady=12)

    def refresh_permissions(self):
        for child in self.permission_controls.winfo_children(): child.destroy()
        if not self.selection: return
        details = self.client.call("inspect", app_id=self.selection)
        for capability in details["app"]["requested_permissions"]:
            row = ttk.Frame(self.permission_controls); row.pack(fill="x", pady=4)
            ttk.Label(row, text=capability + ": " + ("allowed" if details["permissions"].get(capability) else "denied / ask"), width=35).pack(side="left")
            for allowed in (True, False):
                ttk.Button(row, text="Allow" if allowed else "Deny", command=lambda c=capability, a=allowed: self.set_permission(c, a)).pack(side="left", padx=6)

    def set_permission(self, capability, allowed):
        self.call("decide", app_id=self.selection, capability=capability, allowed=allowed); self.refresh()

    def build_settings(self):
        settings = self.client.call("settings")
        for key, label in (("appearance.high_contrast", "High contrast"), ("input.touchpad_natural_scroll", "Natural touchpad scrolling"), ("privacy.telemetry", "Optional telemetry preference (no collection service)")):
            value = tk.BooleanVar(value=settings[key])
            ttk.Checkbutton(self.settings_frame, text=label, variable=value, command=lambda k=key, v=value: self.setting(k, v.get())).pack(anchor="w", pady=10)
        ttk.Label(self.settings_frame, text="Text scale").pack(anchor="w")
        self.scale = tk.DoubleVar(value=settings["appearance.text_scale"])
        ttk.Spinbox(self.settings_frame, from_=0.75, to=3.0, increment=0.25, textvariable=self.scale, width=10).pack(anchor="w")
        ttk.Button(self.settings_frame, text="Apply scale", command=lambda: self.setting("appearance.text_scale", self.scale.get())).pack(anchor="w", pady=10)
        ttk.Label(self.settings_frame, text="Sources are explicitly trusted by you. Packages are checksum verified.").pack(anchor="w", pady=10)
        ttk.Button(self.settings_frame, text="Add software source…", command=self.add_source).pack(anchor="w")
        ttk.Button(self.settings_frame, text="View sources", command=lambda: messagebox.showinfo("Sources", json.dumps(self.client.call("sources"), indent=2))).pack(anchor="w", pady=10)
        self.apply_style(settings)

    def setting(self, key, value):
        result = self.call("set", key=key, value=value)
        if result: self.apply_style(result)

    def apply_style(self, settings):
        size = int(11 * settings["appearance.text_scale"])
        style = ttk.Style(self.root)
        colours = {"background": "#111111", "foreground": "#ffffff"} if settings["appearance.high_contrast"] else {"background": "#e9eef5", "foreground": "#14243b"}
        style.configure(".", font=("DejaVu Sans", size), **colours)
        style.configure("Treeview", rowheight=max(36, int(size * 2.7)))
        style.map("TButton", background=[("focus", "#b4c7f7")])

    def add_source(self):
        name = simpledialog.askstring("Source", "Source name:", parent=self.root)
        if name:
            url = simpledialog.askstring("Source", "HTTPS or file catalog URL:", parent=self.root)
            if url: self.call("source", name=name, url=url)

    def build_support(self):
        for label, command in (("Device diagnostics", self.devices), ("Export support bundle…", self.bundle), ("Create recovery snapshot…", self.snapshot), ("Restore snapshot…", self.restore), ("Start safe mode next login", self.safe)):
            ttk.Button(self.support_frame, text=label, command=command).pack(anchor="w", pady=8)
        ttk.Label(self.support_frame, text="Logs appear in app details. Support bundles omit app documents and file grants.").pack(anchor="w", pady=12)

    def devices(self):
        messagebox.showinfo("Device diagnostics", json.dumps(self.client.call("devices"), indent=2), parent=self.root)

    def bundle(self):
        path = filedialog.asksaveasfilename(parent=self.root, initialfile="ruxeonrx-support.zip", defaultextension=".zip")
        if path: self.call("bundle", path=path)

    def snapshot(self):
        name = simpledialog.askstring("Recovery", "Snapshot name:", parent=self.root)
        if name: self.call("snapshot", name=name)

    def restore(self):
        names = self.client.call("snapshots")
        name = simpledialog.askstring("Recovery", "Choose snapshot: " + ", ".join(names), parent=self.root)
        if name and messagebox.askyesno("Restore", "Replace managed state from this snapshot?", parent=self.root):
            self.call("restore", name=name); self.refresh()

    def safe(self):
        (Path(os.environ["RX_STATE"]) / "safe-mode").touch()
        self.status.set("Safe mode selected for the next login. Close the VM and restart.")

    def power(self):
        if messagebox.askyesno("Power", "Shut down RuxeonRX?", parent=self.root):
            import subprocess
            subprocess.Popen(["/usr/bin/sudo", "/sbin/poweroff"])

    def poll(self):
        try:
            for request in self.client.call("pending"):
                if request["id"] in self.prompting: continue
                self.prompting.add(request["id"])
                self.root.lift()
                allowed = messagebox.askyesno("RuxeonRX permission", request["app_id"] + " requests " + request["capability"] + ". Allow?", parent=self.root)
                path = ""
                if allowed and request["capability"] == "files":
                    path = filedialog.askopenfilename(parent=self.root)
                    allowed = bool(path)
                self.call("answer", id=request["id"], allowed=allowed, path=path)
                self.refresh_permissions()
            entries = self.client.call("notifications")
            self.notification_text.configure(state="normal"); self.notification_text.delete("1.0", "end")
            self.notification_text.insert("1.0", "\n\n".join(item["title"] + ": " + item["body"] for item in entries))
            self.notification_text.configure(state="disabled")
            if entries: self.status.set(entries[-1]["title"] + ": " + entries[-1]["body"])
        except Exception as error: self.status.set("Service disconnected: " + str(error))
        self.root.after(500, self.poll)

    def ready(self):
        if self.root.winfo_viewable() and self.client.call("health")["healthy"]:
            print("RX_GRAPHICAL_SESSION=ready", flush=True)
            Path(os.environ["RX_RUNTIME"], "graphical-ready").write_text("ready\n")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Desktop().run()
