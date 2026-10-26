# ── Apple Music hand-off ────────────────────────────────────────────────────
# Mac:     tells the Music app to import the file directly and adds it to a
#          "SkipMan" playlist (created automatically the first time).
# Windows: copies into Apple Music's "Automatically Add" folder (Windows
#          Apple Music can't be scripted, so no playlist there).

import os
import shutil
import subprocess
from pathlib import Path

from skipman.paths import IS_MAC, IS_WIN

PLAYLIST = "SkipMan"

_MAC_ADD = r'''
on run argv
    set theFile to (POSIX file (item 1 of argv)) as alias
    set plName to item 2 of argv
    tell application "Music"
        if not (exists user playlist plName) then
            make new user playlist with properties {name:plName}
        end if
        set t to add theFile to user playlist plName
        try
            return (name of t) & " — " & (artist of t)
        on error
            return "added"
        end try
    end tell
end run
'''

# Library listing for duplicate checks (fast bulk read via JavaScript)
_MAC_LIBRARY = r'''
const m = Application("Music");
const t = m.libraryPlaylists[0].tracks;
JSON.stringify({n: t.name(), a: t.artist()});
'''

_WIN_FOLDERS = [
    Path.home() / "Music" / "Apple Music" / "Media" / "Automatically Add to Apple Music",
    Path.home() / "Music" / "iTunes" / "iTunes Media" / "Automatically Add to iTunes",
]


def send(file_path, playlist=PLAYLIST):
    """Add a song to Apple Music. Returns a short status message."""
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if IS_MAC:
        r = subprocess.run(["osascript", "-e", _MAC_ADD, file_path, playlist],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            err = (r.stderr or "").strip()
            if "-1743" in err or "Not authorized" in err:
                raise RuntimeError(
                    "macOS blocked SkipMan from controlling Music. Open System "
                    "Settings → Privacy & Security → Automation and allow "
                    "SkipMan (or Terminal/Python) to control Music.")
            raise RuntimeError(f"Music app error: {err[:300]}")
        return f'Added to Apple Music + "{playlist}" playlist'

    if IS_WIN:
        folder = next((f for f in _WIN_FOLDERS if f.exists()), None)
        if not folder:
            raise RuntimeError(
                "Apple Music's auto-add folder wasn't found. Open Apple Music "
                "once, then try again.")
        shutil.copy2(file_path, folder / os.path.basename(file_path))
        _win_launch_music()
        return "Added to Apple Music"

    raise RuntimeError("Apple Music isn't available on this computer.")


def _win_launch_music():
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq AppleMusic.exe",
                            "/NH"], capture_output=True, text=True, timeout=5,
                           creationflags=flags)
        if "applemusic.exe" in r.stdout.lower():
            return
        ps = ("$a = Get-StartApps | Where-Object { $_.Name -like 'Apple Music*' }"
              " | Select-Object -First 1; if ($a) { Start-Process "
              "('shell:AppsFolder\\' + $a.AppID) }")
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                          "-Command", ps], creationflags=flags)
    except Exception:
        pass


def library_tracks():
    """[(title, artist)] already in Apple Music, for duplicate checks.
    Returns None if it can't be read (falls back to a folder scan)."""
    if not IS_MAC:
        return None
    try:
        import json
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", _MAC_LIBRARY],
                           capture_output=True, text=True, timeout=90)
        if r.returncode != 0:
            return None
        d = json.loads(r.stdout)
        return list(zip(d.get("n") or [], d.get("a") or []))
    except Exception:
        return None


def media_folder():
    """Where Apple Music keeps files (used for the fallback scan)."""
    for p in (Path.home() / "Music" / "Music" / "Media",
              Path.home() / "Music" / "Apple Music" / "Media",
              Path.home() / "Music" / "iTunes" / "iTunes Media"):
        if p.exists():
            return str(p)
    return None
