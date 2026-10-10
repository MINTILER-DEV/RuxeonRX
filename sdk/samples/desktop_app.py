"""Real native Tk application exercising the file and notification portals."""
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from rxipc import Client

root = tk.Tk()
root.title("RX Notes")
root.geometry("600x400")
client = Client(Path(os.environ["RX_PORTAL_DIR"]) / "portal.sock")
token = os.environ["RX_TOKEN"]
status = tk.StringVar(value="Choose a file using the RuxeonRX portal.")
text = tk.Text(root, wrap="word", font=("DejaVu Sans", 12))


def request(capability):
    request_id = client.call("request", token=token, capability=capability)
    status.set("Waiting for permission in the RuxeonRX shell…")
    def poll():
        answer = client.call("result", token=token, request_id=request_id)
        if answer.get("pending"):
            root.after(200, poll)
        else:
            status.set(answer.get("message", "Completed"))
            if "content" in answer:
                text.delete("1.0", "end")
                text.insert("1.0", answer["content"])
    root.after(200, poll)


toolbar = ttk.Frame(root, padding=12)
toolbar.pack(fill="x")
ttk.Button(toolbar, text="Open file…", command=lambda: request("files")).pack(side="left", padx=4)
ttk.Button(toolbar, text="Send notification", command=lambda: request("notifications")).pack(side="left", padx=4)
text.pack(fill="both", expand=True, padx=12)
ttk.Label(root, textvariable=status, padding=12).pack(fill="x")
root.mainloop()
