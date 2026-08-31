# ── yt-dlp Wrapper — probe + download ───────────────────────────────────────

import os
import re


APPLE_MUSIC_PATTERN = re.compile(r"(music\.apple\.com|itunes\.apple\.com)", re.I)


def detect_apple_music(url):
    """Check if URL is an Apple Music / iTunes link (DRM-protected)."""
    return bool(APPLE_MUSIC_PATTERN.search(url))


def _base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": False,
    }


def probe(url):
    """
    Fetch info WITHOUT downloading. Fast (flat) for playlists.

    Returns dict:
      {"kind": "single", "entry": {title, artist, url, id}}
      {"kind": "playlist", "title": str, "uploader": str,
       "entries": [{title, artist, url, id}, ...]}

    Raises ValueError for Apple Music links, Exception on failure.
    """
    if detect_apple_music(url):
        raise ValueError(
            "Apple Music links are DRM-protected and cannot be downloaded.\n"
            "Paste a YouTube or SoundCloud link instead."
        )

    import yt_dlp

    opts = _base_opts()
    opts["extract_flat"] = "in_playlist"

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    def _entry(e, fallback_url=None):
        url = e.get("url") or e.get("webpage_url") or fallback_url or ""
        title = e.get("title")
        guess = False
        if not title or title == "Unknown":
            # Flat playlist entries (e.g. SoundCloud) may omit the title —
            # derive a readable one from the URL slug; the real title is
            # picked up when the track actually downloads.
            slug = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
            title = slug.replace("-", " ").replace("_", " ").strip().title() \
                or "Unknown"
            guess = True
        return {
            "title": title,
            "artist": e.get("artist") or e.get("creator")
                      or e.get("uploader") or "",
            "url": url,
            "id": e.get("id") or "",
            "guess": guess,
        }

    if info.get("_type") == "playlist" or "entries" in info:
        entries = [
            _entry(e) for e in (info.get("entries") or []) if e
        ]
        return {
            "kind": "playlist",
            "title": info.get("title") or "Playlist",
            "uploader": info.get("uploader") or info.get("channel") or "",
            "entries": entries,
        }

    return {"kind": "single", "entry": _entry(info, fallback_url=url)}


def download_song(url, save_dir, progress_callback=None, ffmpeg_location=None):
    """
    Download audio from URL and convert to 320kbps MP3.

    Returns dict: {title, artist, album, thumbnail_url, file_path}
    Raises ValueError for Apple Music links, Exception on failure.
    """
    if detect_apple_music(url):
        raise ValueError(
            "Apple Music links are DRM-protected and cannot be downloaded.\n"
            "Paste a YouTube or SoundCloud link instead."
        )

    import yt_dlp

    os.makedirs(save_dir, exist_ok=True)

    # Include the video id so two songs with the same title never clobber
    # each other; the id is stripped again on the edit screen save.
    outtmpl = os.path.join(save_dir, "%(title)s [%(id)s].%(ext)s")

    opts = _base_opts()
    opts.update({
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
    })

    if ffmpeg_location:
        opts["ffmpeg_location"] = ffmpeg_location

    if progress_callback:
        opts["progress_hooks"] = [progress_callback]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        prepared = ydl.prepare_filename(info)
        mp3_path = os.path.splitext(prepared)[0] + ".mp3"

    title = info.get("title") or "Unknown"
    artist = info.get("artist") or info.get("creator") or info.get("uploader") or ""
    album = info.get("album") or ""
    thumbnail = info.get("thumbnail") or ""

    # Fallback: if the expected path doesn't exist, search for latest .mp3
    if not os.path.exists(mp3_path):
        mp3_files = [
            os.path.join(save_dir, f)
            for f in os.listdir(save_dir)
            if f.lower().endswith(".mp3")
        ]
        if mp3_files:
            mp3_path = max(mp3_files, key=os.path.getmtime)

    return {
        "title": title,
        "artist": artist,
        "album": album,
        "thumbnail_url": thumbnail,
        "file_path": mp3_path,
    }
