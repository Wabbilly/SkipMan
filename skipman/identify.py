# ── Artist / Title Identification — SkipMan's brain ─────────────────────────
#
# Turns a messy upload ("🔥 Drake ft. Future - Life Is Good (Official Video)
# [HD]" posted by "RapVibesDaily") into clean tags: who the song is BY, the
# real title, featured guests, and version markers.
#
# Order of trust (highest first):
#   1. Your own past correction for this exact upload
#   2. Apple's catalog (only accepted when title, artist AND length agree)
#   3. Official site fields (YouTube Music "- Topic" uploads)
#   4. Parsing the title ("Artist - Title", "Title by Artist", ...)
#   5. The uploader name, but only when it's an official/artist account
# Your preferred spellings (e.g. "Kanye West", never "Ye") are applied last.
#
# Rules (Billy's):
#   • Artist = who the song is by. Repost accounts never become the artist.
#   • "(feat. X)" stays in the title only when X is really a guest.
#   • Remixes: artist is the ORIGINAL artist; "(X Remix)" stays in the title.
#   • Two credited leads both go in the artist field ("Drake & Future").
#   • Keep: slowed / sped up / nightcore, prod. by, live, remastered,
#     acoustic, demo. Strip: official video, lyrics, HD, emoji, etc.

import re
import unicodedata
import difflib

# ── Vocabulary ──────────────────────────────────────────────────────────────

# Words that, on their own, are junk when found in brackets or as a trailing
# segment. A bracket group is removed only if EVERY word in it is junk.
JUNK_WORDS = {
    "official", "video", "audio", "music", "lyric", "lyrics", "visualizer",
    "visualiser", "hd", "hq", "4k", "1080p", "720p", "explicit", "clean",
    "dirty", "free", "download", "dl", "out", "now", "premiere", "exclusive",
    "new", "mv", "m/v", "with", "full", "song", "high", "quality", "version",
    "uncensored", "censored", "color", "coded", "colour", "animated",
    "vertical", "shot", "by", "cole", "bennett", "directed", "dir", "prod",
    "the", "and", "&", "+", "-", "|", "/", "music-video", "lyric-video",
    "audio-only", "only", "topic", "vevo", "single", "track", "release",
    "oficial", "vídeo", "videoclip", "clip", "letra", "lyrique", "officiel",
    "musical", "visual", "visuals", "performance", "trailer",
    "leak", "leaked", "snippet", "unreleased", "cdq", "hq.", "4k60", "60fps",
}
# Words that can't make a group junk on their own (avoid stripping "(Live)")
_JUNK_CORE = (JUNK_WORDS - {"performance"}) - {"with", "the", "and", "&", "+", "-", "|", "/",
                           "by", "prod", "new", "full", "song", "high",
                           "out", "now", "free", "only", "track", "single"}

# Directed-by credits are junk ("(Dir. by Cole Bennett)")
_DIRECTED = re.compile(r"^\s*(dir\.?|directed)\b", re.I)

# Version markers that STAY in the title, with their display spelling
KEEP_PATTERNS = [
    (re.compile(r"\bslowed\b(?:\s*(?:\+|&|and|\+\s*)?\s*reverb(?:ed)?)?", re.I),
     lambda m: "Slowed + Reverb" if "reverb" in m.group(0).lower() else "Slowed"),
    (re.compile(r"\bsped\s*up\b", re.I), lambda m: "Sped Up"),
    (re.compile(r"\bnightcore\b", re.I), lambda m: "Nightcore"),
    (re.compile(r"\bremaster(?:ed)?(?:\s+\d{4})?\b", re.I), None),
    (re.compile(r"\blive\b", re.I), None),
    (re.compile(r"\bacoustic\b", re.I), None),
    (re.compile(r"\bdemo\b", re.I), None),
    (re.compile(r"\bremix\b", re.I), None),
    (re.compile(r"\b(?:re)?edit\b", re.I), None),
    (re.compile(r"\bbootleg\b", re.I), None),
    (re.compile(r"\bflip\b", re.I), None),
    (re.compile(r"\bvip\b", re.I), None),
    (re.compile(r"\bmashup\b", re.I), None),
    (re.compile(r"\binstrumental\b", re.I), None),
    (re.compile(r"\bextended\b", re.I), None),
    (re.compile(r"\bcover\b", re.I), None),
    (re.compile(r"\bprod\.?\s*(?:by\s+)?\S", re.I), None),
]

