# ── yt-dlp Wrapper — probe + download ───────────────────────────────────────

import os
import re


APPLE_MUSIC_PATTERN = re.compile(r"(music\.apple\.com|itunes\.apple\.com)", re.I)


def detect_apple_music(url):
    """Check if URL is an Apple Music / iTunes link (DRM-protected)."""
    return bool(APPLE_MUSIC_PATTERN.search(url))


APPLE_MSG = ("Apple Music links are DRM-protected and cannot be downloaded.\n"
             "Paste a YouTube, SoundCloud, TikTok, Reddit, X or Instagram "
             "link instead.")

# Social sites: SkipMan keeps only the audio from their videos
SOCIAL_PATTERN = re.compile(
    r"(reddit\.com|redd\.it|(?:^|[/.@])x\.com|twitter\.com|instagram\.com|"
    r"tiktok\.com)", re.I)
SOCIAL_EXTRACTORS = ("reddit", "twitter", "instagram", "tiktok")
SITE_NAMES = (("reddit", "Reddit"), ("redd.it", "Reddit"), ("x.com", "X"),
              ("twitter", "X"), ("instagram", "Instagram"),
              ("tiktok", "TikTok"))


def is_social(url):
    return bool(SOCIAL_PATTERN.search(url or ""))


def site_name(url):
    u = (url or "").lower()
    return next((n for k, n in SITE_NAMES if k in u), "That site")


def _is_social_info(info):
    ex = (info.get("extractor_key") or info.get("extractor")
          or info.get("ie_key") or "").lower()
    return any(ex.startswith(s) for s in SOCIAL_EXTRACTORS), ex


def social_title(info):
    """Social posts come with post-style titles ("Max - look at this",
    "Video by someone", "TikTok video #123"). Turn them into the post's own
    words so the tag panel starts from something readable."""
    title = (info.get("title") or "").strip()
    social, ex = _is_social_info(info)
    if not social:
        return title
    up = (info.get("uploader") or info.get("channel") or "").strip()
    desc = (info.get("description") or "").strip()
    first = next((l.strip() for l in desc.splitlines() if l.strip()), "")
    first = re.sub(r"\s*https?://t\.co/\S+", "", first).strip()
    if ex.startswith("twitter"):
        if up and title.startswith(up + " - "):
            title = title[len(up) + 3:]
        if title.endswith(("…", "...")) and first:
            title = first
        title = re.sub(r"\s*https?://t\.co/\S+", "", title)
    elif re.match(r"^(Video|Post|Reel|Photo) by ", title) or \
            re.match(r"^TikTok video #\d+$", title) or not title:
        track = (info.get("track") or "").strip()
        if not first and track and not re.match(r"^original sound", track, re.I):
            first = track          # TikTok with no caption: the sound's name
        if not first and up:
            first = f"{up} clip"
        title = first or title
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) > 120:
        title = title[:120].rsplit(" ", 1)[0] + "…"
    return title or (info.get("title") or "")


# ── Sign-in fallback ────────────────────────────────────────────────────────
# Reddit, Instagram and X sometimes refuse anonymous downloads. When they do,
# SkipMan quietly borrows the sign-in from a browser on this computer (the
# same way yt-dlp's --cookies-from-browser does) and remembers which worked.

AUTH_ERR = re.compile(
    r"authenticat|log ?in|sign ?in|cookies|blocked|rate.?limit|"
    r"private|not available without|requested content is not available|"
    r"HTTP Error 40[13]", re.I)


def _browsers():
    import sys
    if sys.platform == "darwin":
        order = ["chrome", "safari", "firefox", "brave", "edge", "vivaldi",
                 "opera", "chromium"]
    elif sys.platform.startswith("win"):
        order = ["firefox", "edge", "chrome", "brave", "vivaldi", "opera"]
    else:
        order = ["firefox", "chrome", "chromium", "brave"]
    saved = _saved_browser()
    if saved in order:
        order.remove(saved)
        order.insert(0, saved)
    return order


def _browser_file():
    try:
        from skipman.paths import data_dir
        return os.path.join(data_dir(), "login_browser.txt")
    except Exception:
        return None


def _saved_browser():
    f = _browser_file()
    try:
        with open(f, encoding="utf-8") as fh:
            return fh.read().strip()
    except Exception:
        return ""


def _save_browser(name):
    f = _browser_file()
    if f:
        try:
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(name)
        except Exception:
            pass


