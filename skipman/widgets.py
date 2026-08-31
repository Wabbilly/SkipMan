# ── Retro Widgets — autocomplete entries + classic popup dialogs ────────────

import tkinter as tk

from skipman import theme


class AutofillEntry(tk.Entry):
    """
    Entry with a retro dropdown of suggestions while you type.

    suggest_fn(text) -> list[str] is called on each keystroke.
    Up/Down navigates, Enter/Tab accepts, Escape dismisses.
    """

    def __init__(self, parent, suggest_fn, on_pick=None, **kwargs):
        opts = theme.entry_style()
        opts.update(kwargs)
        super().__init__(parent, **opts)
        self.suggest_fn = suggest_fn
        self.on_pick = on_pick
        self._popup = None
        self._listbox = None

        self.bind("<KeyRelease>", self._on_key)
        self.bind("<FocusOut>", lambda e: self.after(150, self._hide))
        self.bind("<Escape>", lambda e: self._hide())
        self.bind("<Down>", self._nav_down)
        self.bind("<Up>", self._nav_up)
        self.bind("<Return>", self._accept)
        self.bind("<Tab>", self._accept_tab)

    # ── Value helpers ───────────────────────────────────────────────────────
    def set_text(self, text):
        self.delete(0, "end")
        self.insert(0, text or "")

    # ── Suggestion popup ────────────────────────────────────────────────────
    def _on_key(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab",
                            "Left", "Right"):
            return
        text = self.get()
        if not text.strip():
            self._hide()
            return
        try:
            items = self.suggest_fn(text) or []
        except Exception:
            items = []
        # Don't suggest exactly what's already typed
        items = [i for i in items if i.lower() != text.lower().strip()]
        if items:
            self._show(items)
        else:
            self._hide()

    def _show(self, items):
        if self._popup is None or not self._popup.winfo_exists():
            self._popup = tk.Toplevel(self)
            self._popup.overrideredirect(True)
            self._popup.attributes("-topmost", True)
            self._listbox = tk.Listbox(
                self._popup, height=min(len(items), 6),
                **theme.listbox_style())
            self._listbox.pack(fill="both", expand=True)
            self._listbox.bind("<ButtonRelease-1>", self._click_pick)
        else:
            self._listbox.config(height=min(len(items), 6))

        self._listbox.delete(0, "end")
        for it in items:
            self._listbox.insert("end", " " + it)

        # Position just under the entry
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()
        self._popup.geometry(f"{w}x{self._listbox.winfo_reqheight()}+{x}+{y}")

    def _hide(self):
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
        self._listbox = None

    def _visible(self):
        return self._popup is not None and self._popup.winfo_exists()

    # ── Navigation / selection ──────────────────────────────────────────────
    def _nav(self, delta):
        if not self._visible():
            return "break"
        size = self._listbox.size()
        cur = self._listbox.curselection()
        idx = (cur[0] + delta) if cur else (0 if delta > 0 else size - 1)
        idx = max(0, min(size - 1, idx))
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(idx)
        self._listbox.activate(idx)
        return "break"

    def _nav_down(self, e):
        return self._nav(1)

    def _nav_up(self, e):
        return self._nav(-1)

    def _pick_current(self):
        cur = self._listbox.curselection()
        if not cur:
            return False
        value = self._listbox.get(cur[0]).strip()
        self.set_text(value)
        self._hide()
        self.icursor("end")
        if self.on_pick:
            self.on_pick(value)
        return True

    def _accept(self, e):
        if self._visible() and self._pick_current():
            return "break"
        self._hide()
        return None

    def _accept_tab(self, e):
        if self._visible():
            self._pick_current()
        return None

    def _click_pick(self, e):
        if self._visible():
            self._pick_current()


class RetroDialog(tk.Toplevel):
    """Classic-Windows-style modal dialog. Returns the clicked button's key."""

    def __init__(self, parent, title, message, buttons,
                 accent=None, checkbox=None):
        """
        buttons: list of (key, label) tuples
        accent: key of the button drawn amber
        checkbox: optional label -> adds a check box; result stored
                  in self.checked
        """
        super().__init__(parent)
        self.result = None
        self.checked = False
        self.title(title)
        self.configure(bg=theme.BG_DARK)
        self.resizable(False, False)
        self.transient(parent)

        tk.Label(
            self, text=title.upper(), font=theme.FONT_TITLE,
            bg=theme.BG_DARK, fg=theme.AMBER,
        ).pack(padx=18, pady=(14, 4), anchor="w")

        tk.Label(
            self, text=message, font=theme.FONT_SMALL, justify="left",
            bg=theme.BG_DARK, fg=theme.TEXT_LIGHT, wraplength=380,
        ).pack(padx=18, pady=(0, 10), anchor="w")

        self._check_var = tk.IntVar(value=0)
        if checkbox:
            tk.Checkbutton(
                self, text=checkbox, variable=self._check_var,
                font=theme.FONT_SMALL, bg=theme.BG_DARK,
                fg=theme.TEXT_LIGHT, selectcolor=theme.BG_INPUT,
                activebackground=theme.BG_DARK,
                activeforeground=theme.TEXT_LIGHT,
            ).pack(padx=18, pady=(0, 8), anchor="w")

        row = tk.Frame(self, bg=theme.BG_DARK)
        row.pack(padx=18, pady=(0, 14), anchor="e")

        for key, label in buttons:
            tk.Button(
                row, text=label, padx=12, pady=3,
                **theme.button_style(accent=(key == accent)),
                command=lambda k=key: self._done(k),
            ).pack(side="left", padx=(0, 6))

        self.protocol("WM_DELETE_WINDOW", lambda: self._done(None))
        self.bind("<Escape>", lambda e: self._done(None))

        # Center over parent
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"+{px - self.winfo_width() // 2}"
                      f"+{py - self.winfo_height() // 2}")

        self.grab_set()
        self.focus_set()

    def _done(self, key):
        self.checked = bool(self._check_var.get())
        self.result = key
        self.grab_release()
        self.destroy()


def ask(parent, title, message, buttons, accent=None, checkbox=None):
    """Show a RetroDialog and wait. Returns (clicked_key, checkbox_bool)."""
    dlg = RetroDialog(parent, title, message, buttons,
                      accent=accent, checkbox=checkbox)
    parent.wait_window(dlg)
    return dlg.result, dlg.checked
