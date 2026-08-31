# ── Persistent Store — remembers what you've told SkipMan ───────────────────
# Powers autofill (artists / albums you've used before), download history,
# duplicate detection, and app settings. Single JSON file, atomic writes.

import json
import os
import threading
import time


def _store_dir():
    """Per-user data dir: %LOCALAPPDATA%\\SkipMan on Windows, ~/.skipman elsewhere."""
    base = os.environ.get("LOCALAPPDATA")
    if base and os.path.isdir(base):
        return os.path.join(base, "SkipMan")
    return os.path.join(os.path.expanduser("~"), ".skipman")


STORE_PATH = os.path.join(_store_dir(), "store.json")

_DEFAULT = {
    "version": 2,
    "settings": {},          # save_dir, auto_upload, etc.
    "artists": {},           # name -> use count
    "albums": {},            # album -> {"artist": str, "count": int}
    "history": [],           # [{title, artist, album, key, file, date}]
    "am_cache": None,        # cached Apple Music scan {sig, tracks}
}

_MAX_HISTORY = 2000


class Store:
    """Thread-safe persistent JSON store."""

    def __init__(self, path=STORE_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._data = self._load()

    # ── Persistence ─────────────────────────────────────────────────────────
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(_DEFAULT)
            merged.update(data)
            return merged
        except Exception:
            return json.loads(json.dumps(_DEFAULT))

    def save(self):
        """Atomic write (tmp file + replace) so a crash never corrupts data."""
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
            except Exception:
                pass  # Store is best-effort; never crash the app over it

    # ── Settings ────────────────────────────────────────────────────────────
    def get_setting(self, key, default=None):
        with self._lock:
            return self._data["settings"].get(key, default)

    def set_setting(self, key, value):
        with self._lock:
            self._data["settings"][key] = value
        self.save()

    # ── Autofill memory ─────────────────────────────────────────────────────
    def remember(self, title=None, artist=None, album=None, key=None, file=None):
        """Record a saved song: bumps artist/album counts + appends history."""
        artist = (artist or "").strip()
        album = (album or "").strip()
        title = (title or "").strip()
        with self._lock:
            if artist:
                self._data["artists"][artist] = \
                    self._data["artists"].get(artist, 0) + 1
            if album:
                rec = self._data["albums"].get(album) or {"artist": "", "count": 0}
                rec["count"] += 1
                if artist:
                    rec["artist"] = artist
                self._data["albums"][album] = rec
            if title or artist:
                self._data["history"].append({
                    "title": title, "artist": artist, "album": album,
                    "key": key or "", "file": file or "",
                    "date": time.strftime("%Y-%m-%d %H:%M"),
                })
                if len(self._data["history"]) > _MAX_HISTORY:
                    self._data["history"] = self._data["history"][-_MAX_HISTORY:]
        self.save()

    def artist_suggestions(self, prefix=""):
        """Known artists matching prefix, most-used first."""
        p = prefix.lower().strip()
        with self._lock:
            items = self._data["artists"].items()
            hits = [(n, c) for n, c in items
                    if not p or p in n.lower()]
        hits.sort(key=lambda x: (not x[0].lower().startswith(p), -x[1], x[0].lower()))
        return [n for n, _ in hits[:8]]

    def album_suggestions(self, prefix="", artist=None):
        """Known albums matching prefix; albums by `artist` rank first."""
        p = prefix.lower().strip()
        a = (artist or "").lower().strip()
        with self._lock:
            items = list(self._data["albums"].items())
        hits = [(name, rec) for name, rec in items
                if not p or p in name.lower()]
        hits.sort(key=lambda x: (
            not (a and x[1].get("artist", "").lower() == a),
            not x[0].lower().startswith(p),
            -x[1].get("count", 0), x[0].lower()))
        return [n for n, _ in hits[:8]]

    def album_artist(self, album):
        """The artist you last used with this album (for autofill)."""
        with self._lock:
            rec = self._data["albums"].get((album or "").strip())
        return rec.get("artist", "") if rec else ""

    def artist_for(self, title):
        """If this exact title was saved before, return its artist."""
        t = (title or "").lower().strip()
        with self._lock:
            for h in reversed(self._data["history"]):
                if h.get("title", "").lower().strip() == t and h.get("artist"):
                    return h["artist"]
        return ""

    # ── History / duplicate support ─────────────────────────────────────────
    def history(self):
        with self._lock:
            return list(self._data["history"])

    def get_am_cache(self):
        with self._lock:
            return self._data.get("am_cache")

    def set_am_cache(self, cache):
        with self._lock:
            self._data["am_cache"] = cache
        self.save()
