# ── Background Download Worker ──────────────────────────────────────────────
# Downloads the queue continuously on its own thread, so songs keep coming in
# while you're editing tags. The UI is notified through marshalled events.

import threading
import queue as _queue
import itertools

_ids = itertools.count(1)


class Job:
    """One download job (a single song, possibly part of an album group)."""

    __slots__ = ("id", "url", "title", "artist", "group", "track_no",
                 "album", "title_guess")

    def __init__(self, url, title="", artist="", group=None,
                 track_no=None, album="", title_guess=False):
        self.id = next(_ids)
        self.url = url
        self.title = title or url
        self.artist = artist
        self.group = group      # album group id, or None for singles
        self.track_no = track_no
        self.album = album
        self.title_guess = title_guess  # True if title was derived from URL


class DownloadWorker:
    """
    Owns a job queue + one download thread.

    emit(event: str, **data) is called FROM THE WORKER THREAD — the app
    wraps it in tk's .after() to get back on the UI thread.

    Events: started(job), progress(job, pct, speed), done(job, result),
            error(job, message), idle()
    """

    def __init__(self, emit, get_save_dir):
        self._emit = emit
        self._get_save_dir = get_save_dir
        self._jobs = _queue.Queue()
        self._cancelled = set()
        self._lock = threading.Lock()
        self.pending = []       # jobs waiting (mirrors queue, for display)
        self.active = None      # job currently downloading
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ── Public API (UI thread) ──────────────────────────────────────────────
    def add(self, job):
        with self._lock:
            self.pending.append(job)
        self._jobs.put(job)

    def cancel(self, job_id):
        """Cancel a job that hasn't started yet."""
        with self._lock:
            self._cancelled.add(job_id)
            self.pending = [j for j in self.pending if j.id != job_id]

    def cancel_all(self):
        with self._lock:
            for j in self.pending:
                self._cancelled.add(j.id)
            self.pending = []

    def snapshot(self):
        """(active_job, [pending jobs]) for queue display."""
        with self._lock:
            return self.active, list(self.pending)

    # ── Worker thread ───────────────────────────────────────────────────────
    def _run(self):
        from skipman.downloader import download_song
        from skipman.ffmpeg import ensure_ffmpeg

        while True:
            job = self._jobs.get()

            with self._lock:
                if job.id in self._cancelled:
                    self._cancelled.discard(job.id)
                    continue
                self.pending = [j for j in self.pending if j.id != job.id]
                self.active = job

            self._emit("started", job=job)

            try:
                ffmpeg_loc = ensure_ffmpeg(
                    lambda msg: self._emit("status", message=msg))

                def hook(d):
                    if d.get("status") == "downloading":
                        pct_str = d.get("_percent_str", "0%")
                        pct_str = pct_str.strip().replace("%", "")
                        try:
                            pct = float(pct_str)
                        except ValueError:
                            return
                        self._emit("progress", job=job, pct=pct,
                                   speed=d.get("_speed_str", "").strip())
                    elif d.get("status") == "finished":
                        self._emit("progress", job=job, pct=100,
                                   speed="converting")

                result = download_song(
                    job.url, self._get_save_dir(),
                    progress_callback=hook, ffmpeg_location=ffmpeg_loc)

                result["job_id"] = job.id

                self._emit("done", job=job, result=result)
            except Exception as e:
                self._emit("error", job=job, message=str(e))
            finally:
                with self._lock:
                    self.active = None
                if self._jobs.empty():
                    self._emit("idle")