# Tags that mean "different recording than the catalog's original"
VARIANT = re.compile(
    r"\b(remix|slowed|sped up|nightcore|live|acoustic|demo|edit|bootleg|"
    r"flip|vip|mashup|instrumental|extended|cover)\b", re.I)

FEAT_WORD = r"(?:feat\.?|ft\.?|featuring|f/|w/)"
_FEAT_INLINE = re.compile(
    r"\s+" + FEAT_WORD + r"\s+(.+?)(?=\s*[\(\[\{]|$)", re.I)
_FEAT_BRACKET = re.compile(r"^\s*(?:" + FEAT_WORD + r"|with)\s+(.+)$", re.I)

_BRACKETS = re.compile(r"[\(\[\{【]([^\(\)\[\]\{\}【】]*)[\)\]\}】]")
_SEPARATORS = re.compile(r"\s+[-–—~]+\s+|\s*[–—]\s*|\s+\|\s+|\s+//\s+|\s+::\s+")
_HASHTAG = re.compile(r"(?:^|\s)#[\w\-]+")
_QUOTED = re.compile(r'^(.+?)\s+["“”\'‘](.+?)["“”\'’]\s*$')
_BY = re.compile(r"^(.+?)\s+by\s+(.+)$", re.I)
_SPACES = re.compile(r"\s+")

# Splitting a credit into individual artists. "x", "&", "and" are only used
# when the whole name isn't a known act ("Simon & Garfunkel").
_LEAD_SPLIT = re.compile(r"\s+(?:&|x|X|×|\+|and|vs\.?)\s+|\s*,\s*")

KNOWN_ACTS = {
    "simon & garfunkel", "tyler, the creator", "earth, wind & fire",
    "crosby, stills, nash & young", "hall & oates", "daryl hall & john oates",
    "florence + the machine", "mumford & sons", "she & him",
    "chase & status", "above & beyond", "macklemore & ryan lewis",
    "marina and the diamonds", "of monsters and men", "kool & the gang",
    "sam & dave", "peaches & herb", "ike & tina turner", "brooks & dunn",
    "big & rich", "dan + shay", "years & years", "rudimental", "salt-n-pepa",
    "earth wind & fire", "outkast", "run-dmc", "drake & 21 savage",
    "angus & julia stone", "bob marley & the wailers",
    "tom petty and the heartbreakers", "huey lewis & the news",
    "prince & the revolution", "sly & the family stone",
    "derek & the dominos", "black country, new road", "now, now",
    "jay & silent bob", "lil nas x", "dj snake", "x ambassadors",
    "malcolm x", "the jacksons", "silk sonic", "$uicideboy$",
}

# Uploader names that are almost always repost / promo / lyric channels
_REPOST_HINTS = re.compile(
    r"\b(music|records|recordings|promo|promotions|lyrics?|lyrical|vibes|"
    r"nation|tv|mixes|channel|network|media|daily|hub|uploads?|bass|trap|"
    r"chill|lo-?fi|sounds|radio|repost|plug|zone|world|hits|beats|"
    r"collective|label|entertainment|official repost|central|planet|"
    r"empire|kingdom|nightcore|slowed|reverb|sped|archive|vault|unreleased|"
    r"leaks|fanpage|fan page|tracks|playlist|selection|selected|"
    r"underground|exclusives|mafia|gang tv|culture)\b", re.I)


