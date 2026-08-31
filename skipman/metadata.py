# ── ID3 Metadata Handler (mutagen) ──────────────────────────────────────────

import os
from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, TIT2, TPE1, TPE2, TALB, TRCK, APIC, ID3NoHeaderError)


def read_tags(filepath):
    """Read ID3 tags from an MP3 file."""
    try:
        audio = MP3(filepath, ID3=ID3)
        tags = audio.tags
        if tags is None:
            return {"title": "", "artist": "", "album": "", "artwork": None}
        return {
            "title": str(tags.get("TIT2", "")),
            "artist": str(tags.get("TPE1", "")),
            "album": str(tags.get("TALB", "")),
            "artwork": tags.getall("APIC")[0] if tags.getall("APIC") else None,
        }
    except Exception:
        return {"title": "", "artist": "", "album": "", "artwork": None}


def write_tags(filepath, title=None, artist=None, album=None,
               album_artist=None, track_no=None, total_tracks=None,
               artwork_path=None, artwork_data=None, clear_artwork=False):
    """
    Write ID3 tags to an MP3 file.

    Args:
        filepath: Path to the MP3 file
        title / artist / album: basic tags (TIT2 / TPE1 / TALB)
        album_artist: TPE2 — keeps album tracks grouped in Apple Music
        track_no / total_tracks: TRCK ("3/12") for album ordering
        artwork_path: image file to embed as cover art
        artwork_data: raw image bytes (alternative to artwork_path)
        clear_artwork: if True, remove all artwork
    """
    try:
        audio = MP3(filepath, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
    except ID3NoHeaderError:
        audio = MP3(filepath)
        audio.add_tags()

    tags = audio.tags

    if title is not None:
        tags["TIT2"] = TIT2(encoding=3, text=title)
    if artist is not None:
        tags["TPE1"] = TPE1(encoding=3, text=artist)
    if album is not None:
        tags["TALB"] = TALB(encoding=3, text=album)
    if album_artist:
        tags["TPE2"] = TPE2(encoding=3, text=album_artist)
    if track_no:
        trck = f"{track_no}/{total_tracks}" if total_tracks else str(track_no)
        tags["TRCK"] = TRCK(encoding=3, text=trck)

    if clear_artwork:
        tags.delall("APIC")
    elif artwork_path and os.path.exists(artwork_path):
        ext = os.path.splitext(artwork_path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        with open(artwork_path, "rb") as f:
            data = f.read()
        tags.delall("APIC")
        tags.add(APIC(
            encoding=3, mime=mime, type=3, desc="Cover", data=data,
        ))
    elif artwork_data:
        tags.delall("APIC")
        tags.add(APIC(
            encoding=3, mime="image/jpeg", type=3, desc="Cover",
            data=artwork_data,
        ))

    audio.save()


def rename_to_clean(filepath, title, artist=""):
    """
    Rename '<Title> [videoid].mp3' to a clean '<Artist> - <Title>.mp3'
    (or '<Title>.mp3'). Returns the new path (or original on failure).
    """
    try:
        d = os.path.dirname(filepath)
        base = f"{artist} - {title}" if artist else (title or "")
        base = base.strip() or os.path.splitext(os.path.basename(filepath))[0]
        # Strip characters Windows filenames can't hold
        for ch in '<>:"/\\|?*':
            base = base.replace(ch, "")
        base = base.strip(". ") or "track"
        new_path = os.path.join(d, base + ".mp3")
        if os.path.abspath(new_path) == os.path.abspath(filepath):
            return filepath
        n = 2
        while os.path.exists(new_path):
            new_path = os.path.join(d, f"{base} ({n}).mp3")
            n += 1
        os.rename(filepath, new_path)
        return new_path
    except OSError:
        return filepath
