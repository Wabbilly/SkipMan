# ── Persistent Store — everything SkipMan remembers about your choices ──────
# Autofill (artists / albums), download history (dupe check), settings, and
# the "learning" data behind artist identification: accounts that are
# reposts vs. the real artist, your preferred artist spellings, and every
# correction you've made. Single JSON file, atomic writes, thread-safe.

import json
import os
import threading
import time

from skipman.paths import data_dir

STORE_PATH = os.path.join(data_dir(), "store.json")

# Spellings you prefer over what the catalog says. Learned as you correct.
DEFAULT_ALIASES = {"ye": "Kanye West"}

_DEFAULT = {
    "version": 3,
    "settings": {},
    "artists": {},           # name -> use count
    "albums": {},            # album -> {"artist": str, "count": int}
    "history": [],           # [{title, artist, album, key, file, date}]
    "am_cache": None,        # cached Apple Music library scan
    "aliases": {},           # lower(catalog spelling) -> your spelling
    "accounts": {},          # lower(uploader) -> "repost" | "official"
    "corrections": {},       # key (url id / raw title) -> {title, artist}
}

_MAX_HISTORY = 5000


def _norm_key(s):
    return " ".join((s or "").lower().split())


class Store:
    def __init__(self, path=STORE_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._data = self._load()

    # ── Persistence ─────────────────────────────────────────────────────────
    def _load(self):
        base = json.loads(json.dumps(_DEFAULT))
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            base.update(data)
        except Exception:
            pass
        return base

    def save(self):
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
            except Exception:
                pass

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
                self._data["history"] = self._data["history"][-_MAX_HISTORY:]
        self.save()

    def artist_suggestions(self, prefix=""):
        p = prefix.lower().strip()
        with self._lock:
            hits = [(n, c) for n, c in self._data["artists"].items()
                    if not p or p in n.lower()]
        hits.sort(key=lambda x: (not x[0].lower().startswith(p), -x[1],
                                 x[0].lower()))
        return [n for n, _ in hits[:8]]

    def album_suggestions(self, prefix="", artist=None):
        p = prefix.lower().strip()
        a = (artist or "").lower().strip()
        with self._lock:
            items = list(self._data["albums"].items())
        hits = [(n, r) for n, r in items if not p or p in n.lower()]
        hits.sort(key=lambda x: (
            not (a and x[1].get("artist", "").lower() == a),
            not x[0].lower().startswith(p), -x[1].get("count", 0),
            x[0].lower()))
        return [n for n, _ in hits[:8]]

    def album_artist(self, album):
        with self._lock:
            rec = self._data["albums"].get((album or "").strip())
        return rec.get("artist", "") if rec else ""

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

    # ── Learning: preferred spellings ───────────────────────────────────────
    def preferred_name(self, name):
        """Your spelling for an artist (e.g. 'Ye' -> 'Kanye West')."""
        k = _norm_key(name)
        with self._lock:
            hit = self._data["aliases"].get(k)
        return hit or DEFAULT_ALIASES.get(k) or name

    def learn_alias(self, catalog_name, your_name):
        if not catalog_name or not your_name:
            return
        if _norm_key(catalog_name) == _norm_key(your_name):
            return
        with self._lock:
            self._data["aliases"][_norm_key(catalog_name)] = your_name.strip()
        self.save()

    # ── Learning: uploader accounts ─────────────────────────────────────────
    def account_kind(self, uploader):
        with self._lock:
            return self._data["accounts"].get(_norm_key(uploader))

    def learn_account(self, uploader, kind):
        if not uploader:
            return
        with self._lock:
            self._data["accounts"][_norm_key(uploader)] = kind
        self.save()

    # ── Learning: exact corrections ─────────────────────────────────────────
    def correction(self, *keys):
        with self._lock:
            for k in keys:
                if k and _norm_key(k) in self._data["corrections"]:
                    return dict(self._data["corrections"][_norm_key(k)])
        return None

    def learn_correction(self, keys, title, artist):
        with self._lock:
            for k in keys:
                if k:
                    self._data["corrections"][_norm_key(k)] = {
                        "title": title, "artist": artist}
        self.save()
