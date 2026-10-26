# SkipMan v2

Download songs (YouTube / SoundCloud / more), tag them, and send them to
Apple Music — in a small retro window that does the work for you.

## What it does

1. Paste a URL (song **or playlist**) and hit ADD.
2. SkipMan checks it against your library (download history + Apple Music
   scan) and warns you about duplicates before wasting a download.
3. Downloads run on a background worker — keep pasting links or editing
   tags while they come in at 320kbps MP3.
4. The edit screen autofills artists/albums you've used before, embeds
   artwork, cleans the filename, and uploads to Apple Music's
   "Automatically Add" folder.
5. Playlists become albums: arrange the track order on one quick screen,
   and every track is tagged with album, album artist, track number and
   artwork — auto-uploaded as each one finishes if you want.

## Files

| Path | What it is |
|---|---|
| `SkipMan.bat` / `SkipMan.vbs` / `skipman.pyw` | Launchers (double-click the .bat) |
| `skipman/app.py` | Main window, screen switching, worker events |
| `skipman/worker.py` | Background download queue (the pipelining) |
| `skipman/downloader.py` | yt-dlp probe + download |
| `skipman/download_screen.py` | Screen 1 — paste URLs, queue, log |
| `skipman/edit_screen.py` | Screen 2 — tags, artwork, upload |
| `skipman/album_screen.py` | Screen 3 — arrange playlist → album |
| `skipman/store.py` | Persistent memory (autofill, history, settings) |
| `skipman/library.py` | Duplicate detection index |
| `skipman/metadata.py` | ID3 read/write + filename cleanup |
| `skipman/itunes.py` | Apple Music integration |
| `skipman/ffmpeg_setup.py` | FFmpeg auto-download |
| `skipman/theme.py` / `widgets.py` | Retro theme + autofill/popup widgets |

User data (autofill memory, history, settings, Apple Music scan cache)
lives in `%LOCALAPPDATA%\SkipMan\store.json` — delete that file for a
factory reset. Deleting it also clears duplicate-detection history.

## RULES — editing & pushing live

These exist so future edits stay painless. Follow them every time.

1. **Edit in ONE place only:** `Desktop\Superdev\BBProjectDevelopment\SkipMan`
   is the working copy. **Never** edit `Desktop\Superdev\SongDL` by hand —
   it's the git mirror and gets overwritten on every push.
2. **Test before pushing:** double-click `SkipMan.bat` and make sure the
   app opens and a download works. `update.ps1` also refuses to push if
   any file fails to compile.
3. **Log every change:** add a line (or a dated section) to `CHANGELOG.md`
   describing what you changed. If the change is user-visible, bump the
   version in `skipman/__init__.py` (that's the only place the version
   number lives — the window title and screens read it from there).
4. **Push live with one command** (from the SkipMan folder, right-click →
   "Run with PowerShell" or):

   ```powershell
   .\update.ps1 "what you changed"
   ```

   This compiles everything, mirrors the working copy into `SongDL`,
   commits, and pushes to GitHub (Wabbilly/SkipMan). No message?
   It uses a dated default.
5. **Don't commit junk:** `__pycache__`, `downloads/`, `ffmpeg/`, logs and
   the store file are excluded by the sync + `.gitignore`. Keep it that way.

## Requirements

Python 3.11+ with tkinter. Everything else (yt-dlp, mutagen, Pillow,
requests) auto-installs on first run; FFmpeg auto-downloads next to the
app. `pip install -r requirements.txt` works too.
