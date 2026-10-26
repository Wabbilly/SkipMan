# ── Read the clipboard (for "you copied a link — add it?") ──────────────────

import subprocess

from skipman.paths import IS_MAC, IS_WIN


def read_clipboard():
    try:
        if IS_MAC:
            return subprocess.run(["pbpaste"], capture_output=True, text=True,
                                  timeout=2).stdout
        if IS_WIN:
            return _win_clipboard()
    except Exception:
        pass
    return ""


def _win_clipboard():
    import ctypes
    from ctypes import wintypes
    CF_UNICODETEXT = 13
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    u32.GetClipboardData.restype = wintypes.HANDLE
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalLock.restype = wintypes.LPVOID
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    if not u32.OpenClipboard(None):
        return ""
    try:
        h = u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = k32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else ""
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()
