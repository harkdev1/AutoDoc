from datetime import datetime
import json
import os
from pathlib import Path
import time
import threading
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter import filedialog

try:
    from . import public_cli
    from .public_vibe import VibeCoder
except ImportError:
    import public_cli
    from public_vibe import VibeCoder

try:
    from google import genai
except ImportError:
    genai = None


SETTINGS_FILE = public_cli.STATE_DIR / "settings.json"
UPDATE_API_URL = os.getenv(
    "AUTODOC_UPDATE_API_URL",
    "https://api.github.com/repos/harkdev1/AutoDoc-Public-Edition/releases/latest",
)
GITHUB_CLIENT_ID = os.getenv("AUTODOC_GITHUB_CLIENT_ID", "")


class PublicApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoDoc Public Edition")
        self.geometry("980x640")
        self.minsize(760, 520)
        self.configure(bg="#f5f7fb")
        self.session_started_at = None
        self.session = None
        self.sidebar_open = True
        self.nav_buttons = []
        self.settings = self.load_settings()
        self.configure_styles()
        self.build_layout()
        self.refresh_dashboard()

    def configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#f4f6fb")
        style.configure("Sidebar.TFrame", background="#111827")
        style.configure("Sidebar.TLabel", background="#111827", foreground="#dbe5f5")
        style.configure("Title.TLabel", background="#f4f6fb", foreground="#111827", font=("Segoe UI", 27, "bold"))
        style.configure("Subtitle.TLabel", background="#f4f6fb", foreground="#64748b", font=("Segoe UI", 10))
        style.configure("Topbar.TFrame", background="#ffffff")
        style.configure("Topbar.TLabel", background="#ffffff", foreground="#334155", font=("Segoe UI", 10, "bold"))
        style.configure("Timer.TLabel", background="#ffffff", foreground="#287a63", font=("Segoe UI", 11, "bold"))
        style.configure("Card.TFrame", background="#ffffff", relief="solid", borderwidth=1)
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 11, "bold"))
        style.configure("CardValue.TLabel", background="#ffffff", foreground="#287a63", font=("Segoe UI", 25, "bold"))
        style.configure("Body.TLabel", background="#ffffff", foreground="#42506a", font=("Segoe UI", 10))
        style.configure("Nav.TButton", background="#111827", foreground="#dbe5f5", borderwidth=0, anchor="w", padding=13, font=("Segoe UI", 10, "bold"))
        style.map("Nav.TButton", background=[("active", "#253451")])
        style.configure("Primary.TButton", background="#287a63", foreground="#ffffff", padding=11, borderwidth=0, font=("Segoe UI", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#1f624f")])
        style.configure("Secondary.TButton", background="#e8edf5", foreground="#263754", padding=9, borderwidth=0)

    def build_layout(self):
        self.sidebar = ttk.Frame(self, style="Sidebar.TFrame", width=230)
        sidebar = self.sidebar
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="AutoDoc", style="Sidebar.TLabel", font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=22, pady=(28, 2))
        ttk.Label(sidebar, text="PUBLIC EDITION", style="Sidebar.TLabel", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24, pady=(0, 35))
        for label, page in (("Dashboard", self.show_dashboard), ("Session", self.show_session), ("Manual Log", self.show_manual_log), ("Logs", self.show_logs), ("Vibe Code", self.show_vibe_code), ("Settings", self.show_settings)):
            button = ttk.Button(sidebar, text=label, style="Nav.TButton", command=page)
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons.append((button, label))
        self.project_button = ttk.Button(sidebar, text="Choose project", style="Nav.TButton", command=self.choose_project)
        self.project_button.pack(fill="x", padx=10, pady=(18, 2))
        self.sidebar_note = ttk.Label(sidebar, text="LOCAL-FIRST\nNo API key required", style="Sidebar.TLabel", justify="left")
        self.sidebar_note.pack(side="bottom", anchor="w", padx=24, pady=24)

        self.content = ttk.Frame(self, style="App.TFrame", padding=32)
        self.content.pack(side="left", fill="both", expand=True)
        topbar = ttk.Frame(self.content, style="Topbar.TFrame", padding=(14, 10))
        topbar.pack(fill="x", pady=(0, 24))
        ttk.Button(topbar, text="Menu", style="Secondary.TButton", command=self.toggle_sidebar).pack(side="left")
        self.timer_label = ttk.Label(topbar, text="No active session", style="Timer.TLabel")
        self.timer_label.pack(side="right")
        self.page_content = ttk.Frame(self.content, style="App.TFrame")
        self.page_content.pack(fill="both", expand=True)
        self.show_dashboard()
        self.update_timer()

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
        self.sidebar.configure(width=230 if self.sidebar_open else 58)
        for button, label in self.nav_buttons:
            button.configure(text=label if self.sidebar_open else label[:1])
        self.project_button.configure(text="Choose project" if self.sidebar_open else "+")
        self.sidebar_note.configure(text="LOCAL-FIRST\nNo API key required" if self.sidebar_open else "LOCAL")

    def clear_content(self):
        for child in self.page_content.winfo_children():
            child.destroy()

    def page_header(self, title, subtitle):
        ttk.Label(self.page_content, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.page_content, text=subtitle, style="Subtitle.TLabel").pack(anchor="w", pady=(4, 24))

    def show_dashboard(self):
        self.clear_content()
        self.page_header("Good to see you.", "Your engineering workspace, kept simple and local.")
        stats = public_cli.load_stats()
        cards = ttk.Frame(self.page_content, style="App.TFrame")
        cards.pack(fill="x")
        values = (("Sessions", stats["total_sessions"]), ("Minutes", stats["total_minutes"]), ("Days logged", len(stats["days_logged"])))
        for title, value in values:
            card = ttk.Frame(cards, style="Card.TFrame", padding=18)
            card.pack(side="left", fill="x", expand=True, padx=(0, 12))
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(card, text=str(value), style="CardValue.TLabel").pack(anchor="w", pady=(10, 0))

        activity = ttk.Frame(self.page_content, style="Card.TFrame", padding=22)
        activity.pack(fill="both", expand=True, pady=(22, 0))
        ttk.Label(activity, text="Workspace status", style="CardTitle.TLabel").pack(anchor="w")
        active = public_cli.SESSION_FILE.exists()
        status = "A session is in progress." if active else "Ready for a focused session."
        ttk.Label(activity, text=status, style="Body.TLabel").pack(anchor="w", pady=(10, 18))
        ttk.Label(activity, text=f"Project folder: {Path.cwd()}", style="Body.TLabel", wraplength=620).pack(anchor="w", pady=(0, 18))
        ttk.Button(activity, text="Open Session", style="Primary.TButton", command=self.show_session).pack(anchor="w")

    def choose_project(self):
        project = filedialog.askdirectory(title="Choose an AutoDoc project folder", initialdir=str(Path.cwd()))
        if project:
            os.chdir(project)
            public_cli.STATE_DIR = Path(project) / ".autodoc-public"
            public_cli.SESSION_FILE = public_cli.STATE_DIR / "session.json"
            public_cli.STATS_FILE = public_cli.STATE_DIR / "stats.json"
            public_cli.LOG_DIR = Path(project) / "logs"
            public_cli.SCREENSHOT_DIR = Path(project) / "screenshots"
            global SETTINGS_FILE
            SETTINGS_FILE = public_cli.STATE_DIR / "settings.json"
            self.settings = self.load_settings()
            self.show_dashboard()

    def show_session(self):
        self.clear_content()
        self.page_header("Focus session", "Capture the work while it is happening.")
        form = ttk.Frame(self.page_content, style="Card.TFrame", padding=24)
        form.pack(fill="x")
        self.goal = tk.StringVar()
        self.done = tk.StringVar()
        self.notes = tk.StringVar()
        self.planned = tk.IntVar(value=60)
        for label, variable in (("Session goal", self.goal), ("Definition of done", self.done), ("Notes", self.notes)):
            ttk.Label(form, text=label, style="Body.TLabel").pack(anchor="w", pady=(0, 4))
            ttk.Entry(form, textvariable=variable).pack(fill="x", pady=(0, 14))
        ttk.Label(form, text="Planned minutes", style="Body.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Spinbox(form, from_=1, to=1440, textvariable=self.planned, width=10).pack(anchor="w", pady=(0, 20))
        if public_cli.SESSION_FILE.exists():
            ttk.Button(form, text="Finish session", style="Primary.TButton", command=self.finish_session).pack(anchor="w")
            ttk.Label(form, text="Active session found. Finish it to write the Markdown log.", style="Body.TLabel").pack(anchor="w", pady=(12, 0))
        else:
            ttk.Button(form, text="Start session", style="Primary.TButton", command=self.start_session).pack(anchor="w")

    def start_session(self):
        public_cli.STATE_DIR.mkdir(exist_ok=True)
        session = {"start_time": datetime.now().isoformat(timespec="seconds"), "goal": self.goal.get(), "definition_of_done": self.done.get(), "blockers": "", "planned_minutes": self.planned.get()}
        public_cli.SESSION_FILE.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
        messagebox.showinfo("Session started", "Your focus session is now active.")
        self.update_timer()
        self.show_session()

    def finish_session(self):
        try:
            session = json.loads(public_cli.SESSION_FILE.read_text(encoding="utf-8"))
            start_time = datetime.fromisoformat(session["start_time"])
            end_time = datetime.now()
            duration = max(0, int((end_time - start_time).total_seconds() / 60))
            date_str = end_time.strftime("%Y-%m-%d")
            notes = self.notes.get()
            summary = self.generate_summary(notes)
            entry = f"\n---\n\n## Public Session - {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}\n### Goal\n{session['goal'] or 'Not specified'}\n\n### Definition of Done\n{session['definition_of_done'] or 'Not specified'}\n\n### Notes\n{self.notes.get() or 'None'}\n\n### Duration\n{duration} minutes (planned: {session['planned_minutes']} minutes)\n"
            entry = entry.replace("### Notes\n" + (notes or "None"), "### AI Summary\n" + summary + "\n\n### Notes\n" + (notes or "None"))
            log_file = public_cli.append_log(entry, date_str)
            public_cli.record_session(date_str, duration)
            public_cli.SESSION_FILE.unlink()
            self.update_timer()
            messagebox.showinfo("Session saved", f"Markdown log written to {log_file}")
            self.show_dashboard()
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Could not finish session", str(error))

    def load_settings(self):
        if not SETTINGS_FILE.exists():
            return {"gemini_api_key": "", "github_username": ""}
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"gemini_api_key": "", "github_username": ""}

    def generate_summary(self, notes):
        if not notes or not self.settings.get("gemini_api_key") or genai is None:
            return "AI summary unavailable; local notes preserved."
        try:
            client = genai.Client(api_key=self.settings["gemini_api_key"])
            prompt = "Summarize these engineering notes in 2-4 concise sentences:\n\n" + notes
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return response.text.strip()
        except Exception:
            return "AI summary unavailable; local notes preserved."

    def show_manual_log(self):
        self.clear_content()
        self.page_header("Manual log", "Record one piece of work without starting an ongoing session.")
        form = ttk.Frame(self.page_content, style="Card.TFrame", padding=24)
        form.pack(fill="both", expand=True)
        self.manual_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.manual_start = tk.StringVar(value="")
        self.manual_end = tk.StringVar(value="")
        self.manual_title = tk.StringVar()
        for label, variable in (("Date (YYYY-MM-DD)", self.manual_date), ("Start time (optional)", self.manual_start), ("End time (optional)", self.manual_end), ("Title", self.manual_title)):
            ttk.Label(form, text=label, style="Body.TLabel").pack(anchor="w", pady=(0, 4))
            ttk.Entry(form, textvariable=variable).pack(fill="x", pady=(0, 12))
        ttk.Label(form, text="What happened?", style="Body.TLabel").pack(anchor="w", pady=(0, 4))
        self.manual_notes = tk.Text(form, height=8, wrap="word", font=("Segoe UI", 10))
        self.manual_notes.pack(fill="both", expand=True, pady=(0, 14))
        ttk.Button(form, text="Create reviewed log", style="Primary.TButton", command=self.create_manual_log).pack(anchor="w")

    def create_manual_log(self):
        try:
            date_str = datetime.strptime(self.manual_date.get().strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Manual log", "Use a date in YYYY-MM-DD format.")
            return
        notes = self.manual_notes.get("1.0", "end").strip()
        if not notes:
            messagebox.showwarning("Manual log", "Add some notes before creating the log.")
            return
        start = self.manual_start.get().strip() or "Not specified"
        end = self.manual_end.get().strip() or "Not specified"
        title = self.manual_title.get().strip() or "Manual work log"
        summary = self.generate_summary(notes)
        review = self.open_review_dialog(summary)
        if review is None:
            return
        entry = f"\n---\n\n## {title}\n### Time\n{start} to {end}\n\n### AI Summary\n{summary}\n\n### Notes\n{notes}\n\n### Human Review\n{review}\n"
        log_file = public_cli.append_log(entry, date_str)
        messagebox.showinfo("Manual log saved", f"Log written to {log_file}")
        self.show_logs()

    def open_review_dialog(self, summary):
        dialog = tk.Toplevel(self)
        dialog.title("Human review")
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text="Review the AI-assisted summary before saving.", padding=16).pack(anchor="w")
        preview = tk.Text(dialog, width=80, height=10, wrap="word")
        preview.insert("1.0", summary)
        preview.pack(padx=16, pady=(0, 12))
        decision = {"value": None}
        buttons = ttk.Frame(dialog, padding=(16, 0, 16, 16))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Approve and save", style="Primary.TButton", command=lambda: self.finish_review(dialog, preview, decision)).pack(side="right", padx=(0, 8))
        self.wait_window(dialog)
        return decision["value"]

    @staticmethod
    def finish_review(dialog, preview, decision):
        decision["value"] = preview.get("1.0", "end").strip() or "Approved; no review notes."
        dialog.destroy()

    def show_logs(self):
        self.clear_content()
        self.page_header("Logs", "Read every local Markdown record inside AutoDoc.")
        toolbar = ttk.Frame(self.page_content, style="App.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Sync to GitHub", style="Secondary.TButton", command=self.sync_to_github).pack(side="right")
        body = ttk.Frame(self.page_content, style="App.TFrame")
        body.pack(fill="both", expand=True)
        files = sorted(public_cli.LOG_DIR.glob("*.md"), reverse=True) if public_cli.LOG_DIR.exists() else []
        self.log_list = tk.Listbox(body, width=28, exportselection=False)
        self.log_list.pack(side="left", fill="y")
        self.log_view = tk.Text(body, wrap="word", state="disabled", font=("Consolas", 10))
        self.log_view.pack(side="left", fill="both", expand=True, padx=(12, 0))
        for path in files:
            self.log_list.insert("end", path.name)
        self.log_paths = files
        self.log_list.bind("<<ListboxSelect>>", self.display_selected_log)
        if files:
            self.log_list.selection_set(0)
            self.display_selected_log()
        else:
            self.set_log_view("No Markdown logs yet. Create a manual log or finish a session.")

    def set_log_view(self, text):
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.insert("1.0", text)
        self.log_view.configure(state="disabled")

    def display_selected_log(self, _event=None):
        selected = self.log_list.curselection()
        if selected:
            self.set_log_view(self.log_paths[selected[0]].read_text(encoding="utf-8"))

    def sync_to_github(self):
        try:
            status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            messagebox.showerror("GitHub sync", f"Could not inspect this project: {error}")
            return
        changes = status.stdout.strip() or "No local changes detected."
        if not messagebox.askyesno("Review GitHub sync", f"Files currently changed:\n\n{changes}\n\nReview complete? Continue to stage logs and sync?\nThis is step 1 of 2."):
            return
        if not messagebox.askyesno("Confirm GitHub sync", "Stage Markdown logs, create a commit, and push to the configured remote?\n\nThis is step 2 of 2."):
            return
        try:
            subprocess.run(["git", "add", "logs"], check=True)
            subprocess.run(["git", "commit", "-m", "AutoDoc public logs"], check=True)
            subprocess.run(["git", "push"], check=True)
            messagebox.showinfo("GitHub sync", "Logs synced successfully.")
        except (OSError, subprocess.CalledProcessError) as error:
            messagebox.showerror("GitHub sync failed", str(error))

    def show_settings(self):
        self.clear_content()
        self.page_header("Settings", "Optional integrations stay under your control.")
        panel = ttk.Frame(self.page_content, style="Card.TFrame", padding=24)
        panel.pack(fill="x")
        ttk.Label(panel, text="Gemini API key", style="Body.TLabel").pack(anchor="w", pady=(0, 4))
        self.api_key = tk.StringVar(value=self.settings.get("gemini_api_key", ""))
        ttk.Entry(panel, textvariable=self.api_key, show="*").pack(fill="x", pady=(0, 8))
        ttk.Label(panel, text="Optional. Your key is saved only in this project's .autodoc-public folder.", style="Body.TLabel").pack(anchor="w", pady=(0, 18))
        ttk.Label(panel, text="GitHub OAuth client ID", style="Body.TLabel").pack(anchor="w", pady=(0, 4))
        self.github_client_id = tk.StringVar(value=self.settings.get("github_client_id", GITHUB_CLIENT_ID))
        ttk.Entry(panel, textvariable=self.github_client_id).pack(fill="x", pady=(0, 8))
        ttk.Label(panel, text="Optional. Use a public GitHub OAuth App client ID for device sign-in.", style="Body.TLabel").pack(anchor="w", pady=(0, 18))
        ttk.Button(panel, text="Save settings", style="Primary.TButton", command=self.save_settings).pack(anchor="w")

        github = ttk.Frame(self.page_content, style="Card.TFrame", padding=24)
        github.pack(fill="x", pady=(18, 0))
        ttk.Label(github, text="GitHub", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(github, text="Sign in is optional and requires a configured GitHub OAuth app.", style="Body.TLabel").pack(anchor="w", pady=(8, 12))
        ttk.Button(github, text="Open GitHub sign-in", style="Secondary.TButton", command=self.github_sign_in).pack(anchor="w")

        updates = ttk.Frame(self.page_content, style="Card.TFrame", padding=24)
        updates.pack(fill="x", pady=(18, 0))
        ttk.Label(updates, text="Updates", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(updates, text="Check manually whenever you choose. Nothing updates automatically.", style="Body.TLabel").pack(anchor="w", pady=(8, 12))
        ttk.Button(updates, text="Check for updates", style="Secondary.TButton", command=self.check_for_updates).pack(anchor="w")

    def show_vibe_code(self):
        self.clear_content()
        self.page_header("Vibe Code", "Describe a feature. Review the proposal. Apply only what you approve.")
        panel = ttk.Frame(self.page_content, style="Card.TFrame", padding=24)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="What would you like to build?", style="CardTitle.TLabel").pack(anchor="w")
        self.vibe_request = tk.Text(panel, height=6, wrap="word", font=("Segoe UI", 10))
        self.vibe_request.pack(fill="x", pady=(10, 16))
        controls = ttk.Frame(panel, style="Card.TFrame")
        controls.pack(fill="x")
        self.vibe_mode = tk.StringVar(value="propose")
        ttk.Radiobutton(controls, text="Explain", variable=self.vibe_mode, value="explain").pack(side="left", padx=(0, 12))
        ttk.Radiobutton(controls, text="Propose changes", variable=self.vibe_mode, value="propose").pack(side="left", padx=(0, 12))
        ttk.Button(controls, text="Ask Gemini", style="Primary.TButton", command=self.ask_vibe).pack(side="right")
        ttk.Label(panel, text="Proposal preview", style="CardTitle.TLabel").pack(anchor="w", pady=(22, 8))
        self.vibe_output = tk.Text(panel, height=14, wrap="word", state="disabled", font=("Consolas", 9))
        self.vibe_output.pack(fill="both", expand=True)
        self.apply_vibe_button = ttk.Button(panel, text="Apply approved changes", style="Secondary.TButton", command=self.apply_vibe, state="disabled")
        self.apply_vibe_button.pack(anchor="w", pady=(14, 0))
        self.vibe_proposal = None

    def set_vibe_output(self, text):
        self.vibe_output.configure(state="normal")
        self.vibe_output.delete("1.0", "end")
        self.vibe_output.insert("1.0", text)
        self.vibe_output.configure(state="disabled")

    def ask_vibe(self):
        request = self.vibe_request.get("1.0", "end").strip()
        if not request:
            messagebox.showwarning("Vibe Code", "Describe the feature you want to build first.")
            return
        self.set_vibe_output("Gemini is reviewing the project...\n")
        threading.Thread(target=self.request_vibe, args=(request, self.vibe_mode.get()), daemon=True).start()

    def request_vibe(self, request, mode):
        try:
            coder = VibeCoder(Path.cwd(), self.settings.get("gemini_api_key", ""))
            proposal = coder.propose(request, mode)
            self.after(0, lambda: self.show_vibe_proposal(proposal))
        except Exception as error:
            self.after(0, lambda: self.set_vibe_output(f"Proposal failed:\n{error}"))

    def show_vibe_proposal(self, proposal):
        self.vibe_proposal = proposal
        files = "\n".join(f"- {item['action']}: {item['path']}" for item in proposal["files"])
        preview = f"{proposal.get('summary', 'Proposal ready.')}\n\nFiles:\n{files}\n\nNotes:\n{proposal.get('notes', 'None')}"
        self.set_vibe_output(preview)
        self.apply_vibe_button.configure(state="normal")

    def apply_vibe(self):
        if not self.vibe_proposal:
            return
        if not messagebox.askyesno("Apply changes", "Create a backup and apply this proposal?\n\nPython files will be syntax-checked afterward."):
            return
        try:
            coder = VibeCoder(Path.cwd(), self.settings.get("gemini_api_key", ""))
            changed, backup_dir = coder.apply(self.vibe_proposal)
            names = ", ".join(str(path.relative_to(Path.cwd())) for path in changed)
            messagebox.showinfo("Changes applied", f"Updated: {names}\nBackup: {backup_dir}")
            self.apply_vibe_button.configure(state="disabled")
        except Exception as error:
            messagebox.showerror("Changes rejected", str(error))

    def save_settings(self):
        public_cli.STATE_DIR.mkdir(exist_ok=True)
        self.settings["gemini_api_key"] = self.api_key.get().strip()
        self.settings["github_client_id"] = self.github_client_id.get().strip()
        SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2) + "\n", encoding="utf-8")
        messagebox.showinfo("Settings saved", "Your local settings were saved.")

    def github_sign_in(self):
        client_id = self.settings.get("github_client_id") or GITHUB_CLIENT_ID
        if not client_id:
            messagebox.showinfo("GitHub sign-in", "GitHub sign-in is optional. Configure AUTODOC_GITHUB_CLIENT_ID before enabling OAuth.")
            webbrowser.open("https://github.com/login")
            return
        threading.Thread(target=self.github_device_flow, args=(client_id,), daemon=True).start()

    def github_device_flow(self, client_id):
        try:
            device_request = urllib.request.Request(
                "https://github.com/login/device/code",
                data=urllib.parse.urlencode({"client_id": client_id, "scope": "read:user"}).encode(),
                headers={"Accept": "application/json", "User-Agent": "AutoDoc-Public"},
            )
            with urllib.request.urlopen(device_request, timeout=10) as response:
                device = json.loads(response.read().decode("utf-8"))
            self.after(0, lambda: self.show_device_code(device["user_code"], device["verification_uri"]))

            deadline = time.time() + int(device.get("expires_in", 900))
            interval = int(device.get("interval", 5))
            while time.time() < deadline:
                time.sleep(interval)
                token_request = urllib.request.Request(
                    "https://github.com/login/oauth/access_token",
                    data=urllib.parse.urlencode({
                        "client_id": client_id,
                        "device_code": device["device_code"],
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    }).encode(),
                    headers={"Accept": "application/json", "User-Agent": "AutoDoc-Public"},
                )
                with urllib.request.urlopen(token_request, timeout=10) as response:
                    token = json.loads(response.read().decode("utf-8"))
                if token.get("access_token"):
                    self.settings["github_access_token"] = token["access_token"]
                    SETTINGS_FILE.parent.mkdir(exist_ok=True)
                    SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2) + "\n", encoding="utf-8")
                    self.after(0, lambda: messagebox.showinfo("GitHub sign-in", "GitHub sign-in completed."))
                    return
                if token.get("error") not in ("authorization_pending", "slow_down"):
                    raise RuntimeError(token.get("error_description", "GitHub authorization failed."))
                if token.get("error") == "slow_down":
                    interval += 5
            raise RuntimeError("GitHub authorization timed out.")
        except (OSError, urllib.error.URLError, KeyError, ValueError, RuntimeError) as error:
            self.after(0, lambda: messagebox.showerror("GitHub sign-in failed", str(error)))

    def show_device_code(self, user_code, verification_uri):
        webbrowser.open(verification_uri)
        messagebox.showinfo("GitHub sign-in", f"Enter this code in your browser:\n\n{user_code}\n\nWaiting for authorization...")

    def check_for_updates(self):
        def request_release():
            try:
                request = urllib.request.Request(UPDATE_API_URL, headers={"User-Agent": "AutoDoc-Public"})
                with urllib.request.urlopen(request, timeout=8) as response:
                    release = json.loads(response.read().decode("utf-8"))
                version = release.get("tag_name", "latest")
                url = release.get("html_url", UPDATE_API_URL)
                self.after(0, lambda: self.show_release(version, url))
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
                self.after(0, lambda: messagebox.showerror("Update check failed", str(error)))

        threading.Thread(target=request_release, daemon=True).start()

    def show_release(self, version, url):
        if messagebox.askyesno("Update check", f"Latest public release: {version}\n\nOpen the release page?"):
            webbrowser.open(url)

    def refresh_dashboard(self):
        self.update_timer()

    def update_timer(self):
        if public_cli.SESSION_FILE.exists():
            try:
                session = json.loads(public_cli.SESSION_FILE.read_text(encoding="utf-8"))
                started = datetime.fromisoformat(session["start_time"])
                elapsed = max(0, int((datetime.now() - started).total_seconds()))
                planned = int(session.get("planned_minutes", 0))
                hours, remainder = divmod(elapsed, 3600)
                minutes, seconds = divmod(remainder, 60)
                timer = f"LIVE  {hours:02d}:{minutes:02d}:{seconds:02d}"
                if planned:
                    timer += f"  /  {planned} min"
                self.timer_label.configure(text=timer)
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.timer_label.configure(text="Session needs attention")
        else:
            self.timer_label.configure(text="No active session")
        self.after(1000, self.update_timer)


if __name__ == "__main__":
    app = PublicApp()
    app.mainloop()