class _Quiet:
    """Swallows yt-dlp chatter while trying browsers one by one."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _extract(url, opts, download):
    """extract_info; returns (info, prepared_filename_or_None)."""
    import yt_dlp
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=download)
        name = None
        if download and info:
            one = _first_entry(info)
            name = ydl.prepare_filename(one) if one else None
        return info, name


def _first_entry(info):
    if info.get("_type") == "playlist" or "entries" in info:
        return next((e for e in (info.get("entries") or []) if e), None)
    return info


def _extract_with_login(url, opts, download):
    """Try normally; for social sites that demand a sign-in, retry with the
    browser's sign-in."""
    try:
        return _extract(url, opts, download)
    except Exception as first:
        if not (is_social(url) and AUTH_ERR.search(str(first))):
            raise
        for browser in _browsers():
            o = dict(opts)
            o["cookiesfrombrowser"] = (browser,)
            o["logger"] = _Quiet()
            try:
                res = _extract(url, o, download)
            except Exception:
                continue
            _save_browser(browser)
            return res
        site = site_name(url)
        raise ValueError(
            f"{site} wants you signed in. Log in to {site} in Chrome, Safari "
            "or Firefox on this computer, then try again.") from first


ID_FIELDS = ("title", "uploader", "channel", "artist", "artists", "track",
             "album", "duration", "extractor", "id", "webpage_url",
             "thumbnail", "channel_is_verified", "creators")


def id_info(info):
    """The parts of yt-dlp's info that artist identification uses."""
    out = {k: info.get(k) for k in ID_FIELDS}
    out["extractor"] = (info.get("extractor_key") or info.get("extractor")
                        or info.get("ie_key") or "").lower()
    if _is_social_info(info)[0]:
        out["title"] = social_title(info)
    return out


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
        raise ValueError(APPLE_MSG)

    import yt_dlp

    opts = _base_opts()
    opts["extract_flat"] = "in_playlist"

    info, _ = _extract_with_login(url, opts, False)

    def _entry(e, fallback_url=None):
        url = e.get("webpage_url") or e.get("url") or fallback_url or ""
        title = social_title(e) if _is_social_info(e)[0] else e.get("title")
        guess = False
        if not title or title == "Unknown":
            # Flat playlist entries (e.g. SoundCloud) may omit the title —
            # derive a readable one from the URL slug; the real title is
            # picked up when the track actually downloads.
            slug = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
            title = slug.replace("-", " ").replace("_", " ").strip().title() \
                or "Unknown"
            guess = True
        d = id_info(e)
        d.update({"title": title, "url": url, "id": e.get("id") or "",
                  "guess": guess})
        return d

    if info.get("_type") == "playlist" or "entries" in info:
        raw = [e for e in (info.get("entries") or []) if e]
        if is_social(url):
            # Posts with one clip are songs, not albums. Posts with several
            # clips (X, Instagram carousels) become an album; each track
            # needs its own link so it downloads its own clip.
            if len(raw) <= 1:
                e = _entry(raw[0] if raw else info, fallback_url=url)
                e["url"] = url
                return {"kind": "single", "entry": e}
            base = url.split("?")[0].rstrip("/")
            out = []
            for n, e in enumerate(raw, 1):
                d = _entry(e, fallback_url=url)
                if "twitter" in d["extractor"] and \
                        re.search(r"/status/\d+$", base):
                    d["url"] = f"{base}/video/{n}"
                elif d["url"].split("?")[0].rstrip("/") == base:
                    d["url"] = f"{base}?img_index={n}" \
                        if "instagram" in d["extractor"] else d["url"]
                out.append(d)
            entries = out
            raw = None
        else:
            entries = [_entry(e) for e in raw]
        # SoundCloud sets come back without track names; for normal-size
        # sets, read each track properly so the arrange list is readable
        if raw is not None and any(e["guess"] for e in entries) \
                and len(entries) <= 40:
            try:
                full_opts = _base_opts()
                full_opts.update({"skip_download": True,
                                  "ignoreerrors": True})
                with yt_dlp.YoutubeDL(full_opts) as ydl:
                    full = ydl.extract_info(url, download=False)
                better = [e for e in (full.get("entries") or []) if e]
                if len(better) == len(entries):
                    entries = [_entry(e) for e in better]
            except Exception:
                pass
        thumbs = info.get("thumbnails") or []
        art = info.get("thumbnail") or (thumbs[-1].get("url") if thumbs else "")
        return {
            "kind": "playlist",
            "title": info.get("title") or "Playlist",
            "uploader": info.get("uploader") or info.get("channel") or "",
            "artwork": art or "",
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
        raise ValueError(APPLE_MSG)

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

    m = re.search(r"[?&]img_index=(\d+)", url)
    if m:
        # One clip out of an Instagram carousel
        opts["playlist_items"] = m.group(1)
        opts["noplaylist"] = False
        url = re.sub(r"[?&]img_index=\d+", "", url)

    info, prepared = _extract_with_login(url, opts, True)
    info = _first_entry(info) or info
    mp3_path = os.path.splitext(prepared or "")[0] + ".mp3"

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
        "info": id_info(info),
        "thumbnail_url": thumbnail,
        "file_path": mp3_path,
    }