# ── Small helpers ───────────────────────────────────────────────────────────

def _clean_space(s):
    return _SPACES.sub(" ", s or "").strip(" -–—|~:·•")


def strip_emoji(s):
    """Remove emoji / pictographs / decorative symbols but keep $, &, etc."""
    out = []
    for ch in s or "":
        cat = unicodedata.category(ch)
        if cat in ("So", "Cs", "Co") or ch in "‍️⃣":
            continue
        out.append(ch)
    return "".join(out)


def norm(s):
    """Lowercase, accents/punctuation removed — for comparisons only."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ").replace("$", "s")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return _SPACES.sub(" ", s).strip()


def core_title(title):
    """Title without any (...) / [...] parts or feat credits — for matching."""
    t = _BRACKETS.sub(" ", title or "")
    t = _FEAT_INLINE.sub(" ", t)
    return norm(t)


def _is_junk_text(text):
    if _DIRECTED.match(text):
        return True
    words = [w for w in re.split(r"[\s/]+", text.lower().strip(" .!-")) if w]
    if not words:
        return True
    if not all(w.strip(".:,!") in JUNK_WORDS for w in words):
        return False
    return any(w.strip(".:,!") in _JUNK_CORE for w in words)


def _keep_tag(text):
    """If text is a version marker we keep, return its display form."""
    t = _clean_space(text)
    for pat, fmt in KEEP_PATTERNS:
        m = pat.search(t)
        if m:
            if fmt and len(t) <= len(m.group(0)) + 2:
                return fmt(m)
            # Title-case a lower/upper-case tag; leave mixed case alone
            if t.islower() or t.isupper():
                t = " ".join(w if w.lower() in ("x", "vs", "vs.") else
                             (w[:1].upper() + w[1:].lower()) for w in t.split())
                t = re.sub(r"\bProd\b\.?", "prod.", t)
                t = re.sub(r"\bBy\b", "by", t)
            return t
    return None


def _is_pure_tag(text):
    """True when text is ONLY a version marker ('Slowed + Reverb')."""
    t = _clean_space(text)
    for pat, _fmt in KEEP_PATTERNS:
        m = pat.search(t)
        if m and len(_clean_space(t[:m.start()] + t[m.end():])) <= 1:
            return True
    return False


def split_names(credit):
    """'Drake & Future' -> ['Drake', 'Future'] unless it's a known act."""
    credit = _clean_space(credit)
    if not credit:
        return []
    if norm(credit) in {norm(k) for k in KNOWN_ACTS}:
        return [credit]
    # Protect known acts inside a longer credit
    protected = {}
    for i, act in enumerate(sorted(KNOWN_ACTS, key=len, reverse=True)):
        m = re.search(re.escape(act), credit, re.I)
        if m:
            token = f"\x00{i}\x00"
            protected[token] = m.group(0)
            credit = credit[:m.start()] + token + credit[m.end():]
    parts = [p for p in _LEAD_SPLIT.split(credit) if p and p.strip()]
    out = []
    for p in parts:
        for tok, real in protected.items():
            p = p.replace(tok, real)
        p = _clean_space(p)
        if p and norm(p) not in {norm(x) for x in out}:
            out.append(p)
    return out


def join_names(names):
    """Apple Music style: 'A', 'A & B', 'A, B & C'."""
    names = [n for n in names if n]
    if len(names) <= 1:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " & " + names[-1]


def clean_uploader(name):
    """'KendrickLamarVEVO' -> 'Kendrick Lamar', 'Drake - Topic' -> 'Drake'."""
    n = (name or "").strip()
    n = re.sub(r"\s*-\s*Topic$", "", n, flags=re.I)
    if re.search(r"vevo$", n, re.I):
        n = re.sub(r"\s*vevo$", "", n, flags=re.I)
        n = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n)
    n = re.sub(r"\s*[\(\[]?official[\)\]]?$", "", n, flags=re.I)
    return n.strip()


