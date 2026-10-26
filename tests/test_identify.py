import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from skipman.identify import (parse_title, identify, split_names, learn,
                              clean_uploader, compose_title)
from skipman.store import Store


@pytest.fixture
def store():
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "store.json"))


# ── Title parsing ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,artist,title,feats,tags", [
    ("Drake - Hotline Bling (Official Video)", "Drake", "Hotline Bling", [], []),
    ("🔥 Drake ft. Future - Life Is Good [HD] 🔥", "Drake", "Life Is Good", ["Future"], []),
    ("Kendrick Lamar - Not Like Us (Lyrics)", "Kendrick Lamar", "Not Like Us", [], []),
    ("Hotline Bling (Kaytranada Remix)", "", "Hotline Bling", [], ["Kaytranada Remix"]),
    ("Drake - Hotline Bling (BVRNOUT Remix)", "Drake", "Hotline Bling", [], ["BVRNOUT Remix"]),
    ("SZA - Kill Bill (slowed + reverb)", "SZA", "Kill Bill", [], ["Slowed + Reverb"]),
    ("SZA - Kill Bill slowed reverb", "SZA", "Kill Bill", [], ["Slowed + Reverb"]),
    ("Kill Bill (Sped Up) - SZA", "Kill Bill", "SZA", [], ["Sped Up"]),
    ("Travis Scott - goosebumps (prod. by Cardo)", "Travis Scott", "goosebumps", [], ["prod. by Cardo"]),
    ("Oasis - Wonderwall (Remastered)", "Oasis", "Wonderwall", [], ["Remastered"]),
    ("Adele - Hello (Live at the BBC)", "Adele", "Hello", [], ["Live at the BBC"]),
    ("Juice WRLD - Lucid Dreams (Dir. by @_ColeBennett_)", "Juice WRLD", "Lucid Dreams", [], []),
    ('Frank Ocean "Nights"', "Frank Ocean", "Nights", [], []),
    ("Nights by Frank Ocean", "Frank Ocean", "Nights", [], []),
    ("Drake x Future - Jumpman | Official Audio", "Drake x Future", "Jumpman", [], []),
    ("Future – Life Is Good (feat. Drake) #rap #drake", "Future", "Life Is Good", ["Drake"], []),
    ("Not Like Us ft. Kendrick Lamar", "", "Not Like Us", ["Kendrick Lamar"], []),
    ("Lil Nas X - Old Town Road (Official Movie) [Explicit]", "Lil Nas X", "Old Town Road (Official Movie)", [], []),
    ("Tyler, The Creator - EARFQUAKE", "Tyler, The Creator", "EARFQUAKE", [], []),
    ("Kanye West - Stronger (Acoustic)", "Kanye West", "Stronger", [], ["Acoustic"]),
    ("Metro Boomin, The Weeknd, 21 Savage - Creepin' (Visualizer)", "Metro Boomin, The Weeknd, 21 Savage", "Creepin'", [], []),
])
def test_parse(raw, artist, title, feats, tags):
    p = parse_title(raw)
    assert p["artist_credit"] == artist
    assert p["title"] == title
    assert p["feats"] == feats
    assert p["tags"] == tags


def test_split_names_keeps_known_acts():
    assert split_names("Simon & Garfunkel") == ["Simon & Garfunkel"]
    assert split_names("Tyler, The Creator & Kali Uchis") == ["Tyler, The Creator", "Kali Uchis"]
    assert split_names("Drake x Future") == ["Drake", "Future"]
    assert split_names("Lil Nas X") == ["Lil Nas X"]


def test_clean_uploader():
    assert clean_uploader("KendrickLamarVEVO") == "Kendrick Lamar"
    assert clean_uploader("Drake - Topic") == "Drake"


def test_compose():
    assert compose_title("Life Is Good", ["Drake"]) == "Life Is Good (feat. Drake)"
    assert compose_title("Kill Bill", [], ["Slowed + Reverb"]) == "Kill Bill (Slowed + Reverb)"


# ── Full identification (offline: no catalog) ──────────────────────────────

def info(title, uploader="", extractor="youtube", **kw):
    d = {"title": title, "uploader": uploader, "extractor": extractor,
         "id": kw.pop("id", "x1"), "duration": kw.pop("duration", None)}
    d.update(kw)
    return d


def test_repost_never_becomes_artist(store):
    r = identify(info("Hotline Bling", "RapVibesDaily"), store)
    assert r["artist"] == ""
    assert r["confidence"] == "check"


def test_official_uploader_used(store):
    r = identify(info("Hotline Bling", "DrakeVEVO"), store)
    assert r["artist"] == "Drake"


def test_title_artist_beats_uploader(store):
    r = identify(info("Drake - Hotline Bling (Official Audio)", "Lyrical Lemonade"), store)
    assert (r["artist"], r["title"]) == ("Drake", "Hotline Bling")
    assert r["uploader_kind"] == "repost"


