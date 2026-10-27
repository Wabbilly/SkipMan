# ── Auto-update from GitHub Releases ────────────────────────────────────────
# On launch the app checks github.com/Wabbilly/SkipMan/releases for a newer
# version. If there is one, it downloads it in the background and shows a
# RESTART button; restarting swaps the new app in and reopens it. Your
# settings, memory and music are never touched.
#
# Running from source (python main.py in a git checkout) instead does a
# quiet `git pull`.

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from skipman import __version__
from skipman.paths import APP_DIR, FROZEN, IS_MAC, IS_WIN, app_bundle, data_dir

REPO = "Wabbilly/SkipMan"
_staged = {}            # what's ready to install on restart


def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s or "")[:3]) or (0,)


def asset_name():
    """Which download fits this computer."""
    if IS_MAC:
        import platform
        return ("SkipMan-mac-apple-silicon.zip" if platform.machine() == "arm64"
                else "SkipMan-mac-intel.zip")
    if IS_WIN:
        return "SkipMan-windows.zip"
    return None


def check_and_update(status=None):
    """Returns {'message', 'version'} when an update is ready, else None."""
    if os.environ.get("SKIPMAN_NO_UPDATE"):
        return None
    if not FROZEN:
        return _git_update()
    try:
        import requests
        r = requests.get(f"https://api.github.com/repos/{REPO}/releases/latest",
                         timeout=8)
        r.raise_for_status()
        rel = r.json()
    except Exception:
        return None
    latest = rel.get("tag_name", "")
    if _ver(latest) <= _ver(__version__):
        return None
    want = asset_name()
    asset = next((a for a in rel.get("assets", []) if a.get("name") == want), None)
    if not asset:
        return None
    if status:
        status(f"Downloading SkipMan {latest}…")
    try:
        new_app = _download(asset["browser_download_url"])
    except Exception:
        return None
    _staged["path"] = new_app
    return {"message": f"SkipMan {latest} is ready — hit RESTART to switch.",
            "version": latest.lstrip("v")}


def _download(url):
    import requests
    work = os.path.join(data_dir(), "update")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    zpath = os.path.join(work, "new.zip")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    out = os.path.join(work, "new")
    if IS_MAC:   # ditto keeps the app's symlinks + signature intact
        subprocess.run(["ditto", "-x", "-k", zpath, out], check=True)
        app = next(os.path.join(out, n) for n in os.listdir(out)
                   if n.endswith(".app"))
        subprocess.run(["xattr", "-dr", "com.apple.quarantine", app],
                       capture_output=True)
        return app
    with zipfile.ZipFile(zpath) as z:
        z.extractall(out)
    # zip holds a "SkipMan" folder with SkipMan.exe inside
    for root, _d, files in os.walk(out):
        if "SkipMan.exe" in files:
            return root
    raise RuntimeError("SkipMan.exe not found in update")


def restart():
    """Swap in a downloaded update (if any) and reopen SkipMan."""
    new = _staged.get("path")
    pid = os.getpid()
    if FROZEN and IS_MAC:
        target = app_bundle()
        script = (
            f'while kill -0 {pid} 2>/dev/null; do sleep 0.2; done; '
            + (f'rm -rf "{target}" && mv "{new}" "{target}"; ' if new else "")
            + f'open "{target}"')
        subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True)
    elif FROZEN and IS_WIN:
        exe = os.path.join(APP_DIR, "SkipMan.exe")
        bat = os.path.join(tempfile.gettempdir(), "skipman-update.bat")
        with open(bat, "w") as f:
            f.write("@echo off\r\n"
                    f':wait\r\ntasklist /FI "PID eq {pid}" | find "{pid}" >nul '
                    "&& (timeout /t 1 >nul & goto wait)\r\n")
            if new:
                f.write(f'robocopy "{new}" "{APP_DIR}" /E /NFL /NDL /NJH /NJS >nul\r\n')
            f.write(f'start "" "{exe}"\r\n')
        subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000)
    else:
        subprocess.Popen([sys.executable, os.path.join(APP_DIR, "main.py"),
                          "--restarted"], cwd=APP_DIR, start_new_session=True)
    os._exit(0)


def _git_update():
    if not os.path.isdir(os.path.join(APP_DIR, ".git")) or not shutil.which("git"):
        return None
    try:
        def head():
            return subprocess.run(["git", "-C", APP_DIR, "rev-parse", "HEAD"],
                                  capture_output=True, text=True, timeout=10).stdout
        before = head()
        r = subprocess.run(["git", "-C", APP_DIR, "pull", "--ff-only", "-q"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and head() != before:
            return {"message": "Pulled new code — hit RESTART to use it.",
                    "version": ""}
    except Exception:
        pass
    return None
