"""
HaruxSky GUI - Turn the customizable Bluesky automation into a real desktop program.
Uses CustomTkinter for a modern look.
"""

import customtkinter as ctk
import threading
import os
import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path
import yaml


from .config import Config, load_config, DEFAULT_POST_PROMPT, DEFAULT_REPLY_PROMPT
from .utils import format_prompt
from .poster import run_posting
from .engager import run_engagement
from .llm import LLMClient
from .bsky import BskyClientWrapper


def get_user_config_path() -> Path:
    """Return a persistent user-writable location for config (works inside the .exe too)."""
    # Use %LOCALAPPDATA%\HaruxSky\config.yaml on Windows
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    config_dir = Path(local_app_data) / "HaruxSky"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yaml"


class HaruxSkyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HaruxSky")
        self.root.geometry("980x720")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_path = get_user_config_path()
        self.config: Config | None = None
        self.llm_client: LLMClient | None = None
        self.bsky_client: BskyClientWrapper | None = None
        self.stop_event = threading.Event()

        self.main_frame = None
        self.setup_frame = None
        self.loading_frame = None

        self._build_ui()
        self._load_or_show_setup()

    def _build_ui(self):
        # Top header bar (always visible)
        header = ctk.CTkFrame(self.root, height=60)
        header.pack(fill="x", padx=8, pady=(8, 4))
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="HaruxSky", font=ctk.CTkFont(size=26, weight="bold")).pack(side="left", padx=16)
        ctk.CTkLabel(header, text="AI that posts and replies like you on Bluesky", font=ctk.CTkFont(size=13)).pack(side="left", padx=8)

        self.status_bar = ctk.CTkLabel(header, text="Not connected", text_color="gray60")
        self.status_bar.pack(side="right", padx=16)

        # Prominent logout in header
        ctk.CTkButton(header, text="Log Out / Reconfigure Account", command=self._logout, width=180, fg_color="#805ad5", hover_color="#6b46c1").pack(side="right", padx=8)

        # Container for switching between setup and main
        self.content_frame = ctk.CTkFrame(self.root)
        self.content_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self._build_setup_screen()
        self._build_loading_screen()
        self._build_main_screen()

        # Initially show setup (we'll switch in _load_or_show_setup)
        self.setup_frame.pack(fill="both", expand=True)
        self.loading_frame.pack_forget()
        self.main_frame.pack_forget()

        # Processor removed - using direct self._log with root.after(0) like the working test buttons.

    def _build_setup_screen(self):
        """First screen: user puts in the details."""
        self.setup_frame = ctk.CTkFrame(self.content_frame)

        title = ctk.CTkLabel(self.setup_frame, text="Welcome to HaruxSky", font=ctk.CTkFont(size=22, weight="bold"))
        title.pack(pady=(40, 8))

        subtitle = ctk.CTkLabel(self.setup_frame, text="Enter your details to load up the program", font=ctk.CTkFont(size=14))
        subtitle.pack(pady=(0, 30))

        form = ctk.CTkFrame(self.setup_frame)
        form.pack(padx=60, pady=10, fill="x")

        ctk.CTkLabel(form, text="Bluesky Handle", anchor="w").pack(fill="x", padx=20, pady=(12, 2))
        self.setup_handle = ctk.CTkEntry(form, placeholder_text="yourname.bsky.social")
        self.setup_handle.pack(fill="x", padx=20, pady=2)

        ctk.CTkLabel(form, text="App Password (create one at bsky.app/settings/app-passwords)", anchor="w").pack(fill="x", padx=20, pady=(12, 2))
        self.setup_pass = ctk.CTkEntry(form, placeholder_text="xxxx-xxxx-xxxx-xxxx", show="*")
        self.setup_pass.pack(fill="x", padx=20, pady=2)

        ctk.CTkLabel(form, text="LLM API Key (xAI recommended)", anchor="w").pack(fill="x", padx=20, pady=(12, 2))
        self.setup_key = ctk.CTkEntry(form, placeholder_text="xai-...", show="*")
        self.setup_key.pack(fill="x", padx=20, pady=2)

        btn_frame = ctk.CTkFrame(self.setup_frame, fg_color="transparent")
        btn_frame.pack(pady=30)

        self.setup_btn = ctk.CTkButton(
            btn_frame,
            text="Save Details & Load the Program",
            command=self._complete_setup,
            height=42,
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.setup_btn.pack()

        note = ctk.CTkLabel(self.setup_frame, text="Your details are saved locally. The full controls, article sources, and live log will appear after this.", text_color="gray60")
        note.pack(pady=20)

    def _build_loading_screen(self):
        """Loading screen with spinner when the program 'loads up further'."""
        self.loading_frame = ctk.CTkFrame(self.content_frame)

        ctk.CTkLabel(self.loading_frame, text="HaruxSky", font=ctk.CTkFont(size=28, weight="bold")).pack(pady=(60, 10))

        self.loading_title = ctk.CTkLabel(self.loading_frame, text="Loading your program...", font=ctk.CTkFont(size=18))
        self.loading_title.pack(pady=10)

        # Indeterminate progress bar = the spinning thing
        self.loading_progress = ctk.CTkProgressBar(self.loading_frame, width=400, mode="indeterminate")
        self.loading_progress.pack(pady=20)
        self.loading_progress.start()

        # Status messages that update
        self.loading_status = ctk.CTkLabel(self.loading_frame, text="Initializing...", font=ctk.CTkFont(size=14))
        self.loading_status.pack(pady=10)

        # Extra spinner text for fun
        self.spinner_label = ctk.CTkLabel(self.loading_frame, text="⠋", font=ctk.CTkFont(size=24))
        self.spinner_label.pack(pady=10)

        # Start the text spinner animation
        self._start_spinner_animation()

        note = ctk.CTkLabel(self.loading_frame, text="Connecting to Bluesky and warming up the AI. This only takes a moment.", text_color="gray60")
        note.pack(pady=30)

    def _start_spinner_animation(self):
        """Simple rotating spinner using after()."""
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_index = 0
        self._animate_spinner()

    def _animate_spinner(self):
        if self.spinner_label and self.spinner_label.winfo_exists():
            self.spinner_label.configure(text=self.spinner_chars[self.spinner_index])
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
            self.root.after(80, self._animate_spinner)

    def _update_loading_status(self, text: str):
        """Thread-safe way to update loading text from worker."""
        self.root.after(0, lambda: self.loading_status.configure(text=text))

    def _build_main_screen(self):
        """The full program the user sees after entering details."""
        self.main_frame = ctk.CTkFrame(self.content_frame)

        # Center controls + sources + log (simplified UI, no side prompt editors)
        paned = ctk.CTkFrame(self.main_frame)
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        right = ctk.CTkFrame(paned)
        right.pack(fill="both", expand=True, padx=4, pady=4)

        ctk.CTkLabel(right, text="Run the Bot", font=ctk.CTkFont(weight="bold", size=15)).pack(anchor="w", padx=10, pady=(10, 4))

        mode_row = ctk.CTkFrame(right, fg_color="transparent")
        mode_row.pack(fill="x", padx=10)
        self.post_var = ctk.BooleanVar(value=True)
        self.engage_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(mode_row, text="Post articles", variable=self.post_var).pack(side="left")
        ctk.CTkCheckBox(mode_row, text="Send replies", variable=self.engage_var).pack(side="left", padx=12)

        counts_row = ctk.CTkFrame(right, fg_color="transparent")
        counts_row.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(counts_row, text="Articles to post:").pack(side="left")
        self.articles_num_var = ctk.StringVar(value="1")
        ctk.CTkEntry(counts_row, textvariable=self.articles_num_var, width=50).pack(side="left", padx=4)
        ctk.CTkLabel(counts_row, text="   Replies to send:").pack(side="left", padx=(12,0))
        self.replies_num_var = ctk.StringVar(value="1")
        ctk.CTkEntry(counts_row, textvariable=self.replies_num_var, width=50).pack(side="left", padx=4)

        self.dry_run_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(right, text="Dry Run (preview only — nothing is posted)", variable=self.dry_run_var).pack(anchor="w", padx=10, pady=6)

        self.attach_image_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(right, text="Attach image from article if available", variable=self.attach_image_var).pack(anchor="w", padx=10, pady=6)

        self.activity_label = ctk.CTkLabel(right, text="Current activity: Idle", text_color="gray")
        self.activity_label.pack(anchor="w", padx=10, pady=4)

        # Feeds - this is where articles come from
        ctk.CTkLabel(right, text="Article Sources (RSS feeds - one URL per line)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.feeds_text = ctk.CTkTextbox(right, height=70)
        self.feeds_text.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(right, text="Save after editing to use new sources", font=ctk.CTkFont(size=9, slant="italic")).pack(anchor="w", padx=10, pady=(0,4))

        self.run_button = ctk.CTkButton(right, text="▶ Run Now", command=self._run_bot, height=38, font=ctk.CTkFont(size=14))
        self.run_button.pack(fill="x", padx=10, pady=6)

        self.stop_button = ctk.CTkButton(right, text="■ Stop", command=self._stop_run, height=32, fg_color="#c53030", hover_color="#9b2c2c")
        self.stop_button.pack(fill="x", padx=10, pady=(0,6))
        self.stop_button.configure(state="disabled")

        ctk.CTkButton(right, text="Save Settings", command=self._save_config).pack(fill="x", padx=10, pady=2)

        # Test buttons to prove it's actually working
        test_frame = ctk.CTkFrame(right, fg_color="transparent")
        test_frame.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(test_frame, text="Test: Fetch & Generate from Feeds", command=self._test_fetch_and_generate, width=180).pack(side="left", padx=2)
        ctk.CTkButton(test_frame, text="Test: Generate Reply to Random", command=self._test_generate_reply, width=180).pack(side="left", padx=2)

        # Live log — "they see everything"
        log_header = ctk.CTkFrame(right, fg_color="transparent")
        log_header.pack(fill="x", padx=10, pady=(12, 2))
        ctk.CTkLabel(log_header, text="Live Activity Log", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(log_header, text="Clear Log", command=self._clear_log, width=80).pack(side="right")

        self.log_text = ctk.CTkTextbox(right, height=220, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=4)

        # Bottom info
        footer = ctk.CTkFrame(right, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(footer, text="Open Config Folder", command=self._open_config_folder, width=130).pack(side="left")
        ctk.CTkButton(footer, text="Log Out / Reconfigure", command=self._logout, width=150, fg_color="#805ad5").pack(side="left", padx=6)

    def _load_or_show_setup(self):
        """Decide: show setup screen or jump straight to the full program."""
        if self.config_path.exists():
            try:
                self.config = load_config(str(self.config_path))
                self._populate_main_from_config()
                self._switch_to_main()
                self._log("Loaded your saved settings. Program is ready.")
                self._try_connect_in_background()
            except Exception as e:
                self._log(f"Could not load previous config: {e}")
                self._switch_to_setup()
        else:
            self._switch_to_setup()

    def _switch_to_setup(self):
        if self.main_frame:
            self.main_frame.pack_forget()
        if self.loading_frame:
            self.loading_frame.pack_forget()
        self.setup_frame.pack(fill="both", expand=True)
        self.status_bar.configure(text="Setup required")

    def _switch_to_loading(self):
        if self.setup_frame:
            self.setup_frame.pack_forget()
        if self.main_frame:
            self.main_frame.pack_forget()
        self.loading_frame.pack(fill="both", expand=True)
        self.status_bar.configure(text="Loading...")

    def _switch_to_main(self):
        if self.setup_frame:
            self.setup_frame.pack_forget()
        if self.loading_frame:
            self.loading_frame.pack_forget()
        self.main_frame.pack(fill="both", expand=True)
        handle = self.config.bluesky.get('handle', '') if self.config else ''
        self.status_bar.configure(text=f"Ready — connected as @{handle}")
        # Add a nice "loaded" banner so user sees everything is up
        if not hasattr(self, '_main_banner'):
            self._main_banner = ctk.CTkLabel(self.main_frame, text="✨ HaruxSky loaded. Edit article sources and counts below, attach image if wanted, then Run. Live log shows every fetch, LLM step, and post.", text_color="#4ade80")
            self._main_banner.pack(fill="x", padx=10, pady=(4,0), before=self.main_frame.winfo_children()[0] if self.main_frame.winfo_children() else None)

    def _complete_setup(self):
        """User clicked the big button. Show spinning loading while we load up the full program."""
        handle = self.setup_handle.get().strip()
        app_pass = self.setup_pass.get().strip()
        api_key = self.setup_key.get().strip()

        if not handle or not app_pass or not api_key:
            messagebox.showwarning("Missing info", "Please fill in handle, app password, and API key.")
            return

        # Prepare the config data
        data = {
            "bluesky": {"handle": handle, "app_password": app_pass},
            "llm": {"provider": "xai", "api_key": api_key, "model": "grok-3"},
            "posting": {"enabled": True, "feeds": ["https://www.technologyreview.com/feed/", "https://feeds.arstechnica.com/arstechnica/index"], "max_posts_per_run": 1, "generate_images": True},
            "engagement": {"enabled": True, "replies_per_run": 20, "min_likes_for_reply": 0, "skip_political": True},
            "prompts": {
                "style": "default",
                "post": {"prompt": DEFAULT_POST_PROMPT},
                "reply": {"prompt": DEFAULT_REPLY_PROMPT},
            }
        }

        # Switch to loading screen with spinner
        self._switch_to_loading()
        self._update_loading_status("Saving your settings...")

        def worker():
            try:
                # Step 1: Save
                import time
                time.sleep(0.4)  # small pause so user sees the message
                with open(self.config_path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, sort_keys=False)
                self.config = load_config(str(self.config_path))
                self.root.after(0, lambda: self._update_loading_status("Connecting to Bluesky..."))

                # Step 2: Init clients (this is the "loads up further")
                self.llm_client = LLMClient(self.config.llm)
                self.root.after(0, lambda: self._update_loading_status("Warming up the AI..."))
                time.sleep(0.3)

                self.bsky_client = BskyClientWrapper(self.config)
                self.root.after(0, lambda: self._update_loading_status("Loading your custom voice..."))
                time.sleep(0.4)

                # Populate main widgets from the new config
                self.root.after(0, self._populate_main_from_config)

                # Done - switch to full program
                self.root.after(0, lambda: self._update_loading_status("Almost ready..."))
                time.sleep(0.3)
                self.root.after(0, self._finish_loading_and_show_main)

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Failed to load", f"Error while loading the program:\n{e}"))
                self.root.after(0, self._switch_to_setup)
                self.root.after(0, lambda: self._log(f"Load failed: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_loading_and_show_main(self):
        """Called when loading spinner is done."""
        self.loading_progress.stop()
        self._switch_to_main()
        self.status_bar.configure(text=f"Ready — connected as @{self.config.bluesky.get('handle', '')}")
        self._log("Program loaded successfully. Set article sources and run counts, then hit Run. The log shows the real work live.")
        # They now "see everything" in the main view

    def _populate_main_from_config(self):
        if not self.config:
            return
        self.post_var.set(self.config.posting.enabled)
        self.engage_var.set(self.config.engagement.enabled)

        if hasattr(self, 'articles_num_var'):
            self.articles_num_var.set(str(getattr(self.config.posting, 'max_posts_per_run', 1)))

        if hasattr(self, 'replies_num_var'):
            self.replies_num_var.set(str(self.config.engagement.replies_per_run))

        if hasattr(self, 'attach_image_var'):
            self.attach_image_var.set(self.config.posting.generate_images)

        if hasattr(self, 'feeds_text'):
            self.feeds_text.delete("1.0", "end")
            for f in getattr(self.config.posting, 'feeds', []):
                self.feeds_text.insert("end", f + "\n")

    def _log(self, message: str):
        """Thread-safe logging to the activity log. Always schedules on main thread."""
        def do_log():
            try:
                if hasattr(self, 'log_text') and self.log_text:
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", message + "\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
                    self.root.update_idletasks()  # force UI refresh
            except Exception as log_err:
                # last resort, don't crash the worker
                pass
        self.root.after(0, do_log)

    # Queue processor removed - using direct thread-safe _log with root.after(0) like the working test buttons.

    def _try_connect_in_background(self):
        """For existing config case: connect clients in background so status updates."""
        def worker():
            try:
                self.llm_client = LLMClient(self.config.llm)
                self.bsky_client = BskyClientWrapper(self.config)
                self.root.after(0, lambda: self.status_bar.configure(text=f"Ready — connected as @{self.config.bluesky.get('handle', '')}"))
                self._log("Program ready. Customize sources and counts, then run on the right.")
            except Exception as e:
                self.root.after(0, lambda: self.status_bar.configure(text="Ready (connect may need retry)"))
                self._log(f"Note: Could not connect on startup ({e}). Use dry-run first.")

        threading.Thread(target=worker, daemon=True).start()

    def _save_config(self):
        """Save only the customizable parts (prompts + run toggles). Credentials were already saved in setup."""
        if not self.config:
            messagebox.showwarning("Not ready", "Please complete setup first.")
            return
        try:
            data = {
                "bluesky": self.config.bluesky,   # keep original credentials
                "llm": self.config.llm.model_dump() if hasattr(self.config.llm, 'model_dump') else {"provider": "xai", "api_key": self.config.llm.api_key, "model": self.config.llm.model},
                "posting": {
                    "enabled": self.post_var.get(),
                    "feeds": [line.strip() for line in self.feeds_text.get("1.0", "end").strip().splitlines() if line.strip()] if hasattr(self, 'feeds_text') else self.config.posting.feeds,
                    "max_posts_per_run": int(self.articles_num_var.get()) if hasattr(self, 'articles_num_var') and str(self.articles_num_var.get()).isdigit() else 1,
                    "generate_images": self.attach_image_var.get() if hasattr(self, 'attach_image_var') else False,
                },
                "engagement": {
                    "enabled": self.engage_var.get(),
                    "replies_per_run": int(self.replies_num_var.get()) if hasattr(self, 'replies_num_var') and self.replies_num_var.get().isdigit() else 20,
                    "min_likes_for_reply": 0,
                    "skip_political": True,
                },
                "prompts": {
                    "style": "default",  # style removed from UI, using internal
                    "post": {"prompt": DEFAULT_POST_PROMPT},
                    "reply": {"prompt": DEFAULT_REPLY_PROMPT},
                }
            }

            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, sort_keys=False, allow_unicode=True)

            self.config = load_config(str(self.config_path))
            self._log("Settings saved.")
            messagebox.showinfo("Saved", "Settings updated (feeds, counts, image option).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            self._log(f"Save error: {e}")

    def _run_bot(self):
        if not self.config:
            messagebox.showwarning("Setup needed", "Please complete the initial details first.")
            return

        # Apply live edits from UI (feeds, articles count, reply count)
        if hasattr(self, 'feeds_text'):
            feeds = [line.strip() for line in self.feeds_text.get("1.0", "end").strip().splitlines() if line.strip()]
            self.config.posting.feeds = feeds

        if hasattr(self, 'articles_num_var') and self.articles_num_var.get().isdigit():
            self.config.posting.max_posts_per_run = int(self.articles_num_var.get())

        if hasattr(self, 'replies_num_var') and self.replies_num_var.get().isdigit():
            self.config.engagement.replies_per_run = int(self.replies_num_var.get())

        if hasattr(self, 'attach_image_var'):
            self.config.posting.generate_images = self.attach_image_var.get()

        dry_run = self.dry_run_var.get()
        modes = []
        if self.post_var.get(): modes.append("post")
        if self.engage_var.get(): modes.append("engage")
        if not modes:
            return

        self.stop_event.clear()
        self.run_button.configure(state="disabled", text="Running...")
        self.stop_button.configure(state="normal")
        self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Starting background run..."))
        self._log(f"Starting {'dry ' if dry_run else ''}run with {len(modes)} mode(s)...")
        feeds = self.config.posting.feeds if self.config and hasattr(self.config.posting, 'feeds') else []
        self._log(f"  Using {len(feeds)} article sources (RSS feeds):")
        for f in feeds:
            self._log(f"    - {f}")
        num_articles = int(self.articles_num_var.get()) if hasattr(self, 'articles_num_var') and str(self.articles_num_var.get()).isdigit() else 1
        num_replies = int(self.replies_num_var.get()) if hasattr(self, 'replies_num_var') and str(self.replies_num_var.get()).isdigit() else 1
        self._log(f"  Target this run: up to {num_articles} article(s) + up to {num_replies} random replies.")
        self._log("Launching background worker thread now... (the real work of searching your feeds and generating with your prompts happens here)")
        self._log("The log below will fill with details as it works (fetching each URL, considering articles, LLM generating the post text, etc.).")

        def worker():
            try:
                import time
                with open("haruxsky_run_debug.txt", "a") as f:
                    f.write(f"Worker thread started at {time.time()}\n")
                self._log("Worker thread started. This background thread is now running the actual code that searches your RSS feeds and calls the LLM with your prompts to generate the posts and replies.")
                self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Worker thread started - doing the real work..."))
                # Prefer pre-connected clients from "load up", otherwise create fresh (this triggers login)
                if self.llm_client and self.bsky_client:
                    llm = self.llm_client
                    bsky = self.bsky_client
                    self._log("Reusing existing clients from startup.")
                else:
                    self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Initializing LLM..."))
                    self._log("Initializing LLM client...")
                    llm = LLMClient(self.config.llm)
                    self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Logging into Bluesky..."))
                    self._log("Initializing Bluesky client (this may take a moment for login)...")
                    bsky = BskyClientWrapper(self.config)
                    self._log("Clients ready.")

                if "post" in modes:
                    self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Searching RSS feeds and generating posts..."))
                    num_articles = getattr(self.config.posting, 'max_posts_per_run', 1) if self.config else 1
                    self._log("=== Starting article posting phase ===")
                    run_posting(self.config, llm, bsky, dry_run=dry_run, stop_event=self.stop_event, log_func=self._log, max_posts=num_articles)
                    self._log("=== Finished article posting phase ===")

                if "engage" in modes:
                    self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Finding random posts and generating replies..."))
                    self._log("=== Starting reply engagement phase ===")
                    run_engagement(self.config, llm, bsky, dry_run=dry_run, stop_event=self.stop_event, log_func=self._log)
                    self._log("=== Finished reply engagement phase ===")

                if self.stop_event.is_set():
                    self._log("Run was stopped by user.")
                else:
                    self._log("Run finished successfully.")
            except Exception as e:
                self._log(f"Run error: {e}")
                import traceback
                self._log(traceback.format_exc())
            finally:
                self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Idle"))
                self.root.after(0, lambda: self.run_button.configure(state="normal", text="▶ Run Now"))
                self.root.after(0, lambda: self.stop_button.configure(state="disabled"))

        threading.Thread(target=worker, daemon=True).start()

    def _stop_run(self):
        """Request stop for the current run."""
        self.stop_event.set()
        self._log("Stop requested. Will finish current article/reply and exit.")
        self.stop_button.configure(state="disabled")

    def _logout(self):
        """Log out and reset to the login/setup screen (actual reset)."""
        self.llm_client = None
        self.bsky_client = None
        self._log("Logged out - resetting to setup screen for re-entry of details.")

        # Switch back to setup screen (the "log in stuff")
        if hasattr(self, 'main_frame') and self.main_frame:
            self.main_frame.pack_forget()
        if hasattr(self, 'loading_frame') and self.loading_frame:
            self.loading_frame.pack_forget()
        self.setup_frame.pack(fill="both", expand=True)
        self.status_bar.configure(text="Setup required - re-enter or edit details")

        # Prefill the setup fields with current values (so user can see/edit existing)
        if self.config:
            try:
                self.setup_handle.delete(0, "end")
                self.setup_handle.insert(0, self.config.bluesky.get("handle", ""))
                self.setup_pass.delete(0, "end")
                self.setup_pass.insert(0, self.config.bluesky.get("app_password", ""))
                self.setup_key.delete(0, "end")
                self.setup_key.insert(0, getattr(self.config.llm, 'api_key', ""))
            except Exception:
                pass  # if fields not ready, no big deal

        messagebox.showinfo("Logged Out", "Setup screen is back.\nEdit the details (handle, app password, API key) and click 'Save Details & Load the Program' to reconfigure and reload the full program.")

    def _clear_log(self):
        if self.log_text:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")

    def _test_fetch_and_generate(self):
        """Test button: actually fetch from the feeds in the box and generate a post using your prompts. Proves it's real."""
        if not self.config:
            messagebox.showwarning("Setup needed", "Complete setup first.")
            return

        feeds = [line.strip() for line in self.feeds_text.get("1.0", "end").strip().splitlines() if line.strip()]
        if not feeds:
            self._log("No feeds in Article Sources box to test.")
            return

        self.activity_label.configure(text="Current activity: Testing fetch & generate from feeds...")
        self._log("=== TEST: Fetching from your RSS sources and generating post with your prompts ===")

        def worker():
            try:
                llm = self.llm_client or LLMClient(self.config.llm)
                self._log(f"Testing first feed: {feeds[0]}")

                import feedparser
                from bs4 import BeautifulSoup
                feed = feedparser.parse(feeds[0])
                self._log(f"  Found {len(feed.entries)} entries.")

                if not feed.entries:
                    self._log("  No entries in feed.")
                    return

                entry = feed.entries[0]
                title = entry.title
                raw_summary = entry.get("summary", entry.get("description", ""))
                soup = BeautifulSoup(raw_summary, "html.parser")
                clean_summary = soup.get_text(separator=" ", strip=True)

                self._log(f"  Using first article: {title[:60]}...")

                style = getattr(self.config, 'prompts', None).style if self.config and getattr(self.config, 'prompts', None) else "default"
                post_prompt = format_prompt(
                    DEFAULT_POST_PROMPT,
                    title=title,
                    summary=clean_summary,
                    style=style
                )

                self._log("  Calling LLM with your post prompt to generate article...")
                full_text = llm.generate(post_prompt, max_tokens=500, temperature=0.7)

                if full_text:
                    self._log("  === GENERATED POST (using your prompt) ===")
                    self._log(full_text[:500] + ("..." if len(full_text) > 500 else ""))
                    self._log("  === END GENERATED POST ===")
                    self._log("Test successful — it is actually using your sources and prompts to write posts.")
                else:
                    self._log("  LLM returned empty. Check your API key or prompt.")

            except Exception as e:
                self._log(f"Test error: {e}")
            finally:
                self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Idle"))

        threading.Thread(target=worker, daemon=True).start()

    def _test_generate_reply(self):
        """Test button: find a recent post and generate a reply using your reply prompt. Proves replies work."""
        if not self.config:
            messagebox.showwarning("Setup needed", "Complete setup first.")
            return

        self.activity_label.configure(text="Current activity: Testing reply generation to random post...")
        self._log("=== TEST: Finding a random recent post and generating reply with your prompt ===")

        def worker():
            try:
                llm = self.llm_client or LLMClient(self.config.llm)
                bsky = self.bsky_client or BskyClientWrapper(self.config)

                # Simple search for a recent post (like the engager does)
                self._log("  Searching Bluesky for a recent post (broad query)...")
                posts = bsky.search_posts("the", limit=5)  # simple query to get something

                if not posts:
                    self._log("  No posts found in test search.")
                    return

                post = posts[0]
                post_text = ""
                if hasattr(post, 'record') and hasattr(post.record, 'text'):
                    post_text = post.record.text or ""
                elif hasattr(post, 'text'):
                    post_text = post.text or ""

                author = post.author.handle if hasattr(post, 'author') else "unknown"

                self._log(f"  Found post by @{author}: {post_text[:80]}...")

                style = getattr(self.config, 'prompts', None).style if self.config and getattr(self.config, 'prompts', None) else "default"
                reply_prompt = format_prompt(
                    DEFAULT_REPLY_PROMPT,
                    post_text=post_text,
                    author_handle=author,
                    style=style
                )

                self._log("  Calling LLM with your reply prompt to generate response...")
                reply_text = llm.generate(reply_prompt, max_tokens=60, temperature=0.8)

                if reply_text:
                    self._log("  === GENERATED REPLY (using your prompt) ===")
                    self._log(reply_text)
                    self._log("  === END GENERATED REPLY ===")
                    self._log("Test successful — it is actually finding random posts and generating replies like a real person.")
                else:
                    self._log("  LLM returned empty reply.")

            except Exception as e:
                self._log(f"Test error: {e}")
            finally:
                self.root.after(0, lambda: self.activity_label.configure(text="Current activity: Idle"))

        threading.Thread(target=worker, daemon=True).start()

    def _open_config_folder(self):
        folder = self.config_path.parent.resolve()
        try:
            import os
            os.startfile(folder)  # Windows
        except Exception:
            messagebox.showinfo("Config Location", str(folder))


def main():
    root = ctk.CTk()
    app = HaruxSkyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
