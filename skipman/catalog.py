# ── Outside lookups: Apple's catalog + AcoustID audio fingerprint ───────────

import json
import os
import shutil
import subprocess
import threading
import time

_cache = {}
_lock = threading.Lock()
_last_call = [0.0]


def apple_search(term, limit=15):
    """Search Apple's public music catalog. Cached, gently rate-limited."""
    term = " ".join((term or "").split())
    if not term:
        return []
    with _lock:
        if term in _cache:
            return _cache[term]
        # Apple allows ~20 calls/min; space calls out a little
        wait = 0.35 - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
    import requests
    try:
        r = requests.get(
            "https://itunes.apple.com/search",
            params={"term": term, "entity": "song", "limit": limit,
                    "country": "US"},
            timeout=8)
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception:
        return []
    with _lock:
        _cache[term] = results
    return results


def deezer_search(term, limit=15):
    """Deezer's free catalog — backup for songs Apple's store doesn't list.
    Results are reshaped to look like Apple's so matching code is shared."""
    term = " ".join((term or "").split())
    if not term:
        return []
    key = "dz:" + term
    with _lock:
        if key in _cache:
            return _cache[key]
    import requests
    try:
        r = requests.get("https://api.deezer.com/search",
                         params={"q": term, "limit": limit}, timeout=8)
        data = r.json().get("data", [])
    except Exception:
        return []
    out = []
    for d in data:
        out.append({
            "artistName": (d.get("artist") or {}).get("name", ""),
            "trackName": d.get("title", ""),
            "collectionName": (d.get("album") or {}).get("title", ""),
            "trackTimeMillis": int(d.get("duration") or 0) * 1000,
            "trackExplicitness": "explicit" if d.get("explicit_lyrics")
            else "notExplicit",
            "artwork": (d.get("album") or {}).get("cover_xl", ""),
            "_src": "Deezer catalog",
        })
    with _lock:
        _cache[key] = out
    return out


def _tag_apple(term):
    res = apple_search(term)
    for r in res:
        r.setdefault("_src", "Apple Music catalog")
        if not r.get("artwork") and r.get("artworkUrl100"):
            r["artwork"] = r["artworkUrl100"].replace("100x100bb", "1200x1200bb")
    return res


# Catalogs tried in order: Apple first, Deezer as backup
LOOKUPS = [_tag_apple, deezer_search]


# ── AcoustID (optional "Shazam" fallback) ──────────────────────────────────

def _fpcalc():
    for p in (shutil.which("fpcalc"), "/opt/homebrew/bin/fpcalc",
              "/usr/local/bin/fpcalc"):
        if p and os.path.exists(p):
            return p
    return None


def fingerprint_available(api_key):
    return bool(api_key) and bool(_fpcalc())


def fingerprint_lookup(path, api_key):
    """
    Identify a song by its sound. Returns {'title', 'artist'} or None.
    Needs a free AcoustID key and the fpcalc tool (brew install chromaprint).
    """
    exe = _fpcalc()
    if not api_key or not exe:
        return None
    try:
        out = subprocess.run([exe, "-json", path], capture_output=True,
                             text=True, timeout=60)
        fp = json.loads(out.stdout)
        import requests
        r = requests.post("https://api.acoustid.org/v2/lookup", data={
            "client": api_key, "meta": "recordings",
            "duration": int(fp["duration"]), "fingerprint": fp["fingerprint"],
        }, timeout=15)
        best = None
        for res in r.json().get("results", []):
            if res.get("score", 0) < 0.8:
                continue
            for rec in res.get("recordings", []) or []:
                if rec.get("title") and rec.get("artists"):
                    names = [a["name"] for a in rec["artists"]]
                    best = {"title": rec["title"], "artist": names[0],
                            "artists": names}
                    break
            if best:
                break
        return best
    except Exception:
        return None
