# ── FFmpeg — found or fetched automatically, Mac and Windows ────────────────

import os
import shutil
import threading

_lock = threading.Lock()
_found = [None]

_EXTRA_DIRS = ["/opt/homebrew/bin", "/usr/local/bin"]


def _has_both(d):
    exe = ".exe" if os.name == "nt" else ""
    return d and os.path.exists(os.path.join(d, "ffmpeg" + exe)) and \
        os.path.exists(os.path.join(d, "ffprobe" + exe))


def ensure_ffmpeg(status=None):
    """
    Return a folder containing ffmpeg + ffprobe (or None if they're on PATH).
    Order: already installed (PATH / Homebrew) -> the old v2 ffmpeg/ folder
    -> static-ffmpeg package (downloads a build once, ~80MB).
    """
    from skipman.paths import BUNDLE_DIR, FROZEN
    with _lock:
        if _found[0] is not None:
            return _found[0] or None
        bundled = os.path.join(BUNDLE_DIR, "ffmpeg")   # inside the app
        if _has_both(bundled):
            _found[0] = bundled
            return bundled
        if FROZEN:
            raise RuntimeError("FFmpeg is missing from this SkipMan build.")
        ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if ff and fp:
            _found[0] = ""
            return None
        for d in _EXTRA_DIRS + [os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "ffmpeg")]:
            if _has_both(d):
                _found[0] = d
                return d
        if status:
            status("First run: getting FFmpeg (one time, ~1 min)…")
        try:
            import static_ffmpeg.run as sfr
            ff, fp = sfr.get_or_fetch_platform_executables_else_raise()
            d = os.path.dirname(ff)
            _found[0] = d
            return d
        except Exception as e:
            raise RuntimeError(f"Couldn't set up FFmpeg: {e}")
