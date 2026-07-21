import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
import os
import re
import signal

class SiteWatchGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SiteWatch - Control Panel")
        self.root.geometry("500x420")
        self.root.resizable(False, False)
        self.root.configure(bg="#0f172a")

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        self.server_proc = None
        self.tunnel_proc = None
        self.running = False

        self.build_ui()

    def build_ui(self):
        bg = "#0f172a"
        card = "#1e293b"
        accent = "#2563eb"
        text = "#e2e8f0"
        muted = "#94a3b8"

        header = tk.Frame(self.root, bg=bg)
        header.pack(fill="x", pady=(15, 5))

        tk.Label(header, text="SiteWatch", font=("Segoe UI", 20, "bold"),
                 fg=accent, bg=bg).pack()
        tk.Label(header, text="Website Uptime Monitor", font=("Segoe UI", 10),
                 fg=muted, bg=bg).pack()

        status_frame = tk.Frame(self.root, bg=card, highlightbackground="#334155",
                                highlightthickness=1, bd=0)
        status_frame.pack(fill="x", padx=25, pady=(15, 10))

        self.status_dot = tk.Canvas(status_frame, width=14, height=14,
                                     bg=card, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(15, 8), pady=12)
        self.dot = self.status_dot.create_oval(2, 2, 12, 12, fill="#ef4444", outline="")

        self.status_label = tk.Label(status_frame, text="Stopped",
                                      font=("Segoe UI", 12, "bold"),
                                      fg="#ef4444", bg=card)
        self.status_label.pack(side="left", pady=12)

        url_frame = tk.Frame(self.root, bg=card, highlightbackground="#334155",
                             highlightthickness=1, bd=0)
        url_frame.pack(fill="x", padx=25, pady=(0, 10))

        tk.Label(url_frame, text="Public URL", font=("Segoe UI", 9),
                 fg=muted, bg=card, anchor="w").pack(fill="x", padx=15, pady=(8, 0))

        self.url_var = tk.StringVar(value="Not available")
        self.url_label = tk.Label(url_frame, textvariable=self.url_var,
                                   font=("Consolas", 11), fg="#38bdf8", bg=card,
                                   cursor="hand2", anchor="w", wraplength=420)
        self.url_label.pack(fill="x", padx=15, pady=(2, 10))
        self.url_label.bind("<Button-1>", self.copy_url)

        btn_frame = tk.Frame(self.root, bg=bg)
        btn_frame.pack(fill="x", padx=25, pady=(5, 5))

        self.start_btn = tk.Button(btn_frame, text="START", font=("Segoe UI", 12, "bold"),
                                    fg="white", bg="#22c55e", activebackground="#16a34a",
                                    activeforeground="white", relief="flat", bd=0,
                                    cursor="hand2", command=self.start_services, width=12)
        self.start_btn.pack(side="left", padx=(0, 8), ipady=6)

        self.stop_btn = tk.Button(btn_frame, text="STOP", font=("Segoe UI", 12, "bold"),
                                   fg="white", bg="#ef4444", activeforeground="white",
                                   activebackground="#dc2626", relief="flat", bd=0,
                                   cursor="hand2", command=self.stop_services,
                                   state="disabled", width=12)
        self.stop_btn.pack(side="left", ipady=6)

        log_frame = tk.Frame(self.root, bg=card, highlightbackground="#334155",
                             highlightthickness=1, bd=0)
        log_frame.pack(fill="both", expand=True, padx=25, pady=(5, 15))

        tk.Label(log_frame, text="Logs", font=("Segoe UI", 9),
                 fg=muted, bg=card, anchor="w").pack(fill="x", padx=10, pady=(5, 0))

        self.log_text = tk.Text(log_frame, font=("Consolas", 9), bg="#0f172a",
                                 fg=muted, insertbackground=muted, relief="flat",
                                 bd=0, height=5, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def log(self, msg):
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")

    def set_status(self, running):
        self.running = running
        if running:
            self.status_dot.itemconfig(self.dot, fill="#22c55e")
            self.status_label.config(text="Running", fg="#22c55e")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
        else:
            self.status_dot.itemconfig(self.dot, fill="#ef4444")
            self.status_label.config(text="Stopped", fg="#ef4444")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.url_var.set("Not available")

    def copy_url(self, event=None):
        url = self.url_var.get()
        if url and url != "Not available":
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.log("URL copied to clipboard!")

    def start_services(self):
        self.set_status(True)
        self.start_btn.config(state="disabled", text="Starting...")
        self.log("Starting server...")
        threading.Thread(target=self._start, daemon=True).start()

    def _start(self):
        try:
            project_dir = os.path.dirname(os.path.abspath(__file__))
            venv_python = os.path.join(project_dir, "venv", "Scripts", "python.exe")

            self.server_proc = subprocess.Popen(
                [venv_python, "-m", "uvicorn", "app.main:app",
                 "--host", "127.0.0.1", "--port", "9090"],
                cwd=project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            def read_server_output():
                for line in iter(self.server_proc.stdout.readline, b""):
                    text = line.decode("utf-8", errors="ignore").strip()
                    if text:
                        self.root.after(0, lambda t=text: self.log(f"[Server] {t}"))

            threading.Thread(target=read_server_output, daemon=True).start()
            self.root.after(0, lambda: self.log("Server started on port 9090"))
            self.root.after(0, lambda: self.log("Starting tunnel..."))

            cf_log = os.path.join(project_dir, "cf_tunnel.log")
            self.tunnel_proc = subprocess.Popen(
                [r"C:\cloudflared\cloudflared.exe", "tunnel", "--url", "http://localhost:9090"],
                cwd=project_dir,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            url = None
            start = time.time()
            for line in iter(self.tunnel_proc.stderr.readline, b""):
                text = line.decode("utf-8", errors="ignore")
                match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", text)
                if match:
                    url = match.group(0)
                    break
                if time.time() - start > 30:
                    break

            if url:
                self.root.after(0, lambda: self.url_var.set(url))
                self.root.after(0, lambda: self.log(f"Tunnel: {url}"))
                self.root.after(0, lambda: self.log("Ready! Click URL to copy."))
            else:
                self.root.after(0, lambda: self.log("Could not get tunnel URL."))
                self.root.after(0, lambda: self.url_var.set("Check if cloudflared is installed"))

            self.root.after(0, lambda: self.start_btn.config(text="START"))

        except Exception as e:
            self.root.after(0, lambda: self.log(f"Error: {e}"))
            self.root.after(0, lambda: self.set_status(False))

    def stop_services(self):
        self.log("Stopping...")
        threading.Thread(target=self._stop, daemon=True).start()

    def _stop(self):
        for proc in [self.tunnel_proc, self.server_proc]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    try:
                        proc.kill()
                    except:
                        pass

        self.server_proc = None
        self.tunnel_proc = None
        self.root.after(0, lambda: self.log("All services stopped."))
        self.root.after(0, lambda: self.set_status(False))

    def on_close(self):
        if self.running:
            self._stop()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

if __name__ == "__main__":
    app = SiteWatchGUI()
    app.run()