# ── Title parsing ───────────────────────────────────────────────────────────

def parse_title(raw):
    """
    Break a raw upload title into parts.

    Returns dict:
      artist_credit: text that names the artist(s) ('' if none found)
      title:         the song name, cleaned
      feats:         ['Guest', ...] found anywhere
      tags:          ['Slowed + Reverb', 'Kaytranada Remix', ...] kept tags
      how:           'separator' | 'quoted' | 'by' | 'none'
    """
    s = strip_emoji(raw or "")
    s = _HASHTAG.sub(" ", s)
    s = s.replace("“", '"').replace("”", '"')
    feats, tags = [], []

    # 1) Bracket groups: junk out, feats + version tags pulled aside
    def _bracket(m):
        inner = m.group(1).strip()
        fm = _FEAT_BRACKET.match(inner)
        if fm:
            feats.extend(split_names(fm.group(1)))
            return " "
        if _is_junk_text(inner):
            return " "
        kt = _keep_tag(inner)
        if kt:
            tags.append(kt)
            return " "
        return m.group(0)  # something else meaningful: "(Pt. 2)"

    prev = None
    while prev != s:          # handles nested / repeated groups
        prev = s
        s = _BRACKETS.sub(_bracket, s)
    s = _clean_space(s)

    # 2) Split on separators, dropping junk segments ("| Official Video")
    segs = [seg.strip() for seg in _SEPARATORS.split(s) if seg.strip()]
    kept = []
    for seg in segs:
        if _is_junk_text(seg):
            continue
        kt = _keep_tag(seg)
        if kt and kept and len(seg.split()) <= 5 and (
                len(kept) >= 2 or _is_pure_tag(seg)):
            tags.append(kt)
            continue
        kept.append(seg)

    artist_credit, title, how = "", "", "none"
    if len(kept) >= 2:
        # 3+ parts ("Artist - Song | Album name"): extra parts are noise
        artist_credit, title, how = kept[0], kept[1], "separator"
    elif kept:
        one = kept[0]
        qm = _QUOTED.match(one)
        bm = _BY.match(one)
        if qm:
            artist_credit, title, how = qm.group(1), qm.group(2), "quoted"
        elif bm and len(bm.group(2).split()) <= 4:
            title, artist_credit, how = bm.group(1), bm.group(2), "by"
        else:
            title = one

    # 3) Inline feats: "Artist ft. Guest - Song" / "Song feat. Guest"
    def _pull_feat(text):
        m = _FEAT_INLINE.search(" " + text)
        if not m:
            return text
        feats.extend(split_names(m.group(1)))
        return _clean_space((" " + text)[:m.start()] + (" " + text)[m.end():])

    artist_credit = _pull_feat(artist_credit)
    title = _pull_feat(title)

    # 4) Unbracketed trailing version tags / junk words: "Song slowed reverb"
    for pat, fmt in KEEP_PATTERNS[:3]:          # slowed / sped up / nightcore
        m = pat.search(title)
        if m and m.start() > 0:
            tags.append(fmt(m))
            title = _clean_space(title[:m.start()] + title[m.end():])
    words = title.split()
    while len(words) > 1 and words[-1].lower().strip(".!") in _JUNK_CORE:
        words.pop()
    title = _clean_space(" ".join(words))
    if len(title) > 2 and title[0] == title[-1] and title[0] in "\"'":
        title = title[1:-1]

    # de-dupe
    seen, ufeats = set(), []
    for f in feats:
        if norm(f) not in seen:
            seen.add(norm(f))
            ufeats.append(f)
    seen, utags = set(), []
    for t in tags:
        if norm(t) not in seen:
            seen.add(norm(t))
            utags.append(t)

    return {"artist_credit": _clean_space(artist_credit),
            "title": title or _clean_space(raw), "feats": ufeats,
            "tags": utags, "how": how}


