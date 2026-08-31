# ── Download Screen — Queue + Background Download UI ────────────────────────

import tkinter as tk
from tkinter import filedialog
import threading

from skipman import theme


class DownloadScreen(tk.Frame):
    """Screen 1: paste URLs; the queue downloads itself in the background."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG_DARK)
        self.app = app
        self._active_pct = 0
        self._build_ui()

    # ── Build UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=theme.BG_DARK)
        hdr.pack(fill="x", padx=20, pady=(16, 0))

        from skipman import __version__
        tk.Label(
            hdr, text=f"// SKIPMAN v{__version__}", font=theme.FONT_HEADER,
            bg=theme.BG_DARK, fg=theme.GREEN,
        ).pack(anchor="w")

        tk.Label(
            hdr, text="YouTube  ·  SoundCloud (songs + playlists)  ·  and more",
            font=theme.FONT_SMALL, bg=theme.BG_DARK, fg=theme.MUTED,
        ).pack(anchor="w")

        tk.Frame(self, height=2, bg=theme.BORDER_MID).pack(
            fill="x", padx=20, pady=(10, 10))

        # ── URL Input Row ───────────────────────────────────────────────────
        tk.Label(
            self, text="PASTE URL  (song or playlist)",
            **theme.label_style(muted=True),
        ).pack(padx=20, anchor="w")

        url_row = tk.Frame(self, bg=theme.BG_DARK)
        url_row.pack(fill="x", padx=20, pady=(2, 8))

        self.url_entry = tk.Entry(url_row, **theme.entry_style())
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.url_entry.bind("<Return>", lambda e: self._add_url())

        self.add_btn = tk.Button(
            url_row, text="ADD", padx=14, pady=3,
            **theme.button_style(), command=self._add_url,
        )
        self.add_btn.pack(side="right", padx=(8, 0))

        # ── Save Folder ────────────────────────────────────────────────────
        tk.Label(
            self, text="SAVE TO", **theme.label_style(muted=True),
        ).pack(padx=20, anchor="w")

        folder_row = tk.Frame(self, bg=theme.BG_DARK)
        folder_row.pack(fill="x", padx=20, pady=(2, 8))

        self.folder_var = tk.StringVar(value=self.app.save_dir)
        tk.Label(
            folder_row, textvariable=self.folder_var,
            font=theme.FONT_SMALL, bg=theme.BG_INPUT, fg=theme.TEXT_LIGHT,
            anchor="w", relief="sunken", bd=2,
        ).pack(side="left", fill="x", expand=True, ipady=3)

        tk.Button(
            folder_row, text="...", padx=10, pady=1,
            **theme.button_style(), command=self._browse,
        ).pack(side="right", padx=(8, 0))

        # ── Queue ───────────────────────────────────────────────────────────
        self.queue_label = tk.Label(
            self, text="QUEUE (0)", **theme.label_style(muted=True),
        )
        self.queue_label.pack(padx=20, anchor="w", pady=(4, 0))

        queue_frame = tk.Frame(self, bg=theme.BG_DARK)
        queue_frame.pack(fill="x", padx=20, pady=(2, 4))

        self.queue_listbox = tk.Listbox(
            queue_frame, height=5, **theme.listbox_style())
        self.queue_listbox.pack(fill="x")

        # Queue buttons
        qbtn_row = tk.Frame(self, bg=theme.BG_DARK)
        qbtn_row.pack(fill="x", padx=20, pady=(0, 10))

        tk.Button(
            qbtn_row, text="REMOVE", padx=10, pady=2,
            **theme.button_style(), command=self._remove_selected,
        ).pack(side="left")

        tk.Button(
            qbtn_row, text="CLEAR ALL", padx=10, pady=2,
            **theme.button_style(), command=self._clear_queue,
        ).pack(side="left", padx=(8, 0))

        self.edit_btn = tk.Button(
            qbtn_row, text="▶  EDIT READY (0)", padx=16, pady=4,
            **theme.button_style(accent=True), command=self._edit_ready,
            state="disabled",
        )
        self.edit_btn.pack(side="right")

        # ── Progress Bar (segmented, chunky 90s style) ─────────────────────
        self.progress_canvas = tk.Canvas(
            self, height=18, bg=theme.BG_PANEL,
            relief="sunken", bd=2, highlightthickness=0,
        )
        self.progress_canvas.pack(fill="x", padx=20, pady=(0, 4))

        # ── Status ─────────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = tk.Label(
            self, textvariable=self.status_var,
            font=theme.FONT_SMALL, bg=theme.BG_DARK, fg=theme.MUTED,
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=20, pady=(0, 6))

        # ── Log ────────────────────────────────────────────────────────────
        tk.Frame(self, height=2, bg=theme.BORDER_MID).pack(
            fill="x", padx=20, pady=(0, 6))

        self.log = tk.Text(
            self, font=theme.FONT_SMALL, bg=theme.BG_INPUT, fg=theme.MUTED,
            relief="sunken", bd=2, height=4, state="disabled", wrap="word",
        )
        self.log.pack(fill="both", padx=20, pady=(0, 10), expand=True)

        # ── Bottom Status Bar (classic Windows) ────────────────────────────
        status_bar = tk.Frame(self, bg=theme.BG_PANEL, relief="sunken", bd=1)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(
            status_bar, text=f" SkipMan v{__version__}",
            font=theme.FONT_STATUS,
            bg=theme.BG_PANEL, fg=theme.MUTED, anchor="w",
        ).pack(side="left", padx=4, pady=2)

        self.bar_right = tk.Label(
            status_bar, text="", font=theme.FONT_STATUS,
            bg=theme.BG_PANEL, fg=theme.MUTED, anchor="e",
        )
        self.bar_right.pack(side="right", padx=4, pady=2)

    # ── Adding URLs ─────────────────────────────────────────────────────────
    def _add_url(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        self.url_entry.delete(0, "end")
        self.add_btn.config(state="disabled")
        self._set_status("Checking link…", theme.AMBER)

        def _probe():
            from skipman.downloader import probe
            try:
                info = probe(url)
                self.app.post(self._probe_done, url, info, None)
            except Exception as e:
                self.app.post(self._probe_done, url, None, str(e))

        threading.Thread(target=_probe, daemon=True).start()

    def _probe_done(self, url, info, error):
        self.add_btn.config(state="normal")
        if error:
            self._set_status(f"Error: {error}", theme.ERROR)
            self._log(f"[ERROR] {error}")
            return

        if info["kind"] == "playlist":
            n = len(info["entries"])
            self._set_status(
                f'Playlist "{info["title"]}" — {n} tracks. '
                "Arrange the album…", theme.GREEN)
            self.app.show_album_screen(info)
            return

        entry = info["entry"]
        # ── Duplicate check before queueing ────────────────────────────────
        match = self.app.library.check(entry["title"], entry["artist"])
        if match:
            from skipman import widgets
            choice, _ = widgets.ask(
                self.app, "Already in library?",
                f'This looks like a song you already have:\n\n'
                f'  {match["label"]}\n'
                f'  (found in: {match["source"]})\n\n'
                f'Download "{entry["title"]}" anyway?',
                buttons=[("skip", "SKIP IT"), ("dl", "DOWNLOAD ANYWAY")],
                accent="skip",
            )
            if choice != "dl":
                self._set_status(
                    f'Skipped duplicate: "{entry["title"]}"', theme.MUTED)
                self._log(f'[DUPE] Skipped "{entry["title"]}" '
                          f'({match["source"]})')
                return

        from skipman.worker import Job
        job = Job(url=entry["url"] or url, title=entry["title"],
                  artist=entry["artist"])
        self.app.worker.add(job)
        self._set_status(
            f'Queued: "{entry["title"]}" — downloading in background.',
            theme.GREEN)
        self.refresh_queue_display()

    # ── Queue actions ───────────────────────────────────────────────────────
    def _remove_selected(self):
        sel = self.queue_listbox.curselection()
        if not sel:
            return
        _active, pending = self.app.worker.snapshot()
        idx = sel[0]
        # Row 0 is the active download when present (can't remove that one)
        offset = 1 if _active else 0
        p_idx = idx - offset
        if 0 <= p_idx < len(pending):
            self.app.worker.cancel(pending[p_idx].id)
        self.refresh_queue_display()

    def _clear_queue(self):
        self.app.worker.cancel_all()
        self.refresh_queue_display()
        self._set_status("Queue cleared (current download finishes).",
                         theme.MUTED)

    def refresh_queue_display(self):
        active, pending = self.app.worker.snapshot()
        self.queue_listbox.delete(0, "end")

        row = 0
        if active:
            self.queue_listbox.insert(
                "end", f"  ▼ {self._short(active.title)}"
                       f"  [{self._active_pct:.0f}%]")
            self.queue_listbox.itemconfig(row, fg=theme.AMBER)
            row += 1
        for i, job in enumerate(pending):
            self.queue_listbox.insert(
                "end", f"  {i + 1}. {self._short(job.title)}")
            row += 1

        total = len(pending) + (1 if active else 0)
        self.queue_label.config(text=f"QUEUE ({total})")

        # Ready-to-edit button + status bar
        n_ready = len(self.app.ready)
        self.edit_btn.config(
            text=f"▶  EDIT READY ({n_ready})",
            state="normal" if n_ready else "disabled",
        )
        bits = []
        if total:
            bits.append(f"{total} downloading")
        if n_ready:
            bits.append(f"{n_ready} ready to edit")
        self.bar_right.config(text="  ".join(bits))

    @staticmethod
    def _short(text, n=58):
        text = text or ""
        return text if len(text) <= n else text[: n - 3] + "..."

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.app.save_dir)
        if d:
            self.app.set_save_dir(d)
            self.folder_var.set(d)

    def _edit_ready(self):
        self.app._maybe_edit_next(force=True)

    def can_autojump(self):
        """OK to auto-open the edit screen? Not while the user is typing."""
        return not self.url_entry.get().strip()

    # ── Worker event handlers (UI thread) ───────────────────────────────────
    def on_job_started(self, job):
        self._active_pct = 0
        self._set_status(f'Downloading: "{self._short(job.title)}"',
                         theme.MUTED)
        self.refresh_queue_display()

    def on_job_progress(self, job, pct, speed):
        self._active_pct = pct
        self._set_progress(pct)
        if speed == "converting":
            self._set_status("Converting to MP3…", theme.AMBER)
        else:
            self._set_status(
                f"Downloading… {pct:.0f}%  {speed}", theme.MUTED)
        # Update the active row's percentage without full rebuild
        active, _ = self.app.worker.snapshot()
        if active and self.queue_listbox.size():
            self.queue_listbox.delete(0)
            self.queue_listbox.insert(
                0, f"  ▼ {self._short(active.title)}  [{pct:.0f}%]")
            self.queue_listbox.itemconfig(0, fg=theme.AMBER)

    def on_job_done(self, job, result):
        title = result.get("title", "Unknown")
        self._set_progress(100)
        self._log(f'[OK] "{title}"')
        self.refresh_queue_display()

    def on_job_error(self, job, message):
        self._set_status(f"Error: {message}", theme.ERROR)
        self._log(f"[ERROR] {self._short(job.title)}: {message}")
        self._set_progress(0)
        self.refresh_queue_display()

    def on_queue_idle(self):
        n_ready = len(self.app.ready)
        if n_ready:
            self._set_status(
                f"Downloads finished — {n_ready} song(s) ready to edit.",
                theme.GREEN)
        self.refresh_queue_display()

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _set_status(self, msg, color=None):
        self.status_var.set(msg)
        if color:
            self.status_label.config(fg=color)

    def _set_progress(self, pct):
        """Draw segmented progress bar (chunky 90s style)."""
        self.update_idletasks()
        w = self.progress_canvas.winfo_width()
        h = self.progress_canvas.winfo_height()
        self.progress_canvas.delete("seg")

        total_segs = 30
        gap = 2
        seg_w = max(1, (w - 6) / total_segs)
        filled = int(total_segs * pct / 100)

        for i in range(total_segs):
            x0 = 3 + i * seg_w + gap / 2
            x1 = x0 + seg_w - gap
            color = theme.GREEN if i < filled else theme.BG_DARK
            self.progress_canvas.create_rectangle(
                x0, 3, x1, h - 3, fill=color, outline="", tags="seg",
            )

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")
