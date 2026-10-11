"""Native GTK 4 Notes: scoped file/notification portals and private saved notes."""
import os
import concurrent.futures
from pathlib import Path
import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk
from rxipc import Client


class Notes(Adw.Application):
    def __init__(self):
        # Match RX's exported desktop-file identity for correct taskbar icons
        # and grouping, while keeping the portal/registry identity unchanged.
        GLib.set_prgname(os.environ["RX_APP_ID"])
        GLib.set_application_name(os.environ.get("RX_APP_NAME", "RX Notes"))
        super().__init__(application_id="ruxeonrx-" + os.environ["RX_APP_ID"], flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.client = Client(Path(os.environ["RX_PORTAL_DIR"]) / "portal.sock")
        self.token = os.environ["RX_TOKEN"]; self.seen = set(); self.pending = set(); self.poll_busy = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.connect("activate", self.activate)

    def activate(self, application):
        self.window = Adw.ApplicationWindow(application=self, title=os.environ.get("RX_APP_NAME", "RX Notes"), default_width=640, default_height=430)
        toolbar = Adw.ToolbarView(); header = Adw.HeaderBar(); toolbar.add_top_bar(header)
        for label, callback in (("Open file…", lambda: self.request("files")), ("Send notification", lambda: self.request("notifications")), ("Save locally", self.save)):
            button = Gtk.Button(label=label); button.connect("clicked", lambda unused, cb=callback: cb()); header.pack_start(button)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=18, bottom_margin=18, left_margin=18, right_margin=18, vexpand=True)
        content.append(Gtk.ScrolledWindow(child=self.text, vexpand=True))
        self.status = Gtk.Label(label="Open a file through the RX permission portal, or save a private note.", wrap=True, xalign=0, margin_start=18, margin_end=18, margin_bottom=12)
        content.append(self.status); toolbar.set_content(content); self.window.set_content(toolbar)
        saved = Path(os.environ["RX_DATA_DIR"]) / "note.txt"
        if saved.is_file(): self.text.get_buffer().set_text(saved.read_text(encoding="utf-8"))
        self.call("appearance", self.render_appearance, token=self.token)
        self.window.present(); GLib.timeout_add(500, self.intents)

    def render_appearance(self, values):
        scheme = values["color_scheme"]
        self.get_style_manager().set_color_scheme({"prefer-dark": Adw.ColorScheme.FORCE_DARK, "prefer-light": Adw.ColorScheme.FORCE_LIGHT}.get(scheme, Adw.ColorScheme.DEFAULT))

    def call(self, method, callback, **params):
        future = self.executor.submit(self.client.call, method, **params)
        def finished(result):
            def deliver():
                try: callback(result.result())
                except Exception as error: self.status.set_label(str(error))
                return False
            GLib.idle_add(deliver)
        future.add_done_callback(finished)

    def save(self):
        buffer = self.text.get_buffer()
        content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        target = Path(os.environ["RX_DATA_DIR"]) / "note.txt"
        temporary = target.with_suffix(".tmp"); temporary.write_text(content, encoding="utf-8"); temporary.replace(target)
        self.status.set_label("Saved to private app storage. Reset app data erases this note.")

    def request(self, capability):
        self.call("request", self.wait, token=self.token, capability=capability)

    def wait(self, identifier):
        self.pending.add(identifier)
        self.status.set_label("Waiting for your decision in the RuxeonRX permission dialog…")

    def intents(self):
        if self.poll_busy: return True
        self.poll_busy = True; pending = list(self.pending)
        def fetch():
            appearance = self.client.call("appearance", token=self.token)
            intents = self.client.call("intents", token=self.token)
            answers = [(identifier, self.client.call("result", token=self.token, request_id=identifier)) for identifier in pending]
            return appearance, intents, answers
        future = self.executor.submit(fetch)
        def finished(result):
            def deliver():
                self.poll_busy = False
                try:
                    appearance, intents, answers = result.result(); self.render_appearance(appearance)
                    for intent in intents:
                        if intent["id"] not in self.seen: self.seen.add(intent["id"]); self.wait(intent["id"])
                    for identifier, answer in answers:
                        if not answer.get("pending"):
                            self.pending.discard(identifier); self.status.set_label(answer.get("message", "Completed"))
                            if "content" in answer: self.text.get_buffer().set_text(answer["content"])
                except Exception as error: self.status.set_label(str(error))
                return False
            GLib.idle_add(deliver)
        future.add_done_callback(finished)
        return True


application = Notes()
try: result = application.run(sys.argv)
finally: application.executor.shutdown(wait=False, cancel_futures=True)
raise SystemExit(result)
