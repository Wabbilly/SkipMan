import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skipman.api import find_links
from skipman.downloader import social_title, is_social, site_name, id_info


def test_links_from_social_sites():
    text = ("https://www.reddit.com/r/DaveChappelle/comments/18633xr/x/ "
            "https://x.com/a/status/1 https://twitter.com/a/status/2 "
            "https://vm.tiktok.com/ZM1/ https://www.instagram.com/reel/abc/ "
            "https://v.redd.it/abc https://netflix.com/title/1")
    links = find_links(text)
    assert len(links) == 6
    assert not any("netflix" in l for l in links)


def test_is_social_and_names():
    assert is_social("https://x.com/a/status/1")
    assert not is_social("https://www.netflix.com/x")
    assert not is_social("https://www.youtube.com/watch?v=1")
    assert site_name("https://old.reddit.com/r/a") == "Reddit"
    assert site_name("https://x.com/a") == "X"


def test_x_title_drops_poster_name():
    info = {"title": "Max Olson - Storm surge footage https://t.co/abc",
            "uploader": "Max Olson", "extractor_key": "Twitter"}
    assert social_title(info) == "Storm surge footage"


def test_instagram_and_tiktok_titles_use_caption():
    assert social_title({"title": "Video by someone", "extractor": "Instagram",
                         "description": "New song snippet\n#music"}) \
        == "New song snippet"
    assert social_title({"title": "TikTok video #123", "extractor": "TikTok",
                         "uploader": "dj", "description": ""}) == "dj clip"


def test_reddit_title_kept_and_youtube_untouched():
    t = "Dave Chappelle deleted SNL monologue Nov 12th 2022"
    assert id_info({"title": t, "extractor_key": "Reddit"})["title"] == t
    yt = "Drake - Hotline Bling (Official Video)"
    assert id_info({"title": yt, "extractor_key": "Youtube",
                    "uploader": "Drake"})["title"] == yt


def test_login_cookies_saved_and_detected(tmp_path, monkeypatch):
    from http.cookies import SimpleCookie
    from skipman import logins
    monkeypatch.setattr(logins, "cookie_file", lambda: str(tmp_path / "l.txt"))

    def ck(name, value, domain, expires="Wed, 01 Dec 2027 00:00:00 GMT"):
        c = SimpleCookie()
        c[name] = value
        c[name]["domain"], c[name]["path"] = domain, "/"
        c[name]["expires"], c[name]["secure"] = expires, True
        return c

    assert not logins.is_logged_in("reddit")
    got = [ck("reddit_session", "abc", ".reddit.com"), ck("loid", "x", "www.reddit.com", ""),
           ck("other", "y", ".google.com")]
    lines = logins.cookie_lines(got, "reddit")
    assert len(lines) == 2 and logins.has_session(lines, "reddit")
    logins.save("reddit", lines)
    logins.save("x", logins.cookie_lines([ck("auth_token", "t", ".x.com")], "x"))
    assert logins.is_logged_in("reddit") and logins.is_logged_in("x")
    assert not logins.is_logged_in("instagram")
    logins.logout("reddit")
    assert not logins.is_logged_in("reddit") and logins.is_logged_in("x")
    assert logins.site_for_url("https://old.reddit.com/r/a") == "reddit"
    assert logins.site_for_url("https://x.com/a/status/1") == "x"
    assert logins.site_for_url("https://netflix.com/") is None
