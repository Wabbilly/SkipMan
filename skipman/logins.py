# ── Site logins (Reddit, Instagram, X) ──────────────────────────────────────
# Some sites only hand over videos to signed-in people (Reddit isn't here:
# it blocks apps even with a login, see downloader.REDDIT_MSG). SkipMan opens the
# site's own login page in a small window; once you're signed in it keeps
# that login (cookies) in its own data folder and uses it for downloads.
# No browser access or Full Disk Access needed, and it survives updates.

import os
import shutil
import tempfile
import threading
import time

from skipman.paths import data_dir

SITES = {
    "instagram": {"name": "Instagram",
                  "url": "https://www.instagram.com/accounts/login/",
                  "domains": ("instagram.com",), "session": "sessionid"},
    "x": {"name": "X", "url": "https://x.com/i/flow/login",
          "domains": ("x.com", "twitter.com"), "session": "auth_token"},
}
_lock = threading.Lock()


def cookie_file():
    return os.path.join(data_dir(), "logins.txt")


def site_for_url(url):
    u = (url or "").lower()
    if "reddit.com" in u or "redd.it" in u:
        return "reddit"
    if "instagram.com" in u:
        return "instagram"
    if "twitter.com" in u or "://x.com" in u or ".x.com" in u:
        return "x"
    return None


def _on_domain(domain, site):
    d = (domain or "").lstrip(".").lower()
    return any(d == s or d.endswith("." + s) for s in SITES[site]["domains"])


def _read_lines():
    try:
        with open(cookie_file(), encoding="utf-8") as f:
            return [l.rstrip("\n") for l in f if l.strip() and not l.startswith("#")]
    except OSError:
        return []


def _write_lines(lines):
    p = cookie_file()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n# SkipMan site logins\n")
        for l in lines:
            f.write(l + "\n")
    os.replace(tmp, p)


def is_logged_in(site):
    now = time.time()
    for l in _read_lines():
        parts = l.split("\t")
        if len(parts) == 7 and _on_domain(parts[0], site) and \
                parts[5] == SITES[site]["session"]:
            exp = int(parts[4] or 0)
            if exp == 0 or exp > now:
                return True
    return False


def status():
    return {k: {"name": v["name"], "logged_in": is_logged_in(k)}
            for k, v in SITES.items()}


def _expiry(value):
    """Cookie expiry (NSDate on Mac, date text on Windows) → unix time."""
    if value is None or value == "":
        return int(time.time()) + 30 * 86400      # session cookie: keep a month
    if hasattr(value, "timeIntervalSince1970"):
        return int(value.timeIntervalSince1970())
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    from datetime import datetime
    from email.utils import parsedate_to_datetime
    for fn in (lambda x: parsedate_to_datetime(x),
               lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S %z")):
        try:
            return int(fn(s).timestamp())
        except Exception:
            pass
    return int(time.time()) + 30 * 86400


def cookie_lines(cookies, site):
    """pywebview cookies (SimpleCookie objects) → Netscape lines for a site."""
    out = []
    for c in cookies or []:
        for name, m in c.items():
            domain = m["domain"] or ""
            if not _on_domain(domain, site):
                continue
            dom = domain if domain.startswith(".") else "." + domain
            secure = "TRUE" if m["secure"] else "FALSE"
            out.append("\t".join([dom, "TRUE", m["path"] or "/", secure,
                                  str(_expiry(m["expires"])), name, m.value]))
    return out


def save(site, lines):
    with _lock:
        keep = [l for l in _read_lines()
                if not _on_domain(l.split("\t")[0], site)]
        _write_lines(keep + lines)


def logout(site):
    save(site, [])


def has_session(lines, site):
    return any(l.split("\t")[5] == SITES[site]["session"] for l in lines)


def temp_copy():
    """A private copy of the login file for one download (yt-dlp writes back
    to its cookie file, and several downloads can run at once)."""
    if not os.path.exists(cookie_file()):
        return None
    fd, p = tempfile.mkstemp(prefix="skipman-cookies-", suffix=".txt")
    os.close(fd)
    with _lock:
        shutil.copyfile(cookie_file(), p)
    return p
