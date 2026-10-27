# ── SkipMan — start here ────────────────────────────────────────────────────
# python main.py [links or .webloc/.url files to add]

import os
import plistlib
import sys
import time

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skipman.paths import data_dir, inbox_dir, UI_DIR, BUNDLE_DIR, IS_MAC, IS_WIN  # noqa
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


def selftest(url=None):
    """Used by the release build to prove the packaged app really works:
    every module loads, FFmpeg runs, identification works, and (with a URL)
    a real download + MP3 conversion + tagging succeeds. No window."""
    import subprocess
    import tempfile
    import webview  # noqa: F401  (must be bundled)
    from skipman.ffmpeg import ensure_ffmpeg
    from skipman import identify, catalog, applemusic, updater  # noqa: F401
    ff = ensure_ffmpeg(print)
    exe = os.path.join(ff, "ffmpeg" + (".exe" if IS_WIN else "")) if ff else "ffmpeg"
    out = subprocess.run([exe, "-hide_banner", "-version"], capture_output=True,
                         text=True)
    print("ffmpeg:", out.stdout.splitlines()[0] if out.stdout else out.stderr)
    assert out.returncode == 0, "ffmpeg failed to run"
    assert os.path.exists(os.path.join(UI_DIR, "index.html")), "UI missing"
    r = identify.identify({"title": "Drake ft. Future - Life Is Good (Official "
                           "Video)", "uploader": "RapVibes", "duration": 238,
                           "extractor": "youtube"}, None, catalog.LOOKUPS)
    print("identify:", r["artist"], "|", r["title"], "|", r["confidence"])
    if url:
        from skipman.downloader import download_song
        from skipman.metadata import write_tags, read_tags
        res = download_song(url, tempfile.mkdtemp(), ffmpeg_location=ff)
        write_tags(res["file_path"], title="Test", artist="SkipMan")
        tags = read_tags(res["file_path"])
        size = os.path.getsize(res["file_path"])
        print("download:", os.path.basename(res["file_path"]), size, "bytes,",
              tags["title"], "/", tags["artist"])
        assert size > 100_000 and tags["artist"] == "SkipMan"
    print("SELFTEST OK")


def _mac_event_handlers(api):
    """Links / .webloc files dropped on the Dock icon while SkipMan is open,
    and skipman:// links, arrive as Apple Events. Route them to the queue."""
    try:
        import objc
        from Foundation import NSObject, NSAppleEventManager, NSURL
        from PyObjCTools import AppHelper

        def fourcc(s):
            return int.from_bytes(s.encode(), "big")

        class Handler(NSObject):
            @objc.typedSelector(b"v@:@@")
            def gotURL_reply_(self, event, reply):
                d = event.paramDescriptorForKeyword_(fourcc("----"))
                text = _links_from_args([d.stringValue()]) if d else ""
                if text:
                    api.add_text(text)

            @objc.typedSelector(b"v@:@@")
            def openDocs_reply_(self, event, reply):
                lst = event.paramDescriptorForKeyword_(fourcc("----"))
                paths = []
                for i in range(1, (lst.numberOfItems() if lst else 0) + 1):
                    d = lst.descriptorAtIndex_(i).coerceToDescriptorType_(
                        fourcc("furl"))
                    if d and d.stringValue():
                        paths.append(NSURL.URLWithString_(d.stringValue()).path())
                text = _links_from_args(paths)
                if text:
                    api.add_text(text)

        h = Handler.alloc().init()
        _keep.append(h)

        def install():
            m = NSAppleEventManager.sharedAppleEventManager()
            m.setEventHandler_andSelector_forEventClass_andEventID_(
                h, b"gotURL:reply:", fourcc("GURL"), fourcc("GURL"))
            m.setEventHandler_andSelector_forEventClass_andEventID_(
                h, b"openDocs:reply:", fourcc("aevt"), fourcc("odoc"))
        AppHelper.callAfter(install)
    except Exception as e:
        print("Dock drop handlers unavailable:", e)


_keep = []


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        # Windowed builds have no console: log to a file, exit with a code
        log = os.environ.get("SKIPMAN_SELFTEST_LOG") or os.path.join(
            data_dir(), "selftest.log")
        rest = [a for a in args if a.startswith("http")]
        with open(log, "w", encoding="utf-8") as f:
            sys.stdout = sys.stderr = f
            try:
                selftest(rest[0] if rest else None)
                code = 0
            except BaseException:
                import traceback
                traceback.print_exc()
                code = 1
            f.flush()
        os._exit(code)
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

    if IS_MAC and not getattr(sys, "frozen", False):
        try:  # menu bar shows "SkipMan" instead of "Python" (source runs)
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

    smoke = os.environ.get("SKIPMAN_SMOKE_LOG")

    def on_start():
        if smoke:   # build check: window opens + UI talks to Python, then quit
            ok = api.ui_loaded.wait(90)
            with open(smoke, "w") as f:
                f.write("UI OK\n" if ok else "UI DID NOT LOAD\n")
            window.destroy()
            return
        if IS_MAC:
            _mac_icon()
            _mac_event_handlers(api)
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
        if getattr(sys, "frozen", False):
            return  # the real app already has its icon
        icon = os.path.join(BUNDLE_DIR, "skipman", "ui", "icon.png")

        def _set():
            img = NSImage.alloc().initWithContentsOfFile_(icon)
            if img:
                NSApplication.sharedApplication().setApplicationIconImage_(img)
        AppHelper.callAfter(_set)
    except Exception:
        pass


if __name__ == "__main__":
    main()
