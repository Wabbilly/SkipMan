# ── SkipMan controller — everything the window can ask for ──────────────────
# The UI (skipman/ui) calls these methods through pywebview's JS bridge.
# State changes are pushed back with window.evaluate_js("SM.state(...)").

import base64
import io
import json
import os
import re
import threading
import time

from skipman import __version__, identify as ident
from skipman.catalog import LOOKUPS, fingerprint_lookup, fingerprint_available
from skipman.paths import default_save_dir, inbox_dir, IS_MAC

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
SUPPORTED = re.compile(
    r"(youtube\.com|youtu\.be|music\.youtube\.com|soundcloud\.com|"
    r"on\.soundcloud\.com|bandcamp\.com|vimeo\.com|mixcloud\.com|"
    r"audiomack\.com|tiktok\.com)", re.I)


def find_links(text):
    """All supported music links in a blob of text (paste, drop, clipboard)."""
    out = []
    for m in URL_RE.findall(text or ""):
        m = m.rstrip(").,;]")
        if SUPPORTED.search(m) and m not in out:
            out.append(m)
    return out


class Api:
    def __init__(self, store, library):
        self._store = store
        self._library = library
        self._window = None
        self._lock = threading.RLock()
        self._items = {}         # id -> item dict
        self._order = []         # top-level row order (item ids / album ids)
        self._albums = {}        # album id -> album dict
        self._seq = 0
        self._job_item = {}      # worker job id -> item id
        self._last_push = 0.0
        self._push_pending = False
        self._status = ("Starting…", "amber")
        self._offered_clip = set()
        self._update = None
        self._save_dir = store.get_setting("save_dir", default_save_dir())

        from skipman.worker import DownloadWorker, Job
        self._Job = Job
        self._worker = DownloadWorker(emit=self._on_worker,
                                     get_save_dir=lambda: self._save_dir)

    # ── Plumbing ────────────────────────────────────────────────────────────
    def attach(self, window):
        self._window = window

    def _id(self):
        with self._lock:
            self._seq += 1
            return self._seq

    def _push(self, force=False):
        """Send the current state to the UI (throttled to ~8/sec)."""
        if not self._window:
            return
        now = time.time()
        with self._lock:
            if not force and now - self._last_push < 0.12:
                if not self._push_pending:
                    self._push_pending = True
                    threading.Timer(0.13, self._push_later).start()
                return
            self._last_push = now
            payload = json.dumps(self._snapshot())
        try:
            self._window.evaluate_js(f"window.SM && SM.state({payload})")
        except Exception:
            pass

    def _push_later(self):
        with self._lock:
            self._push_pending = False
        self._push(force=True)

    def _set_status(self, msg, color="green"):
        self._status = (msg, color)
        self._push()

    def _snapshot(self):
        rows = []
        for rid in self._order:
            if rid in self._albums:
                a = self._albums[rid]
                rows.append({**{k: v for k, v in a.items() if k != "tracks"},
                             "tracks": [self._public(self._items[t])
                                        for t in a["tracks"] if t in self._items]})
            elif rid in self._items:
                rows.append(self._public(self._items[rid]))
        active, pending = self._worker.snapshot()
        return {"rows": rows, "status": self._status[0],
                "statusColor": self._status[1], "version": __version__,
                "downloading": (1 if active else 0) + len(pending),
                "update": self._update}

    @staticmethod
    def _public(it):
        return {k: v for k, v in it.items()
                if k not in ("info", "proposed", "job")}

    def _new_item(self, url, **kw):
        it = {"id": self._id(), "type": "song", "url": url, "status": "probing",
              "title": kw.pop("title", url), "artist": "", "album": "",
              "confidence": "", "source": "", "art": "", "progress": 0,
              "speed": "", "error": "", "dupe": "", "file": "", "group": None,
              "track_no": None, "info": {}, "proposed": {}, "art_custom": None,
              "message": ""}
        it.update(kw)
        self._items[it["id"]] = it
        return it

    # ── Adding links ────────────────────────────────────────────────────────
    def add_text(self, text):
        """Paste / drop / clipboard: add every supported link found."""
        links = find_links(text)
        if not links and (text or "").strip().startswith("http"):
            links = [text.strip()]
        for url in links:
            self._add_url(url)
        if not links:
            self._set_status("That doesn't look like a YouTube or SoundCloud "
                             "link.", "red")
        return len(links)

    def _add_url(self, url):
        with self._lock:
            it = self._new_item(url)
            self._order.append(it["id"])
        self._set_status("Checking link…", "amber")
        threading.Thread(target=self._probe, args=(it["id"],), daemon=True).start()

    def _probe(self, item_id):
        from skipman.downloader import probe
        it = self._items[item_id]
        try:
            info = probe(it["url"])
        except Exception as e:
            it.update(status="error", error=_short_err(e), title=it["url"])
            self._set_status("Couldn't read that link.", "red")
            return

        if info["kind"] == "playlist":
            self._make_album(item_id, info)
            return

        e = info["entry"]
        it["info"] = e
        it["title"] = e.get("title") or it["url"]
        it["status"] = "identifying"
        self._push()
        self._identify(it)
        dupe = self._library.check(it["title"], it["artist"])
        if dupe:
            it.update(status="dupe",
                      dupe=f"Already in {dupe['source']}: {dupe['label']}")
            self._set_status(f"Possible duplicate — {it['dupe']}", "amber")
            return
        self._enqueue(it)

    def _identify(self, it, album_artist=None):
        try:
            r = ident.identify(it["info"], self._store, LOOKUPS,
                               album_artist=album_artist)
        except Exception as e:  # never block a download over this
            r = {"title": it["info"].get("title", ""), "artist": "",
                 "album": "", "confidence": "check",
                 "source": f"Identify failed: {e}", "artwork_url": ""}
        it["proposed"] = r
        it["title"], it["artist"] = r["title"], r["artist"]
        if not it["group"]:
            it["album"] = r.get("album", "")
        it["confidence"], it["source"] = r["confidence"], r["source"]
        if r.get("artwork_url"):
            it["art"] = r["artwork_url"]
        elif not it["art"]:
            it["art"] = it["info"].get("thumbnail") or ""
        self._push()

    def _enqueue(self, it):
        job = self._Job(it["url"], title=it["title"])
        it["job"] = job
        it["status"] = "queued"
        self._job_item[job.id] = it["id"]
        self._worker.add(job)
        self._set_status("Downloading in the background — fix tags any time.",
                         "amber")

    # ── Albums (playlists) ──────────────────────────────────────────────────
    def _make_album(self, item_id, info):
        with self._lock:
            placeholder = self._items.pop(item_id, None)
            aid = self._id()
            idx = self._order.index(item_id) if item_id in self._order else len(self._order)
            if item_id in self._order:
                self._order.remove(item_id)
            # "Artist - Album Name" playlists: split into the two fields
            pt = ident.parse_title(info["title"])
            album_title = ident.compose_title(pt["title"], (), pt["tags"]) \
                if pt["artist_credit"] else info["title"]
            album = {"id": aid, "type": "album", "url": placeholder["url"],
                     "title": album_title, "artist": info.get("uploader", ""),
                     "title_artist": pt["artist_credit"],
                     "art": info.get("artwork", ""), "art_custom": None,
                     "status": "confirm", "tracks": [], "as": "album"}
            # Guess the album artist from the playlist's tracks, not the
            # uploader (who might be a repost page)
            for n, e in enumerate(info["entries"], 1):
                t = self._new_item(e["url"], title=e["title"], info=e,
                                   group=aid, track_no=n, status="waiting")
                d = self._library.check(e["title"], e.get("uploader", ""))
                if d:
                    t["dupe"] = f"Already in {d['source']}"
                album["tracks"].append(t["id"])
            self._albums[aid] = album
            self._order.insert(idx, aid)
        album["artist"] = self._guess_album_artist(info)
        self._set_status(f"Playlist found: {len(info['entries'])} tracks. "
                         "Check the order, then hit DOWNLOAD.", "amber")

    def _guess_album_artist(self, info):
        from collections import Counter
        named = ident.parse_title(info.get("title", ""))["artist_credit"]
        if named:
            return ident.join_names([self._store.preferred_name(n)
                                     for n in ident.split_names(named)])
        votes = Counter()
        for e in info["entries"][:25]:
            p = ident.parse_title(e.get("title", ""))
            for name in ident.split_names(p["artist_credit"])[:1]:
                votes[name] += 1
        if votes:
            name, n = votes.most_common(1)[0]
            if n >= max(2, len(info["entries"]) // 3):
                return self._store.preferred_name(name)
        up = info.get("uploader", "")
        kind = ident.classify_uploader({"uploader": up}, self._store)
        return ident.clean_uploader(up) if kind != "repost" else ""

    def album_update(self, aid, title=None, artist=None):
        a = self._albums.get(aid)
        if a:
            if title is not None:
                a["title"] = title
            if artist is not None:
                a["artist"] = artist
        return True

    def album_reorder(self, aid, ids):
        a = self._albums.get(aid)
        if a and a["status"] == "confirm" and set(ids) == set(a["tracks"]):
            a["tracks"] = list(ids)
            for n, tid in enumerate(a["tracks"], 1):
                self._items[tid]["track_no"] = n
            self._push()
        return True

    def album_set_kind(self, aid, kind):
        """'album' (tagged as one album) or 'songs' (loose singles)."""
        a = self._albums.get(aid)
        if a and a["status"] == "confirm":
            a["as"] = "songs" if kind == "songs" else "album"
            self._push()
        return True

    def album_drop_dupes(self, aid):
        a = self._albums.get(aid)
        if a:
            for tid in [t for t in a["tracks"] if self._items[t]["dupe"]]:
                self.remove(tid)
        return True

    def album_go(self, aid):
        a = self._albums.get(aid)
        if not a or a["status"] != "confirm":
            return False
        if a["as"] == "songs":
            # Break the playlist apart into separate single rows
            with self._lock:
                idx = self._order.index(aid)
                self._order.remove(aid)
                for off, tid in enumerate(a["tracks"]):
                    t = self._items[tid]
                    t.update(group=None, track_no=None)
                    self._order.insert(idx + off, tid)
                self._albums.pop(aid)
            for tid in a["tracks"]:
                self._enqueue(self._items[tid])
            return True
        a["status"] = "active"
        for tid in a["tracks"]:
            self._enqueue(self._items[tid])
        return True

    # ── Worker events ───────────────────────────────────────────────────────
    def _on_worker(self, event, **d):
        if event == "status":
            self._set_status(d.get("message", ""), "amber")
            return
        if event == "idle":
            self._push()
            return
        job = d.get("job")
        iid = self._job_item.get(job.id) if job else None
        it = self._items.get(iid)
        if not it:
            return
        if event == "started":
            it["status"] = "downloading"
        elif event == "progress":
            it["progress"] = round(d.get("pct", 0))
            it["speed"] = d.get("speed", "")
        elif event == "error":
            it.update(status="error", error=_short_err(d.get("message", "")))
            self._set_status(f"Download failed: {it['title']}", "red")
        elif event == "done":
            res = d["result"]
            it["file"] = res["file_path"]
            if not it["art"]:
                it["art"] = res.get("thumbnail_url", "")
            threading.Thread(target=self._after_download, args=(it, res),
                             daemon=True).start()
            return
        self._push()

    def _after_download(self, it, res):
        """Full info is available now: re-identify album tracks / weak rows."""
        full = res.get("info") or {}
        if it["group"]:
            a = self._albums.get(it["group"])
            it["info"] = {**it["info"], **{k: v for k, v in full.items() if v}}
            self._identify(it, album_artist=None)
            if a:
                it["album"] = a["title"]
                # The album artist only fills in when nothing better was found
                if not it["artist"] and a["artist"]:
                    it["artist"] = a["artist"]
                    it["confidence"] = "guess"
                    it["source"] = "Album artist"
        elif it["confidence"] != "matched":
            it["info"] = {**it["info"], **{k: v for k, v in full.items() if v}}
            self._identify(it)
        # Shazam-style fallback for anything still unsure
        key = self._store.get_setting("acoustid_key", "")
        if it["confidence"] != "matched" and fingerprint_available(key):
            fp = fingerprint_lookup(it["file"], key)
            if fp:
                probe_info = {"title": f"{fp['artist']} - {fp['title']}",
                              "duration": it["info"].get("duration"),
                              "extractor": "fingerprint"}
                r = ident.identify(probe_info, self._store, LOOKUPS)
                if r["artist"]:
                    it["proposed"] = {**r, "uploader_kind":
                                      it["proposed"].get("uploader_kind")}
                    it.update(title=r["title"], artist=r["artist"],
                              confidence="matched" if r["confidence"] == "matched"
                              else "guess", source="Identified by sound")
                    if r.get("artwork_url"):
                        it["art"] = r["artwork_url"]
        it["status"] = "ready"
        it["progress"] = 100
        self._set_status("Ready to review: " + it["title"], "green")

    # ── Review + send ───────────────────────────────────────────────────────
    def send(self, item_id, title, artist, album):
        it = self._items.get(item_id)
        if not it or it["status"] not in ("ready", "error-send"):
            return False
        title, artist, album = (title or "").strip(), (artist or "").strip(), \
            (album or "").strip()
        if not title:
            self._set_status("A song needs a title before it can be sent.", "red")
            return False
        it.update(status="sending", title=title, artist=artist, album=album)
        self._push()
        threading.Thread(target=self._send, args=(it,), daemon=True).start()
        return True

    def send_album(self, aid):
        """Send every ready track of an album with the tags shown."""
        a = self._albums.get(aid)
        if not a:
            return 0
        n = 0
        for tid in a["tracks"]:
            t = self._items[tid]
            if t["status"] == "ready":
                self.send(tid, t["title"], t["artist"], t["album"] or a["title"])
                n += 1
        return n

    def save_edit(self, item_id, title, artist, album):
        """Remember in-progress edits so a re-render never loses typing."""
        it = self._items.get(item_id)
        if it:
            it.update(title=title, artist=artist, album=album)
        return True

    def _send(self, it):
        from skipman.metadata import write_tags, rename_to_clean
        from skipman import applemusic
        a = self._albums.get(it["group"]) if it["group"] else None
        try:
            art = self._art_bytes(it, a)
            total = len(a["tracks"]) if a else None
            write_tags(it["file"], title=it["title"], artist=it["artist"],
                       album=it["album"],
                       album_artist=(a["artist"] or it["artist"]) if a else None,
                       track_no=it["track_no"] if a else None,
                       total_tracks=total, artwork_data=art,
                       clear_artwork=(art is None and it.get("art_custom") == "none"))
            it["file"] = rename_to_clean(it["file"], it["title"], it["artist"])
            msg = applemusic.send(it["file"])
            ident.learn(self._store, it["info"], it["proposed"], it["title"],
                        it["artist"])
            self._store.remember(title=it["title"], artist=it["artist"],
                                album=it["album"], key=it["url"], file=it["file"])
            self._library.add(it["title"], it["artist"])
            it["status"] = "sent"
            it["message"] = msg
            self._set_status(f'✓ "{it["title"]}" — {msg}', "green")
            if a and all(self._items[t]["status"] in ("sent", "skipped", "error")
                         for t in a["tracks"]):
                a["status"] = "done"
        except Exception as e:
            it["status"] = "error-send"
            it["error"] = _short_err(e)
            self._set_status(f"Couldn't send: {it['error']}", "red")
        self._push(force=True)

    def _art_bytes(self, it, album):
        src = (album or {}).get("art_custom") or it.get("art_custom")
        if src == "none":
            return None
        if src and os.path.exists(src):
            with open(src, "rb") as f:
                return _square(f.read())
        # Albums share one cover; singles use their own (catalog art first)
        url = (album or {}).get("art") or it.get("art")
        if not url:
            return None
        try:
            import requests
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return _square(r.content)
        except Exception:
            return None

    # ── Row actions ─────────────────────────────────────────────────────────
    def remove(self, item_id):
        with self._lock:
            if item_id in self._albums:
                a = self._albums.pop(item_id)
                for tid in a["tracks"]:
                    self._drop_item(tid)
                if item_id in self._order:
                    self._order.remove(item_id)
            elif item_id in self._items:
                it = self._items[item_id]
                if it["group"] and it["group"] in self._albums:
                    al = self._albums[it["group"]]
                    if item_id in al["tracks"]:
                        al["tracks"].remove(item_id)
                    for n, tid in enumerate(al["tracks"], 1):
                        self._items[tid]["track_no"] = n
                self._drop_item(item_id)
                if item_id in self._order:
                    self._order.remove(item_id)
        self._push()
        return True

    def _drop_item(self, iid):
        it = self._items.pop(iid, None)
        if it and it.get("job"):
            self._worker.cancel(it["job"].id)

    def get_anyway(self, item_id):
        it = self._items.get(item_id)
        if it and it["status"] == "dupe":
            it["dupe"] = ""
            self._enqueue(it)
        return True

    def retry(self, item_id):
        it = self._items.get(item_id)
        if it and it["status"] == "error":
            it.update(error="", progress=0)
            if it["info"]:
                self._enqueue(it)
            else:
                it["status"] = "probing"
                threading.Thread(target=self._probe, args=(item_id,),
                                 daemon=True).start()
        elif it and it["status"] == "error-send":
            it["status"] = "ready"
            self.send(item_id, it["title"], it["artist"], it["album"])
        return True

    def clear_finished(self):
        with self._lock:
            for rid in list(self._order):
                if rid in self._albums:
                    if self._albums[rid]["status"] == "done":
                        self.remove(rid)
                elif self._items.get(rid, {}).get("status") in ("sent", "skipped"):
                    self.remove(rid)
        self._push()
        return True

    # ── Artwork ─────────────────────────────────────────────────────────────
    def choose_art(self, item_id):
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN",
                       getattr(webview, "OPEN_DIALOG", 10))
        res = self._window.create_file_dialog(
            kind, file_types=("Images (*.jpg;*.jpeg;*.png;*.webp)",))
        if not res:
            return None
        path = res[0] if isinstance(res, (list, tuple)) else res
        self._apply_art(item_id, path)
        return True

    def set_art_none(self, item_id):
        self._apply_art(item_id, "none")
        return True

    def _apply_art(self, item_id, src):
        target = self._albums.get(item_id) or self._items.get(item_id)
        if not target:
            return
        it = self._items.get(item_id)
        if it and it["group"] in self._albums:
            target = self._albums[it["group"]]   # album art is shared
        target["art_custom"] = src
        if src == "none":
            target["art"] = ""
        else:
            with open(src, "rb") as f:
                target["art"] = "data:image/jpeg;base64," + \
                    base64.b64encode(_square(f.read(), 600)).decode()
        if target.get("type") == "album":
            for tid in target["tracks"]:
                self._items[tid]["art"] = target["art"]
        self._push()

    # ── Autofill ────────────────────────────────────────────────────────────
    def suggest_artists(self, prefix):
        return self._store.artist_suggestions(prefix)

    def suggest_albums(self, prefix, artist):
        return self._store.album_suggestions(prefix, artist)

    # ── Clipboard / inbox / settings ────────────────────────────────────────
    def check_clipboard(self):
        """On window focus: offer a copied music link once."""
        from skipman.clipboard import read_clipboard
        links = find_links(read_clipboard())
        known = {it["url"] for it in self._items.values()} | \
            {a["url"] for a in self._albums.values()}
        for l in links:
            if l not in self._offered_clip and l not in known:
                self._offered_clip.add(l)
                return l
        return None

    def watch_inbox(self):
        """Links dropped on the Dock icon arrive as files in the inbox."""
        def _loop():
            d = inbox_dir()
            while True:
                try:
                    for name in sorted(os.listdir(d)):
                        p = os.path.join(d, name)
                        try:
                            with open(p, "r", encoding="utf-8",
                                      errors="replace") as f:
                                text = f.read()
                            os.remove(p)
                        except OSError:
                            continue
                        if text.strip() == "__focus__":
                            self._bring_to_front()
                        elif text.strip():
                            self._bring_to_front()
                            self.add_text(text)
                except Exception:
                    pass
                time.sleep(0.8)
        threading.Thread(target=_loop, daemon=True).start()

    def _bring_to_front(self):
        try:
            self._window.restore()
            self._window.show()
        except Exception:
            pass
        if IS_MAC:
            try:
                from AppKit import NSApplication
                from PyObjCTools import AppHelper
                AppHelper.callAfter(lambda: NSApplication.sharedApplication()
                                    .activateIgnoringOtherApps_(True))
            except Exception:
                pass

    def get_settings(self):
        return {"save_dir": self._save_dir,
                "acoustid_key": self._store.get_setting("acoustid_key", ""),
                "fingerprint_ready": fingerprint_available(
                    self._store.get_setting("acoustid_key", "")),
                "version": __version__}

    def choose_save_dir(self):
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER",
                       getattr(webview, "FOLDER_DIALOG", 20))
        res = self._window.create_file_dialog(kind, directory=self._save_dir)
        if res:
            path = res[0] if isinstance(res, (list, tuple)) else res
            self._save_dir = path
            self._store.set_setting("save_dir", path)
        return self._save_dir

    def set_acoustid_key(self, key):
        self._store.set_setting("acoustid_key", (key or "").strip())
        return self.get_settings()

    def ready(self):
        """Called by the UI once it has loaded."""
        self._push(force=True)
        return self._snapshot()

    # ── Startup + updates ───────────────────────────────────────────────────
    def startup(self):
        def _go():
            from skipman.ffmpeg import ensure_ffmpeg
            try:
                ensure_ffmpeg(lambda m: self._set_status(m, "amber"))
            except Exception as e:
                self._set_status(str(e), "red")
                return
            self._set_status("Ready. Paste a link.", "green")
            self._library.scan_apple_music_async()
            from skipman import updater
            info = updater.check_and_update(
                lambda m: self._set_status(m, "amber"))
            if info:
                self._update = info
                self._set_status(info["message"], "green")
        threading.Thread(target=_go, daemon=True).start()

    def restart(self):
        from skipman import updater
        busy = any(it["status"] in ("downloading", "queued", "sending")
                   for it in self._items.values())
        if busy:
            self._set_status("Finish the current downloads first, then "
                             "restart.", "amber")
            return False
        updater.restart()
        return True


def _short_err(e):
    s = str(e).replace("ERROR: ", "")
    s = re.sub(r"\x1b\[[0-9;]*m", "", s)
    if "Sign in to confirm" in s:
        return "YouTube asked for a sign-in check. Try again in a bit."
    if "not available" in s.lower():
        return "That video isn't available."
    return s.strip().splitlines()[0][:200] if s.strip() else "Unknown error"


def _square(data, size=1200):
    """Center-crop artwork to a square (YouTube thumbnails are 16:9)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = im.size
        if abs(w - h) > 2:
            s = min(w, h)
            im = im.crop(((w - s) // 2, (h - s) // 2,
                          (w - s) // 2 + s, (h - s) // 2 + s))
        if im.size[0] > size:
            im = im.resize((size, size))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=92)
        return out.getvalue()
    except Exception:
        return data