def test_remix_keeps_original_artist(store):
    r = identify(info("Drake - Hotline Bling (BVRNOUT Remix)", "BVRNOUT", "soundcloud"), store)
    assert r["artist"] == "Drake"
    assert r["title"] == "Hotline Bling (BVRNOUT Remix)"


def test_remixer_upload_without_artist_is_flagged(store):
    r = identify(info("Hotline Bling (BVRNOUT Remix)", "BVRNOUT", "soundcloud"), store)
    assert r["artist"] == ""
    assert r["confidence"] == "check"


def test_two_leads(store):
    r = identify(info("Drake & Future - Jumpman"), store)
    assert r["artist"] == "Drake & Future"


def test_feat_kept_for_guest(store):
    r = identify(info("Future - Life Is Good ft. Drake"), store)
    assert (r["artist"], r["title"]) == ("Future", "Life Is Good (feat. Drake)")


def test_repost_feat_is_really_artist(store):
    r = identify(info("Not Like Us ft. Kendrick Lamar", "RapNation"), store)
    assert r["artist"] == "Kendrick Lamar"
    assert r["title"] == "Not Like Us"
    assert r["confidence"] == "check"


def test_youtube_music_fields(store):
    r = identify(info("Life Is Good (feat. Drake)", "Future - Topic",
                      artists=["Future", "Drake"], track="Life Is Good (feat. Drake)"), store)
    assert (r["artist"], r["title"]) == ("Future", "Life Is Good (feat. Drake)")


def test_preferred_spelling(store):
    r = identify(info("Ye - Stronger"), store)
    assert r["artist"] == "Kanye West"


def test_learning_correction_and_accounts(store):
    i = info("Hotline Bling", "RapVibesDaily", id="abc")
    first = identify(i, store)
    learn(store, i, first, "Hotline Bling", "Drake")
    again = identify(i, store)
    assert again["artist"] == "Drake" and again["confidence"] == "matched"
    assert store.account_kind("RapVibesDaily") == "repost"


def test_learning_official_account(store):
    i = info("Some Song", "Bob Smith", "soundcloud", id="q")
    r = identify(i, store)
    learn(store, i, r, "Some Song", "Bob Smith")
    assert store.account_kind("Bob Smith") == "official"


def test_learning_alias(store):
    i = info("x", id="z")
    proposed = {"title": "Stronger", "artist": "Kanye", "catalog_artist": "Kanye",
                "uploader_kind": "unknown"}
    learn(store, i, proposed, "Stronger", "Kanye West")
    assert store.preferred_name("Kanye") == "Kanye West"


# ── With a fake catalog ─────────────────────────────────────────────────────

FAKE = [
    {"artistName": "Future", "trackName": "Life Is Good (feat. Drake)",
     "collectionName": "High Off Life", "trackTimeMillis": 237918,
     "trackExplicitness": "explicit", "artworkUrl100": "https://a/100x100bb.jpg"},
    {"artistName": "Future", "trackName": "Life Is Good (feat. Drake)",
     "collectionName": "Life Is Good (feat. Drake) - Single", "trackTimeMillis": 237735,
     "trackExplicitness": "cleaned", "artworkUrl100": ""},
    {"artistName": "Kendrick Lamar", "trackName": "Not Like Us",
     "collectionName": "Not Like Us - Single", "trackTimeMillis": 274192,
     "trackExplicitness": "explicit", "artworkUrl100": ""},
    {"artistName": "Ye", "trackName": "Stronger", "collectionName": "Graduation",
     "trackTimeMillis": 311867, "trackExplicitness": "explicit", "artworkUrl100": ""},
]


def fake_lookup(term):
    return FAKE


def test_catalog_fixes_lead_vs_guest(store):
    # Uploader got the lead/guest backwards
    r = identify(info("Drake ft. Future - Life Is Good", "RapVibes", duration=238), store, fake_lookup)
    assert (r["artist"], r["title"]) == ("Future", "Life Is Good (feat. Drake)")
    assert r["confidence"] == "matched"
    assert r["album"] == "High Off Life"
    assert "1200x1200" in r["artwork_url"]


def test_catalog_repost_feat_case(store):
    r = identify(info("Not Like Us ft. Kendrick Lamar", "RapNation", duration=275), store, fake_lookup)
    assert (r["artist"], r["title"]) == ("Kendrick Lamar", "Not Like Us")
    assert r["confidence"] == "matched"


def test_catalog_rejects_wrong_length(store):
    r = identify(info("Kendrick Lamar - Not Like Us", "x", duration=600), store, fake_lookup)
    assert r["confidence"] != "matched"
    assert r["artist"] == "Kendrick Lamar"


def test_catalog_variant_keeps_tags(store):
    r = identify(info("Kendrick Lamar - Not Like Us (slowed + reverb)", "x", duration=330), store, fake_lookup)
    assert r["title"] == "Not Like Us (Slowed + Reverb)"
    assert r["artist"] == "Kendrick Lamar"
    assert r["album"] == ""


def test_catalog_alias_applied(store):
    r = identify(info("Kanye West - Stronger", "x", duration=312), store, fake_lookup)
    assert r["artist"] == "Kanye West"
