# ── SkipMan Theme — Late 90s / Early 2000s PC Aesthetic ─────────────────────
# Think Winamp, Napster, LimeWire, mIRC, dark WinXP skins

# ── Backgrounds ─────────────────────────────────────────────────────────────
BG_DARK    = "#1e1e1e"       # Main window
BG_PANEL   = "#2d2d2d"       # Panel / frame backgrounds
BG_INPUT   = "#0a0a0a"       # Text inputs (deep black)
BG_BUTTON  = "#b0b0b0"       # Classic Windows gray buttons
BG_BUTTON_ACTIVE = "#d0d0d0" # Button hover / active state

# ── Accent Colors ───────────────────────────────────────────────────────────
GREEN      = "#00ff41"        # Matrix / terminal green — primary accent
AMBER      = "#ffb000"        # Amber — important actions (download, upload)
AMBER_ACTIVE = "#e09e00"      # Amber hover

# ── Text ────────────────────────────────────────────────────────────────────
TEXT_LIGHT = "#d4d4d4"        # Primary text
TEXT_DARK  = "#000000"        # Text on light buttons
MUTED      = "#707070"        # Secondary / label text
SUCCESS    = "#00ff41"        # Same as GREEN
ERROR      = "#ff3333"        # Error red

# ── Borders ─────────────────────────────────────────────────────────────────
BORDER_LIGHT = "#555555"      # Raised edge light side
BORDER_DARK  = "#0a0a0a"      # Raised edge dark side
BORDER_MID   = "#444444"      # Divider lines

# ── Fonts ───────────────────────────────────────────────────────────────────
FONT_HEADER    = ("Terminal", 18, "bold")
FONT_TITLE     = ("Terminal", 14, "bold")
FONT_MAIN      = ("Courier New", 10)
FONT_SMALL     = ("Courier New", 9)
FONT_BUTTON    = ("MS Sans Serif", 9, "bold")
FONT_BUTTON_BIG = ("MS Sans Serif", 10, "bold")
FONT_STATUS    = ("Courier New", 8)

# ── Widget Style Helpers ────────────────────────────────────────────────────
SUNKEN = dict(relief="sunken", bd=2)
RAISED = dict(relief="raised", bd=2)

def entry_style():
    """Common kwargs for Entry widgets."""
    return dict(
        font=FONT_MAIN, bg=BG_INPUT, fg=TEXT_LIGHT,
        insertbackground=GREEN, relief="sunken", bd=2,
        selectbackground=GREEN, selectforeground=BG_INPUT,
    )

def button_style(accent=False):
    """Common kwargs for Button widgets."""
    if accent:
        return dict(
            font=FONT_BUTTON, bg=AMBER, fg=TEXT_DARK,
            relief="raised", bd=2, cursor="hand2",
            activebackground=AMBER_ACTIVE, activeforeground=TEXT_DARK,
        )
    return dict(
        font=FONT_BUTTON, bg=BG_BUTTON, fg=TEXT_DARK,
        relief="raised", bd=2, cursor="hand2",
        activebackground=BG_BUTTON_ACTIVE, activeforeground=TEXT_DARK,
    )

def label_style(muted=False):
    """Common kwargs for Label widgets."""
    return dict(
        font=FONT_SMALL, bg=BG_DARK,
        fg=MUTED if muted else TEXT_LIGHT,
    )

def listbox_style():
    """Common kwargs for Listbox widgets."""
    return dict(
        font=FONT_SMALL, bg=BG_INPUT, fg=TEXT_LIGHT,
        selectbackground=GREEN, selectforeground=TEXT_DARK,
        relief="sunken", bd=2, activestyle="none",
        highlightthickness=0,
    )