def compose_title(title, feats=(), tags=()):
    """'Song' + feats + tags -> 'Song (feat. A & B) (Slowed + Reverb)'."""
    out = _clean_space(title)
    if feats and not re.search(r"\(feat\.", out, re.I):
        out += f" (feat. {join_names(list(feats))})"
    for t in tags:
        if norm(t) and norm(t) not in norm(out):
            out += f" ({t})"
    return out


# ── Uploader classification ─────────────────────────────────────────────────

def classify_uploader(info, store=None, leads=()):
    """'official' | 'repost' | 'unknown' for the account that posted it."""
    up = info.get("uploader") or info.get("channel") or ""
    if not up:
        return "unknown"
    learned = store.account_kind(up) if store else None
    if learned:
        return learned
    if re.search(r"-\s*Topic$|vevo$", up, re.I):
        return "official"
    cu = norm(clean_uploader(up))
    if leads and any(norm(l) == cu or (len(cu) > 3 and norm(l).replace(" ", "")
                                       == cu.replace(" ", "")) for l in leads):
        return "official"
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", up)
    if _REPOST_HINTS.search(spaced):
        return "repost"
    if leads:  # title names someone else as the artist
        return "repost"
    return "unknown"


# ── Catalog matching (pure scoring; HTTP lives in catalog.py) ───────────────

def _sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _artist_hit(names, catalog_artist):
    ca = norm(catalog_artist)
    for n in names:
        nn = norm(n)
        if nn and (nn == ca or nn in ca or (len(ca) > 3 and ca in nn)
                   or _sim(nn, ca) > 0.85):
            return True
    return False


def pick_catalog_match(results, title, leads, feats, duration, variant):
    """
    Choose the catalog result that is really this song, or None.
    Requires: same core title, a matching artist, and (for non-variants)
    a length within 4 seconds when we know the length.
    """
    want = core_title(title)
    best, best_score = None, -1.0
    for r in results or []:
        ct = core_title(r.get("trackName", ""))
        ts = _sim(want, ct)
        # "Not Like Us Drake Diss" vs catalog "Not Like Us": accept when the
        # catalog title is the start of ours (extra words were description)
        if ts < 0.86 and len(ct) >= 3 and (want + " ").startswith(ct + " "):
            ts = 0.86
        if ts < 0.86:
            continue
        names = list(leads) + list(feats)
        if names:
            if not _artist_hit(names, r.get("artistName", "")):
                continue
        dur_ok = True
        ms = r.get("trackTimeMillis")
        if duration and ms and not variant:
            dur_ok = abs(duration - ms / 1000.0) <= 4.0
        if not dur_ok:
            continue
        if not names and (not duration or not ms or variant):
            continue  # title alone isn't enough proof
        score = ts * 10
        # Prefer the plain recording over "(Apple Music Live)", "(Remix)"...
        extra = re.sub(r"\((?:feat|with)[^)]*\)", "",
                       r.get("trackName", ""), flags=re.I)
        if _BRACKETS.search(extra):
            score -= 2
        if r.get("_src", "").startswith("Apple"):
            score += 0.2
        if duration and ms:
            score -= abs(duration - ms / 1000.0) / 10.0
        exp = r.get("trackExplicitness")
        score += {"explicit": 0.5, "notExplicit": 0.4}.get(exp, 0)
        if not re.search(r"- (Single|EP)$", r.get("collectionName", "")):
            score += 0.3
        if score > best_score:
            best, best_score = r, score
    return best


# ── Main entry ──────────────────────────────────────────────────────────────

