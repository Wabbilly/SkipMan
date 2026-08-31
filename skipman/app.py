# ── SkipMan — Main Application Window ───────────────────────────────────────

import tkinter as tk
import os
import sys
import subprocess
import threading
import queue as _uiqueue

from skipman import theme, __version__


# ── Dependencies that auto-install on first run ────────────────────────────
REQUIRED_PACKAGES = {
    "yt_dlp": "yt-dlp",
    "mutagen": "mutagen",
    "PIL": "Pillow",
    "requests": "requests",
}


def _check_and_install_deps(status_callback=None):
    """Check for required packages and pip-install any that are missing."""
    missing = []
    for module_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        return

    if status_callback:
        status_callback(f"Installing: {', '.join(missing)}...")

    for pkg in missing:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError:
            if status_callback:
                status_callback(f"Failed to install {pkg}. Run: pip install {pkg}")

    if status_callback:
        status_callback("Dependencies installed.")


class SkipManApp(tk.Tk):
    """Main window. Owns the store, library index, download worker + screens."""

    def __init__(self):
        super().__init__()

        self.title(f"SkipMan v{__version__}")
        self.geometry("700x640")
        self.minsize(640, 560)
        self.configure(bg=theme.BG_DARK)

        try:
            self.iconbitmap(default="")
        except tk.TclError:
            pass

        # ── Persistent state ────────────────────────────────────────────────
        from skipman.store import Store
        from skipman.library import LibraryIndex

        self.store = Store()
        self.library = LibraryIndex(self.store)

        default_dir = os.path.join(os.path.expanduser("~"), "Music", "SkipMan")
        self.save_dir = self.store.get_setting("save_dir", default_dir)

        # ── Runtime state ───────────────────────────────────────────────────
        self.ready = []          # downloaded results awaiting edit
        self.groups = {}         # album group id -> group dict
        self.current_song = None
        self.editing = False
        self._group_seq = 0

        # ── Thread-safe UI marshalling ──────────────────────────────────────
        # Background threads never touch tk directly: they app.post()
        # callables onto this queue, drained on the UI thread.
        self._uiq = _uiqueue.Queue()
        self.after(40, self._poll_ui)

        # ── Download worker (runs while you edit) ───────────────────────────
        from skipman.worker import DownloadWorker
        self.worker = DownloadWorker(
            emit=self._emit_from_worker, get_save_dir=lambda: self.save_dir)

        # ── Screens ─────────────────────────────────────────────────────────
        self.container = tk.Frame(self, bg=theme.BG_DARK)
        self.container.pack(fill="both", expand=True)

        from skipman.download_screen import DownloadScreen
        from skipman.edit_screen import EditScreen
        from skipman.album_screen import AlbumScreen

        self.download_screen = DownloadScreen(self.container, self)
        self.edit_screen = EditScreen(self.container, self)
        self.album_screen = AlbumScreen(self.container, self)

        self.show_download_screen()
        self._startup_checks()

    # ── Cross-thread UI marshalling ─────────────────────────────────────────
    def post(self, fn, *args, **kwargs):
        """Safe to call from ANY thread: run fn(*args) on the UI thread."""
        self._uiq.put((fn, args, kwargs))

    def _poll_ui(self):
        try:
            while True:
                fn, args, kwargs = self._uiq.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception:
                    pass
        except _uiqueue.Empty:
            pass
        self.after(40, self._poll_ui)

    # ── Startup ─────────────────────────────────────────────────────────────
    def _startup_checks(self):
        """Dependency + FFmpeg checks and Apple Music scan, off-thread."""
        def _check():
            _check_and_install_deps(
                lambda msg: self.post(
                    self.download_screen._set_status, msg, theme.AMBER))

            from skipman.ffmpeg_setup import ensure_ffmpeg
            try:
                ensure_ffmpeg(
                    lambda msg: self.post(
                        self.download_screen._set_status, msg, theme.AMBER))
            except RuntimeError as e:
                self.post(
                    self.download_screen._set_status, str(e), theme.ERROR)
                return

            self.post(
                self.download_screen._set_status, "Ready.", theme.GREEN)

            # Index the Apple Music library for duplicate detection
            self.library.scan_apple_music_async(
                on_done=lambda n: self.post(
                    self.download_screen._log,
                    f"[LIB] Indexed {n} Apple Music tracks for dupe check."))

        threading.Thread(target=_check, daemon=True).start()

    # ── Worker events (marshalled onto the UI thread) ───────────────────────
    def _emit_from_worker(self, event, **data):
        self.post(self._on_worker_event, event, data)

    def _on_worker_event(self, event, data):
        ds = self.download_screen
        if event == "status":
            ds._set_status(data.get("message", ""), theme.AMBER)
        elif event == "started":
            ds.on_job_started(data["job"])
        elif event == "progress":
            ds.on_job_progress(data["job"], data["pct"], data.get("speed", ""))
        elif event == "done":
            self._on_download_done(data["job"], data["result"])
        elif event == "error":
            ds.on_job_error(data["job"], data["message"])
        elif event == "idle":
            ds.on_queue_idle()

    def _on_download_done(self, job, result):
        ds = self.download_screen
        ds.on_job_done(job, result)

        if job.group is not None and job.group in self.groups:
            self._on_album_track_done(job, result)
            return

        # Single song → goes to the edit pool
        self.ready.append(result)
        self._maybe_edit_next()
        ds.refresh_queue_display()

    # ── Album groups ────────────────────────────────────────────────────────
    def new_group(self, title, artist, total, auto_upload, review_each):
        self._group_seq += 1
        gid = self._group_seq
        self.groups[gid] = {
            "title": title, "artist": artist, "total": total,
            "auto_upload": auto_upload, "review": review_each,
            "done": 0, "errors": 0,
        }
        return gid

    def _on_album_track_done(self, job, result):
        """Auto-tag an album track as arranged; upload or queue for review."""
        g = self.groups[job.group]
        ds = self.download_screen

        from skipman.metadata import write_tags, rename_to_clean

        # Prefer the real extracted title when the arrange screen only had
        # a URL-derived guess (flat SoundCloud playlists omit titles).
        if job.title_guess and result.get("title"):
            title = result["title"]
        else:
            title = job.title or result.get("title", "")
        artist = job.artist or result.get("artist", "") or g["artist"]

        try:
            fp = result.get("file_path", "")
            art = self._fetch_artwork(result.get("thumbnail_url", ""))
            write_tags(
                fp, title=title, artist=artist, album=g["title"],
                album_artist=g["artist"] or artist,
                track_no=job.track_no, total_tracks=g["total"],
                artwork_data=art,
            )
            new_fp = rename_to_clean(fp, title, artist)
            result["file_path"] = new_fp
            result["title"], result["artist"] = title, artist
            result["album"] = g["title"]

            self.store.remember(title=title, artist=artist, album=g["title"],
                                key=job.url, file=new_fp)
            self.library.add(title, artist)

            g["done"] += 1
            ds._log(f'[ALBUM {g["done"]}/{g["total"]}] "{title}" tagged.')

            if g["review"]:
                self.ready.append(result)
                self._maybe_edit_next()
            elif g["auto_upload"]:
                self._upload_quiet(new_fp, title)
        except Exception as e:
            g["errors"] += 1
            ds._log(f"[ERROR] Album track failed: {e}")

        if g["done"] + g["errors"] >= g["total"]:
            msg = f'Album "{g["title"]}" complete — {g["done"]}/{g["total"]} tracks.'
            ds._set_status(msg, theme.SUCCESS if not g["errors"] else theme.AMBER)
            ds._log(f"[OK] {msg}")
        ds.refresh_queue_display()

    def _fetch_artwork(self, url):
        """Fetch thumbnail bytes for embedding (album batch mode)."""
        if not url:
            return None
        try:
            import requests
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    def _upload_quiet(self, file_path, title):
        """Background Apple Music upload for auto-upload album tracks."""
        def _up():
            try:
                from skipman.itunes import add_to_itunes
                _ok, msg = add_to_itunes(file_path)
                self.post(self.download_screen._log, f"[AM] {msg}")
            except Exception as e:
                self.post(self.download_screen._log,
                          f"[AM ERROR] {title}: {e}")
        threading.Thread(target=_up, daemon=True).start()

    # ── Edit pool ───────────────────────────────────────────────────────────
    def _maybe_edit_next(self, force=False):
        """Open the edit screen for the next ready song, if not busy editing."""
        if self.editing or not self.ready:
            self.download_screen.refresh_queue_display()
            return
        # Don't yank the screen away while the user is typing another URL
        if not force and not self.download_screen.can_autojump():
            self.download_screen.refresh_queue_display()
            return
        song = self.ready.pop(0)
        self.show_edit_screen(song)

    # ── Screen Switching ────────────────────────────────────────────────────
    def show_download_screen(self):
        self.editing = False
        self.edit_screen.pack_forget()
        self.album_screen.pack_forget()
        self.download_screen.pack(fill="both", expand=True)
        self.download_screen.refresh_queue_display()

    def show_edit_screen(self, song_info):
        self.editing = True
        self.current_song = song_info
        self.download_screen.pack_forget()
        self.album_screen.pack_forget()
        self.edit_screen.load_song(song_info)
        self.edit_screen.pack(fill="both", expand=True)

    def show_album_screen(self, playlist_info):
        self.editing = False
        self.download_screen.pack_forget()
        self.edit_screen.pack_forget()
        self.album_screen.load_playlist(playlist_info)
        self.album_screen.pack(fill="both", expand=True)

    def on_edit_done(self):
        """User finished with a song: pull the next ready one, or go back."""
        self.editing = False
        if self.ready:
            self._maybe_edit_next()
            return
        self.show_download_screen()
        active, pending = self.worker.snapshot()
        if active or pending:
            self.download_screen._set_status(
                "Downloading in background… next song opens when ready.",
                theme.AMBER)
        else:
            self.download_screen._set_status(
                "All done! Add more URLs to continue.", theme.GREEN)

    # ── Settings passthrough ────────────────────────────────────────────────
    def set_save_dir(self, path):
        self.save_dir = path
        self.store.set_setting("save_dir", path)
