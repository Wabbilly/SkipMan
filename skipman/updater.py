# ── Auto-update from GitHub on launch ───────────────────────────────────────
# Checks github.com/Wabbilly/SkipMan for a newer commit. If there is one, it
# downloads it, swaps the code in place (your settings, memory and music are
# untouched) and offers a RESTART button. No scripts to run, ever.

import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from skipman.paths import APP_DIR, IS_WIN

REPO = "Wabbilly/SkipMan"
BRANCH = "master"
STAMP = os.path.join(APP_DIR, ".installed_commit")

# Never touched by an update
PROTECTED = {".venv", "venv", "ffmpeg", "downloads", ".git",
             ".installed_commit", "SkipMan.app", "__pycache__"}


def _read_stamp():
    try:
        with open(STAMP) as f:
            return f.read().strip()
    except OSError:
        return ""


def _write_stamp(sha):
    try:
        with open(STAMP, "w") as f:
            f.write(sha)
    except OSError:
        pass


def latest_commit():
    import requests
    r = requests.get(f"https://api.github.com/repos/{REPO}/commits/{BRANCH}",
                     headers={"Accept": "application/vnd.github.sha"},
                     timeout=8)
    r.raise_for_status()
    return r.text.strip()


def check_and_update(status=None):
    """Returns {'message', 'version'} if an update was installed, else None."""
    if os.environ.get("SKIPMAN_NO_UPDATE"):
        return None
    # A developer checkout: just fast-forward with git
    if os.path.isdir(os.path.join(APP_DIR, ".git")) and shutil.which("git"):
        return _git_update()
    try:
        sha = latest_commit()
    except Exception:
        return None
    have = _read_stamp()
    if not have:
        _write_stamp(sha)       # first launch: this IS the latest
        return None
    if sha == have:
        return None
    if status:
        status("Updating SkipMan…")
    try:
        _install_zip(sha)
    except Exception:
        return None
    _write_stamp(sha)
    return {"message": "SkipMan updated — hit RESTART to use the new version.",
            "version": _new_version()}


def _git_update():
    try:
        before = subprocess.run(["git", "-C", APP_DIR, "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=10).stdout
        r = subprocess.run(["git", "-C", APP_DIR, "pull", "--ff-only", "-q"],
                           capture_output=True, text=True, timeout=60)
        after = subprocess.run(["git", "-C", APP_DIR, "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=10).stdout
        if r.returncode == 0 and before != after:
            _pip_install()
            return {"message": "SkipMan updated — hit RESTART to use the new "
                               "version.", "version": _new_version()}
    except Exception:
        pass
    return None


def _install_zip(sha):
    import requests
    r = requests.get(f"https://codeload.github.com/{REPO}/zip/{sha}", timeout=60)
    r.raise_for_status()
    old_req = _read(os.path.join(APP_DIR, "requirements.txt"))
    tmp = tempfile.mkdtemp(prefix="skipman-update-")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(tmp)
    root = os.path.join(tmp, os.listdir(tmp)[0])
    for name in os.listdir(root):
        if name in PROTECTED:
            continue
        src, dst = os.path.join(root, name), os.path.join(APP_DIR, name)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    for sh in ("mac/install.command", "mac/run.sh", "SkipMan.command"):
        p = os.path.join(APP_DIR, sh)
        if os.path.exists(p):
            os.chmod(p, 0o755)
    shutil.rmtree(tmp, ignore_errors=True)
    if _read(os.path.join(APP_DIR, "requirements.txt")) != old_req:
        _pip_install()


def _pip_install():
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0
    uv = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
    req = os.path.join(APP_DIR, "requirements.txt")
    if os.path.exists(uv):
        cmd = [uv, "pip", "install", "-q", "--python", sys.executable, "-r", req]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "-q", "-r", req]
    subprocess.run(cmd, capture_output=True, timeout=600, creationflags=flags)


def _read(p):
    try:
        with open(p) as f:
            return f.read()
    except OSError:
        return ""


def _new_version():
    import re
    m = re.search(r'__version__\s*=\s*"([^"]+)"',
                  _read(os.path.join(APP_DIR, "skipman", "__init__.py")))
    return m.group(1) if m else ""


def restart():
    """Start a fresh copy of SkipMan, then quit this one."""
    args = [sys.executable, os.path.join(APP_DIR, "main.py"), "--restarted"]
    kw = {}
    if IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200   # detached
    else:
        kw["start_new_session"] = True
    subprocess.Popen(args, cwd=APP_DIR, **kw)
    os._exit(0)
