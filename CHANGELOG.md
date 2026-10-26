# SkipMan Changelog

All notable changes to SkipMan live here. Add a dated entry at the top
every time you change the app (see README.md for the update rules).

## v3.0.0 — 2026-10-26

Full rebuild: simpler, smarter, and now on Mac.

### Changed
- **One window.** Paste bar, queue and tag panel together; no more jumping
  between Download / Edit / Arrange screens or the EDIT READY button.
- **One action.** SAVE TAGS + UPLOAD merged into SEND (or Enter), which
  jumps straight to the next ready song.
- **Albums inline.** Playlists show as an album group you drag into order
  right in the queue; one toggle for album vs. separate songs. Nothing
  downloads until you hit DOWNLOAD. "SEND n READY" sends a whole album.
- **Duplicates inline** (amber DUPE + SKIP / GET IT ANYWAY), no popup.
- Save folder moved to ⚙ Settings; log box removed (status bar instead).
- New UI engine (pywebview) so the Winamp/mIRC look renders the same on
  Mac and Windows.

### Added
- **Mac version** with installer, Dock icon, and Apple Music import via the
  Music app + an automatic **"SkipMan" playlist**.
- **Smart artist identification** with confidence lights, Apple + Deezer
  catalog checks (title + artist + length), repost-account detection,
  feat./remix/lead-artist rules, version-tag handling, preferred spellings
  and learning from every correction. Optional AcoustID sound matching.
- Official HD artwork from the catalog; YouTube thumbnails cropped square.
- Copied-link detection, drop links on the window or Dock icon,
  `skipman://add?url=` links.
- **Auto-update on launch** from GitHub (replaces update.ps1).
- Tests for the identification rules.

### Removed
- update.ps1 / SongDL mirror workflow, SkipMan.vbs, SkipMan.pyw, Tkinter
  screens, runtime pip installs, Windows-only FFmpeg zip download.

## v2.0.0 — 2026-08-31

### Added
- **Autofill memory** — SkipMan now remembers every artist and album you
  save. The ARTIST and ALBUM fields suggest matches as you type (Up/Down
  to navigate, Enter/Tab to accept). Picking a known album fills in its
  artist automatically, and a title you've saved before recalls its artist.
- **Pipelined queue** — downloads now run on a background worker, so the
  next songs keep downloading *while you edit tags*. When you finish a
  song, the next one is usually already waiting. An "EDIT READY (n)"
  button and status-bar counters show the pipeline state.
- **SoundCloud/YouTube playlist → album** — paste a playlist URL and a new
  ARRANGE ALBUM screen appears: album name (defaults to the playlist
  title), album artist (defaults to the uploader), and a drag-to-reorder
  track list. Tracks download in your order with proper track numbers
  (TRCK), album (TALB) and album-artist (TPE2) tags, plus embedded
  artwork, and can auto-upload to Apple Music as they finish — or flow
  through the edit screen one by one if you prefer.
- **Duplicate detection** — before a song is queued, SkipMan checks it
  against your download history AND a background scan of your Apple Music
  media folder (cached between runs). A retro popup asks SKIP IT /
  DOWNLOAD ANYWAY; playlist tracks get an amber [DUPE] tag and a
  DROP DUPES button.
- **Persistent settings** — save folder and album options are remembered
  between runs (stored in %LOCALAPPDATA%\SkipMan\store.json).
- **Clean filenames** — downloads save as "Title [videoid].mp3" (so two
  songs with the same name never overwrite each other) and are renamed to
  "Artist - Title.mp3" when you save tags.
- update.ps1 — single-command push that syncs the working copy to the git
  repo and pushes to GitHub. README.md + this changelog.

### Changed
- URL adding now probes the link first (shows the real song title in the
  queue instead of the raw URL) and detects playlists automatically.
- Track metadata support extended: TPE2 (album artist) and TRCK
  (track number) tags.
- Version bumped to 2.0.0; store/theme/widgets/worker/library/album_screen
  modules added.

### Unchanged (on purpose)
- The retro Winamp/mIRC look, the small ~700x640 window, the segmented
  green progress bar, the Apple Music auto-add upload flow, and FFmpeg
  auto-setup all work exactly as before.

## v1.0.0 — 2026-02/03

- Original release: URL queue, one-at-a-time download → edit → upload
  loop, ID3 tagging with artwork, Apple Music auto-add integration,
  FFmpeg auto-download, dependency auto-install.