def identify(info, store=None, lookup=None, album_artist=None):
    """
    info: yt-dlp style dict (title, uploader, channel, artist, artists, track,
          album, duration, extractor, id, webpage_url, thumbnail)
    store: Store (for learned corrections / accounts / spellings)
    lookup: fn(term) -> catalog results, or a list of such fns tried in
            order (None = offline)
    album_artist: when this is a track of an album you're building

    Returns dict: title, artist, album, confidence ('matched' | 'guess' |
    'check'), source (plain-English reason), artwork_url, uploader_kind,
    catalog_artist (what Apple called them; used to learn spellings).
    """
    raw = info.get("title") or ""
    uploader = info.get("uploader") or info.get("channel") or ""
    duration = info.get("duration")
    extractor = (info.get("extractor") or info.get("extractor_key") or "").lower()
    keys = [info.get("id") and f"{extractor}:{info.get('id')}", raw]

    def _finish(res):
        res.setdefault("album", info.get("album") or "")
        res.setdefault("artwork_url", "")
        res.setdefault("catalog_artist", "")
        res.setdefault("uploader_kind", "unknown")
        if store:
            parts = split_names(res["artist"])
            res["artist"] = join_names([store.preferred_name(p) for p in parts]) \
                if len(parts) > 1 else store.preferred_name(res["artist"])
            res["title"] = re.sub(
                r"\(feat\. ([^)]+)\)",
                lambda m: "(feat. " + join_names(
                    [store.preferred_name(p) for p in split_names(m.group(1))]) + ")",
                res["title"])
        return res

    # 1) Your past correction wins outright
    if store:
        c = store.correction(*keys)
        if c:
            return _finish({"title": c["title"], "artist": c["artist"],
                            "confidence": "matched",
                            "source": "Your earlier edit"})

    p = parse_title(raw)
    title, feats, tags = p["title"], list(p["feats"]), list(p["tags"])
    leads = split_names(p["artist_credit"])
    source = {"separator": "Read from the title", "quoted": "Read from the title",
              "by": "Read from the title"}.get(p["how"], "")

    # 2) Official site fields (YouTube Music / "- Topic" uploads)
    site_artists = info.get("artists") or (
        [info["artist"]] if info.get("artist") else [])
    if extractor.startswith("youtube") and site_artists and info.get("track"):
        tp = parse_title(info["track"])
        title = tp["title"]
        tags = tp["tags"] or tags
        site_feats = [a for a in site_artists[1:] if
                      norm(a) in norm(info["track"]) or a in tp["feats"]]
        feats = tp["feats"] or site_feats
        leads = [a for a in site_artists if norm(a) not in
                 {norm(f) for f in feats}] or site_artists[:1]
        source = "YouTube Music listing"

    kind = classify_uploader(info, store, leads)

    # 3) No artist in the title: lean on the uploader only if it's official
    if not leads:
        if album_artist:
            leads, source = [album_artist], "Album artist"
        elif kind == "official":
            leads, source = [clean_uploader(uploader)], "Official artist account"
        elif kind == "unknown" and uploader and "soundcloud" in extractor:
            leads, source = [clean_uploader(uploader)], "SoundCloud uploader"
    # Remix posted by the remixer with no original artist named: unknown
    if leads and not p["artist_credit"] and kind != "official":
        for t in tags:
            if re.search(r"remix|edit|flip|bootleg", t, re.I) and \
                    norm(leads[0]) in norm(t):
                leads, source = [], ""

    variant = bool(VARIANT.search(" ".join(tags)))

    # 4) Apple catalog check
    match = None
    lookups = lookup if isinstance(lookup, (list, tuple)) else (
        [lookup] if lookup else [])
    for fn in lookups:
        if match:
            break
        terms = []
        if leads:
            terms.append(f"{' '.join(leads)} {core_title(title)}")
        if feats:
            terms.append(f"{core_title(title)} {' '.join(feats)}")
        terms.append(core_title(title))
        seen = set()
        for term in terms:
            if term in seen or not term.strip():
                continue
            seen.add(term)
            try:
                results = fn(term)
            except Exception:
                results = []
            match = pick_catalog_match(results, title, leads, feats,
                                       duration, variant)
            if match:
                break

    if match:
        cat_title = match["trackName"]
        if variant:
            # Different recording (remix, slowed...): keep OUR title, take
            # only the catalog's official feat credits
            fm = re.search(r"\((?:feat\.|with) ([^)]+)\)", cat_title, re.I)
            cat_feats = split_names(fm.group(1)) if fm else []
            final_title = compose_title(title, cat_feats, tags)
        else:
            # Repost case "Not Like Us ft. Kendrick Lamar": the 'guest' was
            # the actual artist — the catalog decides.
            final_title = compose_title(cat_title, (), tags)
        art = match.get("artwork") or (match.get("artworkUrl100") or "").replace(
            "100x100bb", "1200x1200bb")
        album = re.sub(r"\s*-\s*(Single|EP)$", "",
                       match.get("collectionName", "")) if not variant else ""
        return _finish({
            "title": final_title, "artist": match["artistName"],
            "album": album if not album_artist else "",
            "confidence": "matched",
            "source": match.get("_src", "Apple Music catalog")
            + (" (original song)" if variant else ""),
            "artwork_url": art, "uploader_kind": kind,
            "catalog_artist": match["artistName"]})

    # 5) No artist at all (e.g. a remix posted by the remixer): suggest the
    #    most likely original artist from the catalog, flagged for a check
    if not leads and lookups and not (kind == "repost" and feats):
        for fn in lookups:
            try:
                results = fn(core_title(title))
            except Exception:
                results = []
            hit = next((r for r in results
                        if core_title(r.get("trackName", "")) == core_title(title)
                        and r.get("artistName")), None)
            if hit:
                return _finish({
                    "title": compose_title(title, feats, tags),
                    "artist": hit["artistName"], "confidence": "check",
                    "source": "Likely original artist — please check",
                    "uploader_kind": kind})

    # 6) Best guess from what we parsed
    artist = join_names(leads)
    if not artist and kind == "repost" and feats and p["how"] == "none":
        # "Song ft. X" on a repost page, nothing else to go on: X is likely
        # the artist, not a guest. Flag it for a look.
        artist, feats = join_names(feats), []
        return _finish({"title": compose_title(title, feats, tags),
                        "artist": artist, "confidence": "check",
                        "source": "Guessed — repost page, check the artist",
                        "uploader_kind": kind})
    conf = "guess" if artist else "check"
    if kind == "unknown" and not p["artist_credit"] and "youtube" in extractor:
        conf = "check"
    return _finish({"title": compose_title(title, feats, tags),
                    "artist": artist, "confidence": conf,
                    "source": source or ("No artist found — please fill in"
                                         if not artist else "Best guess"),
                    "uploader_kind": kind})


