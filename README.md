# SkipMan v3

Download songs (YouTube / SoundCloud / more), get the tags right, and send
them to Apple Music — in one small retro window. Works on Mac and Windows.

## How it works

1. **Paste a link** (or drop it on the window / Dock icon, or just copy it —
   SkipMan offers any music link you've copied when you switch to it).
2. SkipMan says what it is: a **song**, or a **playlist** → saved as an
   **album** (or flip it to separate songs). Albums can be dragged into
   order before anything downloads.
3. Downloads run in the background while SkipMan **figures out the real
   artist and title** (see below). Each row gets a light:
   🟢 matched · 🟡 best guess · 🔴 check me.
4. You review each song, fix anything, hit **Enter** → it goes to Apple Music.
   On Mac it also lands in a **"SkipMan" playlist** (created automatically).

## Artist identification

Trust order: your past corrections → Apple's catalog (Deezer as backup;
only accepted when title, artist **and length** agree) → YouTube Music
fields → the title ("Artist - Song", "Song by Artist", …) → the uploader,
only if it's the artist's own account. Optional: identify by sound
(AcoustID key in ⚙ Settings + `brew install chromaprint`).

Rules: repost accounts never become the artist · `(feat. X)` only for real
guests · remixes keep the original artist · two credited leads both go in
the artist field · slowed / sped up / prod. by / live / remastered /
acoustic / demo stay in the title · your spellings win (Kanye West, not Ye).

It learns: fix an artist once and SkipMan remembers that upload, whether the
account was a repost page, and your preferred spelling.

## Install

**Mac:** double-click `mac/install.command` (one time). It sets up
everything, adds SkipMan to Applications and the Dock, and opens it.

**Windows:** double-click `SkipMan.bat` (first run takes a minute).

**Updates are automatic** on both: every launch checks GitHub
(Wabbilly/SkipMan) and installs anything new, then shows a RESTART button.

## Files

| Path | What it is |
|---|---|
| `main.py` | Starts the app (one window; extra launches hand links to it) |
| `skipman/api.py` | The controller: queue, albums, review, sending |
| `skipman/identify.py` | Artist/title identification + learning |
| `skipman/catalog.py` | Apple / Deezer catalog + AcoustID lookups |
| `skipman/applemusic.py` | Mac Music app + Windows auto-add folder |
| `skipman/downloader.py`, `worker.py` | yt-dlp probe + background downloads |
| `skipman/library.py` | Duplicate check against history + Apple Music |
| `skipman/store.py` | Everything SkipMan remembers |
| `skipman/updater.py` | Auto-update from GitHub |
| `skipman/ui/` | The window (HTML/CSS/JS, Winamp-style) |
| `mac/` | Mac installer + Dock launcher · `SkipMan.bat` = Windows |
| `tests/` | `python -m pytest tests` |

Your data (memory, history, settings) lives in
`~/Library/Application Support/SkipMan` (Mac) or `%LOCALAPPDATA%\SkipMan`
(Windows). Delete `store.json` there for a factory reset.

## Changing SkipMan

Edit, run `python -m pytest tests`, add a line to `CHANGELOG.md`, bump
`skipman/__init__.py` if it's user-visible, push to `master`. Both computers
pick it up on their next launch.
