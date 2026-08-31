# ── Album Screen — arrange a playlist into an album before download ─────────

import tkinter as tk

from skipman import theme
from skipman.widgets import AutofillEntry


class AlbumScreen(tk.Frame):
    """
    Shown when a playlist URL is added: set album name/artist, arrange the
    track order, drop duplicates, then send the whole album to the
    background download queue with track numbers pre-assigned.
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG_DARK)
        self.app = app
        self.tracks = []       # [{title, artist, url, dupe}]
        self._build_ui()

    # ── Build UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        tk.Label(
            self, text="// ARRANGE ALBUM", font=theme.FONT_HEADER,
            bg=theme.BG_DARK, fg=theme.GREEN,
        ).pack(padx=20, pady=(16, 0), anchor="w")

        self.sub_label = tk.Label(
            self, text="", font=theme.FONT_SMALL,
            bg=theme.BG_DARK, fg=theme.MUTED,
        )
        self.sub_label.pack(padx=20, anchor="w")

        tk.Frame(self, height=2, bg=theme.BORDER_MID).pack(
            fill="x", padx=20, pady=(8, 8))

        # ── Album name / artist ────────────────────────────────────────────
        row = tk.Frame(self, bg=theme.BG_DARK)
        row.pack(fill="x", padx=20)

        col1 = tk.Frame(row, bg=theme.BG_DARK)
        col1.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(col1, text="ALBUM NAME",
                 **theme.label_style(muted=True)).pack(anchor="w")
        self.album_entry = AutofillEntry(
            col1, suggest_fn=lambda t: self.app.store.album_suggestions(t))
        self.album_entry.pack(fill="x", ipady=5, pady=(2, 8))

        col2 = tk.Frame(row, bg=theme.BG_DARK)
        col2.pack(side="left", fill="x", expand=True)
        tk.Label(col2, text="ALBUM ARTIST",
                 **theme.label_style(muted=True)).pack(anchor="w")
        self.artist_entry = AutofillEntry(
            col2, suggest_fn=lambda t: self.app.store.artist_suggestions(t))
        self.artist_entry.pack(fill="x", ipady=5, pady=(2, 8))

        # ── Track list ─────────────────────────────────────────────────────
        self.tracks_label = tk.Label(
            self, text="TRACK ORDER", **theme.label_style(muted=True))
        self.tracks_label.pack(padx=20, anchor="w")

        list_row = tk.Frame(self, bg=theme.BG_DARK)
        list_row.pack(fill="both", expand=True, padx=20, pady=(2, 4))

        self.listbox = tk.Listbox(list_row, **theme.listbox_style())
        self.listbox.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(list_row, command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        # Drag to reorder
        self.listbox.bind("<Button-1>", self._drag_start)
        self.listbox.bind("<B1-Motion>", self._drag_motion)
        self._drag_index = None

        # ── Track buttons ──────────────────────────────────────────────────
        tbtn = tk.Frame(self, bg=theme.BG_DARK)
        tbtn.pack(fill="x", padx=20, pady=(0, 8))

        tk.Button(tbtn, text="▲ UP", padx=10, pady=2,
                  **theme.button_style(),
                  command=lambda: self._move(-1)).pack(side="left")
        tk.Button(tbtn, text="▼ DOWN", padx=10, pady=2,
                  **theme.button_style(),
                  command=lambda: self._move(1)).pack(side="left", padx=(6, 0))
        tk.Button(tbtn, text="REMOVE", padx=10, pady=2,
                  **theme.button_style(),
                  command=self._remove).pack(side="left", padx=(6, 0))
        self.drop_dupes_btn = tk.Button(
            tbtn, text="DROP DUPES", padx=10, pady=2,
            **theme.button_style(), command=self._drop_dupes)
        self.drop_dupes_btn.pack(side="left", padx=(6, 0))

        # ── Options ────────────────────────────────────────────────────────
        opt = tk.Frame(self, bg=theme.BG_DARK)
        opt.pack(fill="x", padx=20, pady=(0, 6))

        self.auto_upload_var = tk.IntVar(
            value=1 if self.app.store.get_setting("album_auto_upload", True)
            else 0)
        tk.Checkbutton(
            opt, text="Auto-upload to Apple Music as tracks finish",
            variable=self.auto_upload_var,
            font=theme.FONT_SMALL, bg=theme.BG_DARK, fg=theme.TEXT_LIGHT,
            selectcolor=theme.BG_INPUT, activebackground=theme.BG_DARK,
            activeforeground=theme.TEXT_LIGHT,
        ).pack(anchor="w")

        self.review_var = tk.IntVar(value=0)
        tk.Checkbutton(
            opt, text="Review each track on the edit screen instead",
            variable=self.review_var,
            font=theme.FONT_SMALL, bg=theme.BG_DARK, fg=theme.TEXT_LIGHT,
            selectcolor=theme.BG_INPUT, activebackground=theme.BG_DARK,
            activeforeground=theme.TEXT_LIGHT,
        ).pack(anchor="w")

        # ── Actions ────────────────────────────────────────────────────────
        btns = tk.Frame(self, bg=theme.BG_DARK)
        btns.pack(fill="x", padx=20, pady=(0, 10))

        tk.Button(
            btns, text="▶  DOWNLOAD ALBUM", padx=16, pady=5,
            **theme.button_style(accent=True), command=self._go,
        ).pack(side="left")

        tk.Button(
            btns, text="CANCEL", padx=14, pady=5,
            **theme.button_style(), command=self._cancel,
        ).pack(side="right")

        # ── Status bar ─────────────────────────────────────────────────────
        status_bar = tk.Frame(self, bg=theme.BG_PANEL, relief="sunken", bd=1)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(
            status_bar, text=" Album Mode — drag or ▲▼ to reorder",
            font=theme.FONT_STATUS,
            bg=theme.BG_PANEL, fg=theme.MUTED, anchor="w",
        ).pack(side="left", padx=4, pady=2)

    # ── Load playlist ───────────────────────────────────────────────────────
    def load_playlist(self, info):
        self.album_entry.set_text(info.get("title", ""))
        self.artist_entry.set_text(info.get("uploader", ""))

        self.tracks = []
        n_dupes = 0
        for e in info.get("entries", []):
            dupe = self.app.library.check(e.get("title", ""),
                                          e.get("artist", ""))
            if dupe:
                n_dupes += 1
            self.tracks.append({
                "title": e.get("title", "Unknown"),
                "artist": e.get("artist", ""),
                "url": e.get("url", ""),
                "guess": e.get("guess", False),
                "dupe": dupe,
            })

        self.sub_label.config(
            text=f"{len(self.tracks)} tracks from playlist"
                 + (f"  ·  {n_dupes} already in your library" if n_dupes
                    else ""))
        self.drop_dupes_btn.config(
            state="normal" if n_dupes else "disabled")
        self._refresh()

    def _refresh(self, keep_selection=None):
        self.listbox.delete(0, "end")
        for i, t in enumerate(self.tracks):
            tag = "  [DUPE]" if t["dupe"] else ""
            self.listbox.insert(
                "end", f"  {i + 1:>2}. {self._short(t['title'])}{tag}")
            if t["dupe"]:
                self.listbox.itemconfig(i, fg=theme.AMBER)
        self.tracks_label.config(
            text=f"TRACK ORDER  ({len(self.tracks)} tracks)")
        if keep_selection is not None and self.tracks:
            idx = max(0, min(len(self.tracks) - 1, keep_selection))
            self.listbox.selection_set(idx)
            self.listbox.see(idx)

    @staticmethod
    def _short(text, n=52):
        text = text or ""
        return text if len(text) <= n else text[: n - 3] + "..."

    # ── Reordering ──────────────────────────────────────────────────────────
    def _move(self, delta):
        sel = self.listbox.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + delta
        if 0 <= j < len(self.tracks):
            self.tracks[i], self.tracks[j] = self.tracks[j], self.tracks[i]
            self._refresh(keep_selection=j)

    def _drag_start(self, event):
        self._drag_index = self.listbox.nearest(event.y)

    def _drag_motion(self, event):
        if self._drag_index is None:
            return
        j = self.listbox.nearest(event.y)
        i = self._drag_index
        if j != i and 0 <= j < len(self.tracks):
            self.tracks.insert(j, self.tracks.pop(i))
            self._drag_index = j
            self._refresh(keep_selection=j)

    def _remove(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.tracks.pop(sel[0])
        self._refresh(keep_selection=sel[0])

    def _drop_dupes(self):
        self.tracks = [t for t in self.tracks if not t["dupe"]]
        self._refresh()

    # ── Actions ─────────────────────────────────────────────────────────────
    def _go(self):
        if not self.tracks:
            return
        album = self.album_entry.get().strip() or "Album"
        artist = self.artist_entry.get().strip()
        auto_upload = bool(self.auto_upload_var.get())
        review = bool(self.review_var.get())
        self.app.store.set_setting("album_auto_upload", auto_upload)

        gid = self.app.new_group(
            title=album, artist=artist, total=len(self.tracks),
            auto_upload=auto_upload, review_each=review)

        from skipman.worker import Job
        for i, t in enumerate(self.tracks, start=1):
            self.app.worker.add(Job(
                url=t["url"], title=t["title"],
                artist=t["artist"] or artist,
                group=gid, track_no=i, album=album,
                title_guess=t.get("guess", False),
            ))

        # Remember the album for autofill right away
        self.app.store.remember(artist=artist, album=album)

        self.app.show_download_screen()
        self.app.download_screen._set_status(
            f'Album "{album}" queued — {len(self.tracks)} tracks '
            "downloading in background.", theme.GREEN)
        self.app.download_screen._log(
            f'[ALBUM] "{album}" — {len(self.tracks)} tracks queued.')

    def _cancel(self):
        self.app.show_download_screen()