# ── Learning from your edits ────────────────────────────────────────────────

def learn(store, info, proposed, final_title, final_artist):
    """Call when you send a song. Teaches SkipMan from what you changed."""
    if not store:
        return
    raw = info.get("title") or ""
    extractor = (info.get("extractor") or "").lower()
    keys = [info.get("id") and f"{extractor}:{info.get('id')}", raw]
    uploader = info.get("uploader") or info.get("channel") or ""

    changed = (final_title != proposed.get("title")
               or final_artist != proposed.get("artist"))
    if changed:
        store.learn_correction(keys, final_title, final_artist)

    # Accounts: was the uploader the real artist?
    if uploader and final_artist:
        cu = norm(clean_uploader(uploader))
        names = [norm(n) for n in split_names(final_artist)]
        if cu in names or cu.replace(" ", "") in [n.replace(" ", "") for n in names]:
            store.learn_account(uploader, "official")
        elif proposed.get("uploader_kind") != "official":
            store.learn_account(uploader, "repost")

    # Spellings: catalog said "Ye", you typed "Kanye West"
    cat = proposed.get("catalog_artist")
    if cat and final_artist and norm(final_artist) != norm(proposed.get("artist")):
        cparts, fparts = split_names(cat), split_names(final_artist)
        if len(cparts) == len(fparts):
            for c, f in zip(cparts, fparts):
                store.learn_alias(c, f)
