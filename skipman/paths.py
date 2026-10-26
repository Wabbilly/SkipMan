# ── Where SkipMan keeps things, per OS ──────────────────────────────────────

import os
import sys
import shutil

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(APP_DIR, "skipman", "ui")


def data_dir():
    """Per-user data folder (settings, memory, history)."""
    if IS_WIN and os.environ.get("LOCALAPPDATA"):
        d = os.path.join(os.environ["LOCALAPPDATA"], "SkipMan")
    elif IS_MAC:
        d = os.path.expanduser("~/Library/Application Support/SkipMan")
    else:
        d = os.path.expanduser("~/.skipman")
    os.makedirs(d, exist_ok=True)
    # One-time move from the v2 non-Windows location
    old = os.path.expanduser("~/.skipman/store.json")
    new = os.path.join(d, "store.json")
    if not IS_WIN and old != new and os.path.exists(old) \
            and not os.path.exists(new):
        try:
            shutil.copy2(old, new)
        except OSError:
            pass
    return d


def inbox_dir():
    """Links dropped on the Dock icon land here for the running app."""
    d = os.path.join(data_dir(), "inbox")
    os.makedirs(d, exist_ok=True)
    return d


def default_save_dir():
    return os.path.join(os.path.expanduser("~"), "Music", "SkipMan")
