"""Native GTK 4 Notes: scoped file/notification portals and private saved notes."""
import os
from pathlib import Path
import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk
from rxipc import Client


class Notes(Adw.Application):
    def __init__(self):
        super().__init__(application_id=os.environ["RX_APP_ID"], flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.client = Client(Path(os.environ["RX_PORTAL_DIR"]) / "portal.sock")
        self.token = os.environ["RX_TOKEN"]; self.seen = set()
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
        self.window.present(); GLib.timeout_add(500, self.intents)

    def save(self):
        buffer = self.text.get_buffer()
        content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        target = Path(os.environ["RX_DATA_DIR"]) / "note.txt"
        temporary = target.with_suffix(".tmp"); temporary.write_text(content, encoding="utf-8"); temporary.replace(target)
        self.status.set_label("Saved to private app storage. Reset app data erases this note.")

    def request(self, capability):
        try: self.wait(self.client.call("request", token=self.token, capability=capability))
        except Exception as error: self.status.set_label(str(error))

    def wait(self, identifier):
        self.status.set_label("Waiting for your decision in the RuxeonRX permission dialog…")
        def poll():
            try: answer = self.client.call("result", token=self.token, request_id=identifier)
            except Exception as error: self.status.set_label(str(error)); return False
            if answer.get("pending"): return True
            self.status.set_label(answer.get("message", "Completed"))
            if "content" in answer: self.text.get_buffer().set_text(answer["content"])
            return False
        GLib.timeout_add(200, poll)

    def intents(self):
        try:
            for intent in self.client.call("intents", token=self.token):
                if intent["id"] not in self.seen: self.seen.add(intent["id"]); self.wait(intent["id"])
        except Exception as error: self.status.set_label(str(error))
        return True


raise SystemExit(Notes().run(sys.argv))
