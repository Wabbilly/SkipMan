# ── Library Index — duplicate detection ─────────────────────────────────────
# Answers: "is this song already in your library?"
# Sources: 1) SkipMan's own download history   2) a scan of the Apple Music
# media folder (cached; rescanned only when the folder changes).

import os
import re
import threading
import difflib

AM_MEDIA = os.path.join(
    os.path.expanduser("~"), "Music", "Apple Music", "Media")

AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".aiff", ".wav", ".flac", ".ogg", ".opus"}

# Junk commonly found in video titles that isn't part of the song title
_JUNK = re.compile(
    r"\((official|lyric|lyrics|audio|video|visualizer|hd|hq|4k|music video"
    r"|official video|official audio|official music video)[^)]*\)"
    r"|\[(official|lyric|lyrics|audio|video|visualizer|hd|hq|4k)[^\]]*\]",
    re.I)
_FEAT = re.compile(r"\b(feat\.?|ft\.?|featuring)\b.*$", re.I)
_NONWORD = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalize(text):
    """Normalize a title/artist for comparison."""
    t = (text or "").lower()
    t = _JUNK.sub(" ", t)
    t = _FEAT.sub(" ", t)
    t = _NONWORD.sub(" ", t)
    t = _SPACES.sub(" ", t).strip()
    return t


def split_title(raw_title):
    """'Artist - Title' -> (artist, title); otherwise ('', title)."""
    if " - " in (raw_title or ""):
        a, t = raw_title.split(" - ", 1)
        return a.strip(), t.strip()
    return "", (raw_title or "").strip()


class LibraryIndex:
    """In-memory index of known (title, artist) pairs for dupe checks."""

    def __init__(self, store):
        self.store = store
        self._lock = threading.Lock()
        self._entries = []      # [(norm_title, norm_artist, source, label)]
        self._scanning = False
        self._load_history()

    # ── Build ───────────────────────────────────────────────────────────────
    def _load_history(self):
        entries = []
        for h in self.store.history():
            nt = normalize(h.get("title"))
            if nt:
                entries.append(
                    (nt, normalize(h.get("artist")), "SkipMan history",
                     self._label(h.get("title"), h.get("artist"))))
        with self._lock:
            self._entries = entries
        # Cached Apple Music scan from a previous run, if any
        cache = self.store.get_am_cache()
        if cache and cache.get("tracks"):
            self._add_am_tracks(cache["tracks"])

    @staticmethod
    def _label(title, artist):
        return f'"{title}" — {artist}' if artist else f'"{title}"'

    def _add_am_tracks(self, tracks):
        adds = []
        for t in tracks:
            nt = normalize(t.get("title"))
            if nt:
                adds.append((nt, normalize(t.get("artist")), "Apple Music",
                             self._label(t.get("title"), t.get("artist"))))
        with self._lock:
            self._entries.extend(adds)

    def add(self, title, artist):
        """Register a newly-saved song (so the same session catches repeats)."""
        nt = normalize(title)
        if nt:
            with self._lock:
                self._entries.append(
                    (nt, normalize(artist), "SkipMan history",
                     self._label(title, artist)))

    # ── Apple Music scan (background, cached) ───────────────────────────────
    def scan_apple_music_async(self, on_done=None):
        """Scan the Apple Music media folder in a background thread."""
        if self._scanning or not os.path.isdir(AM_MEDIA):
            return
        self._scanning = True

        def _scan():
            try:
                files = []
                for root, _dirs, names in os.walk(AM_MEDIA):
                    for n in names:
                        if os.path.splitext(n)[1].lower() in AUDIO_EXTS:
                            files.append(os.path.join(root, n))
                sig = f"{len(files)}"
                cache = self.store.get_am_cache()
                if cache and cache.get("sig") == sig:
                    return  # Cache already loaded in _load_history

                tracks = []
                try:
                    import mutagen
                except ImportError:
                    mutagen = None
                for fp in files:
                    title = artist = ""
                    if mutagen:
                        try:
                            m = mutagen.File(fp, easy=True)
                            if m:
                                title = (m.get("title") or [""])[0]
                                artist = (m.get("artist") or [""])[0]
                        except Exception:
                            pass
                    if not title:
                        a, t = split_title(os.path.splitext(
                            os.path.basename(fp))[0])
                        title, artist = t, a or artist
                    if title:
                        tracks.append({"title": title, "artist": artist})

                self.store.set_am_cache({"sig": sig, "tracks": tracks})
                # Rebuild from history + fresh scan (avoids stale dupes)
                self._load_history()
                if on_done:
                    on_done(len(tracks))
            finally:
                self._scanning = False

        threading.Thread(target=_scan, daemon=True).start()

    # ── Check ───────────────────────────────────────────────────────────────
    def check(self, title, artist=""):
        """
        Return a match dict {source, label} if (title, artist) looks like
        something already in the library, else None.
        """
        nt = normalize(title)
        na = normalize(artist)
        if not nt:
            return None
        # Also try splitting "Artist - Title" out of the raw title
        sa, st = split_title(title)
        nt2, na2 = normalize(st), normalize(sa)

        with self._lock:
            entries = list(self._entries)

        for cand_t, cand_a in ((nt, na), (nt2, na2 or na)):
            if not cand_t:
                continue
            for et, ea, source, label in entries:
                if et == cand_t:
                    # Same title; require compatible artist if both known
                    if not cand_a or not ea or cand_a == ea \
                            or cand_a in ea or ea in cand_a:
                        return {"source": source, "label": label}
                elif abs(len(et) - len(cand_t)) <= 6 and cand_a and ea \
                        and cand_a == ea:
                    if difflib.SequenceMatcher(None, et, cand_t).ratio() > 0.92:
                        return {"source": source, "label": label}
        return None
