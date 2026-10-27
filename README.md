<p align="center"><img src="skipman/ui/icon.png" width="96" alt=""></p>

# SkipMan

Download songs from YouTube, SoundCloud and more, get the tags right, and send
them straight to Apple Music, all in one small retro window. For Mac and
Windows.

## Download

Get the latest version from **[Releases](https://github.com/Wabbilly/SkipMan/releases/latest)**:

- **Mac (Apple Silicon):** `SkipMan-mac-apple-silicon.zip`. Unzip, drag
  SkipMan to Applications, open it. The first time, macOS blocks it because
  it's not from the App Store: go to System Settings → Privacy & Security →
  **Open Anyway**.
- **Windows 10/11:** `SkipMan-windows.zip`. Unzip anywhere, run
  `SkipMan.exe` (SmartScreen: **More info → Run anyway**).

Nothing else to install. FFmpeg is built in, and SkipMan **updates itself**
whenever a new release comes out.

## How it works

1. **Paste a link**, drop it on the window (or the Dock icon on Mac), or just
   copy it. SkipMan offers any music link you've copied when you switch to it.
2. SkipMan tells you what it is: a **song**, or a **playlist**, which becomes
   an **album** (or flip it to separate songs). Drag album tracks into order
   before anything downloads.
3. Downloads run in the background while SkipMan **works out the real
   artist and title**. Each row gets a light:
   🟢 matched · 🟡 best guess · 🔴 check me.
4. Review each song, fix anything, press **Enter**, and it goes to Apple Music.
   On Mac it also lands in a **"SkipMan" playlist**, created automatically.

### Getting the artist right

SkipMan trusts, in order: your own past corrections → Apple's catalog
(Deezer as backup; only accepted when title, artist **and song length**
agree) → YouTube Music's listing → the title ("Artist - Song",
"Song by Artist", …) → the uploader, but only if it's the artist's own
account.

- Repost/promo accounts never become the artist.
- `(feat. X)` only for real guests. If the song is actually X's, X is the artist.
- Remixes keep the original artist: `Song (Kaytranada Remix)`.
- Two credited lead artists both go in the artist field.
- Kept in the title: slowed / sped up / nightcore, prod. by, live,
  remastered, acoustic, demo. Removed: "Official Video", "Lyrics", "HD",
  emoji, hashtags and other junk.
- Your spellings win (e.g. Kanye West, not Ye). It **learns** from every fix.

Optional: identify badly titled uploads by sound with a free
[AcoustID](https://acoustid.org/new-application) key (⚙ Settings) plus
`fpcalc` (`brew install chromaprint` on Mac).

Your memory, history and settings live in
`~/Library/Application Support/SkipMan` (Mac) or `%LOCALAPPDATA%\SkipMan`
(Windows). Delete `store.json` there for a factory reset.

## For developers

```bash
pip install -r requirements.txt
python main.py            # run from source
python -m pytest tests    # identification rules
```

| Path | What it is |
|---|---|
| `main.py` | Entry point (single window; extra launches hand links to it) |
| `skipman/api.py` | Controller: queue, albums, review, sending |
| `skipman/identify.py` | Artist/title identification + learning |
| `skipman/catalog.py` | Apple / Deezer catalog, AcoustID |
| `skipman/applemusic.py` | Mac Music app + Windows auto-add folder |
| `skipman/downloader.py`, `worker.py` | yt-dlp + background downloads |
| `skipman/library.py`, `store.py` | Duplicate check, persistent memory |
| `skipman/updater.py` | Self-update from GitHub Releases |
| `skipman/ui/` | The window (HTML/CSS/JS) |
| `packaging/` | App build recipe (PyInstaller), icons, FFmpeg fetch |
| `.github/workflows/release.yml` | Builds + self-tests + publishes releases |

**Releasing:** bump `__version__` in `skipman/__init__.py`, add a
`## vX.Y.Z` section to `CHANGELOG.md`, and push to `master`. That's it:
GitHub builds the Mac and Windows apps, self-tests each one with a real
download and a window check, and publishes the release. Installed copies
update themselves. (Push to a `ci/...` branch for a test build that
publishes nothing.)
