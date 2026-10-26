# ── SkipMan — start here ────────────────────────────────────────────────────
# python main.py [links or .webloc/.url files to add]

import os
import plistlib
import sys
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from skipman.paths import data_dir, inbox_dir, UI_DIR, IS_MAC, IS_WIN  # noqa
from skipman import __version__  # noqa

PID_FILE = os.path.join(data_dir(), "skipman.pid")


def _alive(pid):
    if pid <= 0 or pid == os.getpid():
        return False
    if IS_WIN:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _running_pid():
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip() or 0)
        return pid if _alive(pid) else 0
    except (OSError, ValueError):
        return 0


def _links_from_args(args):
    """Turn CLI args / dropped files (.webloc, .url, .txt) into link text."""
    out = []
    for a in args:
        if a.startswith("-"):
            continue
        if a.lower().startswith(("http://", "https://", "skipman://")):
            if a.lower().startswith("skipman://"):
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(a).query)
                out.extend(q.get("url", []))
            else:
                out.append(a)
        elif os.path.isfile(a):
            try:
                if a.lower().endswith(".webloc"):
                    with open(a, "rb") as f:
                        out.append(plistlib.load(f).get("URL", ""))
                else:
                    with open(a, "r", encoding="utf-8", errors="replace") as f:
                        out.append(f.read(20000))
            except Exception:
                pass
    return "\n".join(x for x in out if x)


def main():
    args = sys.argv[1:]
    links = _links_from_args(args)

    # Already open? Hand the links (or just "come to front") to that window.
    if "--restarted" in args:
        for _ in range(50):
            if not _running_pid():
                break
            time.sleep(0.1)
    elif _running_pid():
        name = os.path.join(inbox_dir(), f"{time.time():.6f}.txt")
        with open(name, "w", encoding="utf-8") as f:
            f.write(links or "__focus__")
        return

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    if IS_MAC:
        try:  # menu bar shows "SkipMan" instead of "Python"
            from Foundation import NSBundle
            info = NSBundle.mainBundle().infoDictionary()
            info["CFBundleName"] = "SkipMan"
            info["CFBundleDisplayName"] = "SkipMan"
        except Exception:
            pass

    import webview
    from skipman.store import Store
    from skipman.library import LibraryIndex
    from skipman.api import Api

    store = Store()
    library = LibraryIndex(store)
    api = Api(store, library)

    window = webview.create_window(
        "SkipMan", url=os.path.join(UI_DIR, "index.html"), js_api=api,
        width=720, height=720, min_size=(600, 540),
        background_color="#1e1e1e", text_select=True)
    api.attach(window)

    def on_start():
        if IS_MAC:
            _mac_icon()
        api.startup()
        api.watch_inbox()
        if links:
            time.sleep(1.0)
            api.add_text(links)

    try:
        webview.start(on_start, debug=bool(os.environ.get("SKIPMAN_DEBUG")))
    finally:
        try:
            os.remove(PID_FILE)
        except OSError:
            pass


def _mac_icon():
    try:
        from AppKit import NSApplication, NSImage
        from PyObjCTools import AppHelper
        icon = os.path.join(APP_DIR, "skipman", "ui", "icon.png")

        def _set():
            img = NSImage.alloc().initWithContentsOfFile_(icon)
            if img:
                NSApplication.sharedApplication().setApplicationIconImage_(img)
        AppHelper.callAfter(_set)
    except Exception:
        pass


if __name__ == "__main__":
    main()
