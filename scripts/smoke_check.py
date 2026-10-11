#!/usr/bin/env python3
"""Post-deploy smoke check for the markjin site (stdlib only).

Usage: python3 scripts/smoke_check.py [--base URL] [--json-out FILE] [--pair-config scripts/smoke_pairs.json]
Exit code: 0 = all checks passed, 1 = at least one failure or page flagged REVIEW (sample too small).
External links are reported but never fail the run.
"""
import argparse, json, os, re, sys, time, unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
import datetime
from urllib.error import HTTPError, URLError

UA = "markjin-smoke-check/1.0"
LANGS = ("zh", "en")
_cache = {}
_final = {}   # requested URL -> final URL after redirects


def fetch(url, want_body=True, retries=2):
    """Return (status, body_text). Status 0 = network error."""
    if url in _cache and (not want_body or _cache[url][1] is not None):
        return _cache[url]
    last = (0, None)
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": UA}, method="GET")
            with urlopen(req, timeout=20) as r:
                body = r.read().decode("utf-8", "replace") if want_body else None
                last = (r.status, body)
                _final[url] = r.geturl()
                break
        except HTTPError as e:
            last = (e.code, None)
            if e.code < 500:
                break
        except (URLError, OSError) as e:
            last = (0, None)
        time.sleep(1 + attempt)
    _cache[url] = last
    return last


_REAL_FETCH = fetch


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None   # surface the 3xx itself as an HTTPError instead of following it


_NOFOLLOW = build_opener(_NoRedirect)


def fetch_status_nofollow(url, retries=2):
    """HTTP status of `url` WITHOUT following redirects (a 301/302 is reported as such, never as the
    status of its target). Used for retired paths, which must answer 404 themselves."""
    if fetch is not _REAL_FETCH:          # test doubles of fetch() already report raw statuses
        return fetch(url, want_body=False)[0]
    st = 0
    for attempt in range(retries + 1):
        try:
            with _NOFOLLOW.open(Request(url, headers={"User-Agent": UA}, method="GET"), timeout=20) as r:
                st = r.status
                break
        except HTTPError as e:
            st = e.code
            if e.code < 500:
                break
        except (URLError, OSError):
            st = 0
        time.sleep(1 + attempt)
    return st


class Page(HTMLParser):
    """Structural facts used by the link/table checks: <html lang>, links and assets, tables, CSS.
    Text-based checks use VisibleText instead."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_lang = None
        self.links = []          # (kind, url)
        self.tables = []         # class attr of each <table>
        self._styles = []
        self._in_style = False
        self._inert = 0          # depth inside <template>/<noscript>: nothing there counts

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.html_lang = a.get("lang")
        if tag in ("template", "noscript"):
            self._inert += 1
            return
        if self._inert:
            return
        if tag == "style":
            self._in_style = True
        if tag == "a" and a.get("href"):
            self.links.append(("link", a["href"]))
        if tag in ("img", "script", "source", "iframe", "video", "audio", "track", "embed", "input") and a.get("src"):
            self.links.append(("asset", a["src"]))
        if tag in ("img", "source") and a.get("srcset"):
            for u in parse_srcset(a["srcset"]):
                self.links.append(("asset", u))
        if tag == "video" and a.get("poster"):
            self.links.append(("asset", a["poster"]))
        if tag == "object" and a.get("data"):
            self.links.append(("asset", a["data"]))
        if tag == "link" and a.get("href"):
            self.links.append(("asset", a["href"]))
        if a.get("style"):
            for u in css_urls(a["style"]):
                self.links.append(("asset", u))
        if tag == "table":
            self.tables.append(a.get("class"))

    def handle_endtag(self, tag):
        if tag in ("template", "noscript") and self._inert:
            self._inert -= 1
            return
        if tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self._in_style and not self._inert:
            self._styles.append(data)
            for u in css_urls(data):
                self.links.append(("asset", u))

    @property
    def css(self):
        return "".join(self._styles)


def parse_srcset(value):
    """URLs from a srcset attribute, following the HTML "parse a srcset attribute" algorithm:
    candidates are separated by commas; each is a URL (a run of non-whitespace characters, which
    may itself contain commas) optionally followed by descriptors; trailing commas on a URL end
    the candidate; inside descriptors, commas within parentheses do not split."""
    urls, i, n = [], 0, len(value)
    ws = " \t\n\r\f"
    while i < n:
        while i < n and (value[i] in ws or value[i] == ","):
            i += 1
        if i >= n:
            break
        j = i
        while j < n and value[j] not in ws:
            j += 1
        url = value[i:j]
        i = j
        if url.endswith(","):
            url = url.rstrip(",")
        else:
            depth = 0   # skip descriptors up to the next top-level comma
            while i < n:
                ch = value[i]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth = max(0, depth - 1)
                elif ch == "," and depth == 0:
                    i += 1
                    break
                i += 1
        if url:
            urls.append(url)
    return urls


def css_urls(css):
    """URLs referenced by url(...) in CSS text (data: URLs skipped by the caller)."""
    out = []
    for m in re.finditer(r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^)\s]*))\s*\)", css or "", re.I):
        u = next(g for g in m.groups() if g is not None)
        if u:
            out.append(u)
    return out


MAX_STRIP_FRAC = 0.60          # FAIL if stripping would remove more than this share of letters
MIN_LETTERS = {"daily": 800}   # about has no minimum letter count; its language ratio is still checked


def is_letter(c):
    """Letter filter for the language ratio and the minimum-letter counts:
    Unicode category L* (CJK included), minus blank fillers. Digits do not count."""
    return unicodedata.category(c)[0] == "L" and c not in BLANK_LETTERS


def is_counted_char(c):
    """Filter for the 'page has visible text' check only: letters (is_letter) or digits (N*)."""
    return is_letter(c) or unicodedata.category(c)[0] == "N"


def _is_cjk(c):
    return "\u4e00" <= c <= "\u9fff" or "\u3400" <= c <= "\u4dbf"


def _ratio(text):
    letters = [c for c in text if is_letter(c)]
    if not letters:
        return 0.0, 0
    return sum(1 for c in letters if _is_cjk(c)) / len(letters), len(letters)


def body_language_ratio(html, lang):
    """Language ratio over the visible text of the page's single <main>, using the same parser,
    visibility rules and letter filter as visible_text (no regex extraction, no whole-page fallback).
    Return dict: raw_ratio/raw_letters (before stripping), ratio/letters (after),
    stripped_frac, main_count. Stripping removes code/pre and link text (en pages also
    blockquotes); zh pages also drop the source line right before a line starting with '译文：'."""
    v = parse_visible(html, lang)
    raw_ratio, raw_n = _ratio(v.main_raw())
    lines = [l.strip() for l in v.main_stripped().splitlines() if l.strip()]
    if lang == "zh":
        drop = {i - 1 for i, l in enumerate(lines) if l.startswith("译文：") and i > 0}
        lines = [l for i, l in enumerate(lines) if i not in drop]
    ratio, n = _ratio("\n".join(lines))
    frac = (raw_n - n) / raw_n if raw_n else 0.0
    return {"raw_ratio": raw_ratio, "raw_letters": raw_n, "ratio": ratio, "letters": n,
            "stripped_frac": frac, "main_count": v.main_count}


def judge_language(info, lang, page_type):
    """Not applied to home pages (see check_page); about has no letter minimum (MIN_LETTERS). Return (status, detail); status is 'ok', 'fail' or 'review'."""
    need = ">=0.30" if lang == "zh" else "<=0.05"
    detail = "CJK ratio before stripping %.2f over %d letters; after %.2f over %d letters; stripped %.0f%% (need %s, strip cap %.0f%%, min %d letters for %s)" % (
        info["raw_ratio"], info["raw_letters"], info["ratio"], info["letters"],
        100 * info["stripped_frac"], need, 100 * MAX_STRIP_FRAC, MIN_LETTERS.get(page_type, 0), page_type)
    if info.get("main_count", 1) != 1:
        return "fail", "need exactly one <main>, found %d; " % info.get("main_count", 0) + detail
    if info["letters"] == 0:
        return "fail", "no body text left after stripping; " + detail
    if info["stripped_frac"] > MAX_STRIP_FRAC:
        return "fail", "stripping would remove too much text; " + detail
    def good(r):
        return r >= 0.3 if lang == "zh" else r <= 0.05
    if not (good(info["ratio"]) and good(info["raw_ratio"])):
        return "fail", detail
    if info["letters"] < MIN_LETTERS.get(page_type, 0):
        return "review", "sample too small, manual review needed; " + detail
    return "ok", detail


def site_url(base, sp):
    """Absolute URL of site path `sp` ('/x/' relative to the base path)."""
    return urljoin(base, sp.lstrip("/"))


def site_path(base, url):
    """Site path ('/x/') of an absolute URL under `base`, or None if off-site / outside the base path."""
    b, u = urlparse(base), urlparse(url)
    if (u.scheme, u.netloc.lower()) != (b.scheme, b.netloc.lower()):
        return None
    root = b.path.rstrip("/")
    if u.path == root:
        return "/"
    if not u.path.startswith(root + "/"):
        return None
    return u.path[len(root):]


def norm_url(url):
    """scheme://host/path?query without fragment, host lowercased."""
    u = urlparse(urldefrag(url)[0])
    return u._replace(netloc=u.netloc.lower()).geturl()


def lang_url(base, lang, path):
    path = path.lstrip("/")
    return urljoin(base, path if lang == "zh" else "en/" + path)


def other_lang_path(path):
    """Given a site path (relative to the base path), return the counterpart path in the other language."""
    if path.startswith("/en/") or path == "/en":
        return "/" + path[len("/en/"):]
    return "/en" + path


# Retired (taken-down) sections: every listed path must answer 404, and no checked page, home page or
# expected sitemap may link to / list anything under a retired prefix (decision 2026-10-11 22:39, quote_ref t212u).
RETIRED = {"prefixes": ["/posts/tongyi/", "/framework/", "/posts/daily/2026-10-10/", "/posts/daily/2026-10-11/"], "paths": []}   # defaults; replaced from the discovery config by discover()


def retired_hit(sp):
    """True if site path `sp` lies under a retired prefix (zh or en form)."""
    if sp is None:
        return False
    for pre in RETIRED["prefixes"]:
        if sp.startswith(pre) or sp.startswith("/en" + pre):
            return True
    return False


class SitemapError(Exception):
    pass


def sitemap_locs(xml_text):
    """<loc> values from sitemap / sitemap-index XML, via the XML parser (namespace-agnostic).
    Raises SitemapError if the XML cannot be parsed (callers turn that into a FAIL)."""
    import xml.etree.ElementTree as ET
    if not (xml_text or "").strip():
        raise SitemapError("empty sitemap body")
    try:
        root = ET.fromstring((xml_text or "").encode("utf-8"))
    except ET.ParseError as e:
        raise SitemapError("sitemap XML parse error: %s" % e)
    kind = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
    if kind not in ("urlset", "sitemapindex"):
        raise SitemapError("not a sitemap (root element <%s>, expected <urlset> or <sitemapindex>)" % kind)
    locs = [(el.text or "").strip() for el in root.iter()
            if isinstance(el.tag, str) and el.tag.rsplit("}", 1)[-1] == "loc" and (el.text or "").strip()]
    if not locs:
        raise SitemapError("sitemap <%s> has no <loc> entries" % kind)
    return locs


def html_anchor_hrefs(html):
    """href of every <a> element, via the HTML parser (entities decoded)."""
    p = Page()
    p.feed(html or "")
    p.close()
    return [h for kind, h in p.links if kind == "link"]


def _site_paths_in(base, page_url, body, kind="href"):
    out = []
    found = html_anchor_hrefs(body) if kind == "href" else sitemap_locs(body)
    for h in found:
        full = urldefrag(urljoin(page_url, h.strip()))[0]
        if urlparse(full).query:
            continue
        sp = site_path(base, full)
        if sp is not None:
            out.append(sp)
    return out


DISCOVERY_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke_discovery.json")
DEFAULT_DISCOVERY = {"expected_sitemaps": ["/sitemap.xml", "/zh/sitemap.xml", "/en/sitemap.xml"],
                     "min_pages": {"daily": 1},
                     "daily_min_effective_from": "2026-10-12T07:00",
                     "retired_prefixes": ["/posts/tongyi/", "/framework/", "/posts/daily/2026-10-10/", "/posts/daily/2026-10-11/"],
                     "retired_paths": ["/posts/tongyi/", "/framework/", "/framework/macro/",
                                       "/en/framework/", "/en/framework/macro/", "/en/posts/tongyi/",
                                       "/posts/daily/2026-10-10/", "/posts/daily/2026-10-11/",
                                       "/en/posts/daily/2026-10-10/", "/en/posts/daily/2026-10-11/"]}


def load_discovery_config(path=None):
    """Load and validate the discovery config; raises PairConfigError on any problem."""
    path = path or DISCOVERY_CONFIG
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except OSError as e:
        raise PairConfigError("cannot read discovery config %s: %s" % (path, e))
    except ValueError as e:
        raise PairConfigError("discovery config %s is not valid JSON: %s" % (path, e))
    sm = cfg.get("expected_sitemaps") if isinstance(cfg, dict) else None
    mp = cfg.get("min_pages") if isinstance(cfg, dict) else None
    if not (isinstance(sm, list) and sm and all(isinstance(x, str) and x.startswith("/") for x in sm)):
        raise PairConfigError("discovery config %s: expected_sitemaps must be a non-empty list of site paths" % path)
    lacking = [x for x in FLOOR_SITEMAPS if x not in sm]
    if lacking:
        raise PairConfigError("discovery config %s: expected_sitemaps is below the floor, missing %s" % (path, lacking))
    if not (isinstance(mp, dict) and all(k in mp for k in FLOOR_MIN_PAGES)
            and all(type(v) is int for v in mp.values())):
        raise PairConfigError("discovery config %s: min_pages needs an integer daily value (not a boolean)" % path)
    low = ["%s=%d < %d" % (k, mp[k], v) for k, v in FLOOR_MIN_PAGES.items() if mp[k] < v]
    if low:
        raise PairConfigError("discovery config %s: min_pages below the floor: %s" % (path, ", ".join(low)))
    rp, rpa = cfg.get("retired_prefixes"), cfg.get("retired_paths")
    for key, v in (("retired_prefixes", rp), ("retired_paths", rpa)):
        if not (isinstance(v, list) and v and all(isinstance(x, str) and x.startswith("/") and x.endswith("/") for x in v)):
            raise PairConfigError("discovery config %s: %s must be a non-empty list of site paths ('/x/')" % (path, key))
    lacking = [x for x in FLOOR_RETIRED_PREFIXES if x not in rp]
    if lacking:
        raise PairConfigError("discovery config %s: retired_prefixes is below the floor, missing %s" % (path, lacking))
    lacking = [x for x in FLOOR_RETIRED_PATHS if x not in rpa]
    if lacking:
        raise PairConfigError("discovery config %s: retired_paths is below the floor, missing %s" % (path, lacking))
    eff = cfg.get("daily_min_effective_from")
    if eff is not None:
        if not (isinstance(eff, str) and re.match(r"^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d$", eff)):
            raise PairConfigError("discovery config %s: daily_min_effective_from must be YYYY-MM-DDTHH:MM (SGT)" % path)
        if eff < FLOOR_DAILY_EFFECTIVE_EARLIEST:
            raise PairConfigError("discovery config %s: daily_min_effective_from %s is earlier than the floor %s"
                                  % (path, eff, FLOOR_DAILY_EFFECTIVE_EARLIEST))
        if eff > CAP_DAILY_EFFECTIVE_LATEST:
            raise PairConfigError("discovery config %s: daily_min_effective_from %s is later than the cap %s"
                                  % (path, eff, CAP_DAILY_EFFECTIVE_LATEST))
    outside = [x for x in rpa if not any(x.startswith(pre) or x.startswith("/en" + pre) for pre in rp)]
    if outside:
        raise PairConfigError("discovery config %s: retired_paths not under any retired prefix: %s" % (path, outside))
    return cfg


_sources = []   # every discovery source fetched in this run (dicts, see _record_source)


def _record_source(role, url, status, links=None, site_paths=None, found=None, error=None):
    d = {"role": role, "url": url, "status": status, "links": links, "site_paths": site_paths,
         "found": found, "error": error}
    _sources.append(d)
    return d


def format_source(d):
    parts = ["%s %s -> %s" % (d["role"], d["url"], d["status"])]
    if d["links"] is not None:
        parts.append("%d link(s)/<loc>" % d["links"])
    if d["site_paths"] is not None:
        parts.append("%d in-site path(s)" % d["site_paths"])
    if d["found"] is not None:
        parts.append("%d new page(s)" % d["found"])
    if d["error"]:
        parts.append("FAIL: " + d["error"])
    return ", ".join(parts)


def _scan(base, url, body, kind):
    """(raw link/loc count, in-site site paths) for one source body."""
    raw = html_anchor_hrefs(body) if kind == "href" else sitemap_locs(body)
    return len(raw), _site_paths_in(base, url, body, kind)


def scan_sources(base, expected_sitemaps=None):
    """Fetch the zh and en home pages and every expected sitemap; record each as a discovery source.
    Every expected sitemap must be served (200), parse as a sitemap and contain in-site <loc>s.
    No source may link to / list a path under a retired prefix. Returns the list of errors."""
    errors = []
    expected = sorted(set(expected_sitemaps if expected_sitemaps is not None else DEFAULT_DISCOVERY["expected_sitemaps"]))
    for sp, kind in [("/", "href"), ("/en/", "href")] + [(x, "loc") for x in expected]:
        url = site_url(base, sp)
        st, body = fetch(url)
        role = "sitemap" if kind == "loc" else "seed"
        if kind == "loc" and st != 200:
            _record_source(role, url, st, error="expected sitemap -> HTTP %s" % st)
            errors.append("expected sitemap %s -> HTTP %s" % (sp, st))
            continue
        if kind == "href" and not (st == 200 and body):
            _record_source(role, url, st)
            continue
        try:
            n, paths = _scan(base, url, body, kind)
        except SitemapError as e:
            _record_source(role, url, st, error=str(e))
            errors.append("expected sitemap %s: %s" % (sp, e))
            continue
        err = None
        if kind == "loc" and not paths:
            err = "no <loc> inside the site base (%d <loc> all outside)" % n
        hits = sorted({x for x in paths if retired_hit(x)})
        if hits:
            err = (err + "; " if err else "") + "retired path(s) still listed/linked: " + ", ".join(hits)
        _record_source(role, url, st, n, len(paths), None, err)
        if err:
            errors.append("%s %s: %s" % (role, sp, err))
    return errors


# A daily post's slug is exactly its date (YYYY-MM-DD). Anything else under /posts/daily/ -- e.g. the
# welcome post 2026-10-10-welcome -- is NOT a daily and never counts toward the daily minimum or pairing.
DAILY_RE = re.compile(r"^(?:/en)?/posts/daily/(\d{4}-\d{2}-\d{2})/$")


DAILY_PUBLISH_HM = "07:00"   # SGT publication deadline of each day's daily


def now_sgt():
    """Current Singapore time (UTC+8) as 'YYYY-MM-DDTHH:MM'. Patched in tests."""
    return time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 8 * 3600))


def today_sgt():
    return now_sgt()[:10]


def due_daily(dcfg):
    """(due date or None, explanation). The daily rule takes effect at `daily_min_effective_from`
    (SGT). Before that instant no daily
    is required. The instant is clamped to [FLOOR_DAILY_EFFECTIVE_EARLIEST, CAP_DAILY_EFFECTIVE_LATEST]
    (2026-10-12T07:00 .. 2026-10-19T07:00): it can be set later than the first publication, never earlier,
    and never postponed indefinitely. From then on, the daily of the current SGT date is due once it is 07:00 SGT or later;
    before 07:00 the previous day's daily is due. The due date must exist in zh AND en (paired)."""
    eff = dcfg.get("daily_min_effective_from") or FLOOR_DAILY_EFFECTIVE_EARLIEST
    if len(eff) == 10:
        eff += "T00:00"
    eff = min(max(eff, FLOOR_DAILY_EFFECTIVE_EARLIEST), CAP_DAILY_EFFECTIVE_LATEST)
    now = now_sgt()
    if now < eff:
        return None, "daily rule not yet in effect (starts %s SGT; now %s SGT): 0 dailies allowed" % (eff, now)
    day = now[:10]
    if now[11:] < DAILY_PUBLISH_HM:
        day = (datetime.date.fromisoformat(day) - datetime.timedelta(days=1)).isoformat()
    return day, "daily rule in effect since %s SGT; now %s SGT: the %s daily must exist in zh and en" % (eff, now, day)


def latest_daily(base, lang):
    """Site path of the newest daily post in `lang` (from the list page, else the sitemap).
    Both sources are recorded in the discovery source list."""
    url = lang_url(base, lang, "posts/daily/")
    st, body = fetch(url)
    cands, src = [], "list %s -> %s" % (url, st)
    latest_daily.count = 0

    def match(paths):
        out = []
        for sp in paths:
            m = DAILY_RE.match(sp)
            if m and (sp.startswith("/en/") == (lang == "en")):
                out.append((m.group(1), sp))
        return out

    if st == 200 and body:
        n, paths = _scan(base, url, body, "href")
        cands = match(paths)
        _record_source("%s daily list" % lang, url, st, n, len(paths), len({c[1] for c in cands}))
    else:
        _record_source("%s daily list" % lang, url, st)
    if not cands:  # sitemap fallback
        smurl = site_url(base, ("/en/" if lang == "en" else "/zh/") + "sitemap.xml")
        st, sm = fetch(smurl)
        src += "; sitemap %s -> %s" % (smurl, st)
        if st == 200:
            try:
                n, paths = _scan(base, smurl, sm, "loc")
                cands = match(paths)
                _record_source("%s daily sitemap fallback" % lang, smurl, st, n, len(paths), len({c[1] for c in cands}))
            except SitemapError as e:
                src += " (%s)" % e
                _record_source("%s daily sitemap fallback" % lang, smurl, st, error=str(e))
        else:
            _record_source("%s daily sitemap fallback" % lang, smurl, st)
    latest_daily.count = len({c[1] for c in cands})
    return (max(cands)[1] if cands else None), src


def discover(base, dcfg=None):
    """Return list of (name, zh_site_path_or_None, en_site_path_or_None, notes).
    Paths are relative to the base path."""
    dcfg = dcfg or DEFAULT_DISCOVERY
    mins = dcfg["min_pages"]
    RETIRED["prefixes"] = list(dcfg.get("retired_prefixes", DEFAULT_DISCOVERY["retired_prefixes"]))
    RETIRED["paths"] = list(dcfg.get("retired_paths", DEFAULT_DISCOVERY["retired_paths"]))
    dcfg = dict(DEFAULT_DISCOVERY, **dcfg)
    discover.retired_ok = []
    del _sources[:]
    pages = [("home", "/", "/en/", [])]
    due, why = due_daily(dcfg)
    need = 0 if due is None else mins["daily"]
    discover.daily_rule = why
    zh_daily, src = latest_daily(base, "zh")
    n_daily = latest_daily.count
    if zh_daily is not None and n_daily < need:
        pages.append(("daily (too few)", None, None,
                      ["FAIL: %d zh daily post(s) discovered, minimum is %d (%s; %s)" % (n_daily, need, why, src)]))
    en_latest, _ = latest_daily(base, "en")
    if due is not None:
        zd = "/posts/daily/%s/" % due
        if zh_daily != zd:
            pages.append(("due daily", zd, "/en" + zd, ["due by date (%s); latest zh daily found: %s" % (why, zh_daily)]))
    if zh_daily is None and need == 0:
        discover.daily_rule += "; no zh daily found, allowed (%s)" % src
        if en_latest is not None:
            pages.append(("latest daily", None, None,
                          ["FAIL: en daily %s exists but no zh daily was found (%s)" % (en_latest, src)]))
    elif zh_daily is None:
        pages.append(("latest daily", None, None,
                      ["FAIL: no zh daily post found (%s; %s)" % (why, src)]))
    else:
        en_pair = "/en" + zh_daily   # same date/slug as the latest zh daily
        notes = ["paired by date: zh %s <-> en %s" % (zh_daily, en_pair)]
        if en_latest and en_latest != en_pair:
            notes.append("en daily list's latest is %s (differs from the zh date; the en page for the zh date is checked)" % en_latest)
        pages.append(("latest daily", zh_daily, en_pair, notes))
    pages.append(("about", "/about/", "/en/about/", []))
    errs = scan_sources(base, dcfg["expected_sitemaps"])
    discover.sources = [dict(d) for d in _sources]
    if errs:
        pages.append(("sources (sitemap error / retired link)", None, None, ["FAIL: " + "; ".join(errs)]))
    for rp in dcfg["retired_paths"]:
        st = fetch_status_nofollow(site_url(base, rp))
        if st != 404:
            pages.append(("retired " + rp, None, None,
                          ["FAIL: retired path %s must answer 404, got HTTP %s" % (rp, st)]))
        else:
            discover.retired_ok.append(rp)
    return pages


# letters/digits (category L*/N*) or blank-pattern characters that render as blank space
BLANK_LETTERS = set("\u115f\u1160\u3164\uffa0\u2800\u17b4\u17b5\u1cbb\u1cbc")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
        "source", "track", "wbr"}
NONRENDER = {"head", "title", "script", "style", "template", "noscript"}


def parse_style(style):
    """Parse an inline style attribute into {property: value} following CSS cascade rules
    within one declaration block: later declarations win, except that an earlier
    `!important` declaration beats a later normal one. Comments are removed, custom
    properties (--x) are ignored, property names are case-insensitive."""
    style = re.sub(r"/\*.*?\*/", "", style or "", flags=re.S)
    decls, buf, depth, quote = [], "", 0, None
    for ch in style:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            decls.append(buf); buf = ""
            continue
        buf += ch
    decls.append(buf)
    out = {}
    for d in decls:
        if ":" not in d:
            continue
        prop, val = d.split(":", 1)
        prop = prop.strip().lower()
        if not prop or prop.startswith("--") or not re.match(r"^-?[a-z][a-z0-9-]*$", prop):
            continue
        val = val.strip()
        imp = bool(re.search(r"!\s*important\s*$", val, re.I))
        if imp:
            val = re.sub(r"!\s*important\s*$", "", val, flags=re.I).strip()
        if not val:
            continue
        if prop in out and out[prop][1] and not imp:
            continue
        out[prop] = (val.lower(), imp)
    return {k: v for k, (v, _) in out.items()}


def element_visibility(tag, attrs):
    """Return (removed, visibility). removed=True hides the element and all descendants
    (non-rendered tags, hidden attribute, aria-hidden="true", display:none).
    visibility is 'hidden', 'visible' or None (inherit); a descendant may override
    an inherited visibility:hidden with visibility:visible, as in CSS."""
    if tag in NONRENDER:
        return True, None
    a = {k.lower(): (v or "") for k, v in attrs}
    if "hidden" in a:
        return True, None
    if a.get("aria-hidden", "").strip().lower() == "true":
        return True, None
    st = parse_style(a.get("style", ""))
    disp = st.get("display", "").split()
    if disp and disp[0] == "none":
        return True, None
    v = st.get("visibility", "").split()
    v = v[0] if v else ""
    if v in ("hidden", "collapse"):
        return False, "hidden"
    if v in ("visible", "initial"):
        return False, "visible"
    return False, None


BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "td", "th", "blockquote",
         "pre", "section", "article", "header", "footer", "nav", "ul", "ol", "table", "main", "dt", "dd"}


class VisibleText(HTMLParser):
    """One parser for all text-based checks.
    Visible = inside <body>, no ancestor (or self) that is non-rendered
    (head/title/script/style/template/noscript), has the hidden attribute, aria-hidden="true"
    or inline display:none; visibility:hidden is inherited but a descendant with
    visibility:visible shows again (applies to <html>, <body>, <main> too).
    Collects: visible text inside <main> (raw, and with code/pre/link text[/blockquote] stripped),
    visible body text outside code/pre (for the Markdown check), visible links inside
    <span class="lang">, and the number of <main> elements in <body>."""

    def __init__(self, lang="zh"):
        super().__init__(convert_charrefs=True)
        self.strip = {"code", "pre", "a"} | ({"blockquote"} if lang != "zh" else set())
        self.stack = []      # (tag, removed, visibility, is_lang_span)
        self.main_count = 0
        self._raw, self._stripped, self._md = [], [], []
        self._key = []           # visible text in <main>, <header>, <footer> (pair checks)
        self.key_links = []      # visible <a href> in <main>, <header>, <footer> (pair checks)
        self.lang_links = []

    def _tags(self):
        return [e[0] for e in self.stack]

    def _visible(self):
        tags = self._tags()
        if "body" not in tags or any(e[1] for e in self.stack):
            return False
        for e in reversed(self.stack):
            if e[2] is not None:
                return e[2] == "visible"
        return True

    def _in_main(self):
        tags = self._tags()
        return "body" in tags and "main" in tags[tags.index("body"):]

    def _in_key_scope(self):
        tags = self._tags()
        if "body" not in tags:
            return False
        after = tags[tags.index("body"):]
        return any(t in ("main", "header", "footer") for t in after)

    def _newline(self):
        for buf in (self._raw, self._stripped, self._md, self._key):
            buf.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK:
            self._newline()
        if tag in VOID:
            return
        removed, vis = element_visibility(tag, attrs)
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "main" and "body" in self._tags() and not any(t in ("template", "noscript") for t in self._tags()):
            self.main_count += 1   # <main> inside <template>/<noscript> is not rendered and ignored
        is_lang = tag == "span" and "lang" in a.get("class", "").split()
        self.stack.append((tag, removed, vis, is_lang))
        if tag == "a" and a.get("href") and any(e[3] for e in self.stack) and self._visible():
            self.lang_links.append(a["href"])
        if tag == "a" and a.get("href") and self._visible() and self._in_key_scope():
            self.key_links.append(a["href"])

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK:
            self._newline()

    def handle_endtag(self, tag):
        if tag in BLOCK:
            self._newline()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, d):
        if not self._visible():
            return
        tags = set(self._tags())
        if not tags & {"code", "pre"}:
            self._md.append(d)
        if self._in_key_scope():
            self._key.append(d)
        if self._in_main():
            self._raw.append(d)
            if not tags & self.strip:
                self._stripped.append(d)

    def main_raw(self):
        return "".join(self._raw)

    def main_stripped(self):
        return "".join(self._stripped)

    def key_text(self):
        return "".join(self._key)

    def body_visible(self):
        return "".join(self._md)

    def text(self):
        return "".join(c for c in self.main_raw() if is_counted_char(c))


def parse_visible(html, lang="zh"):
    v = VisibleText(lang)
    v.feed(html)
    v.close()
    return v


def visible_info(html):
    """Return (main_count, text): text = visible counted letters/digits inside <main>."""
    v = parse_visible(html)
    return v.main_count, v.text()


def visible_text(html):
    return visible_info(html)[1]


def is_home_url(base, url, lang):
    """True only for the exact home page of `lang` under `base`:
    same scheme+host as base, path == base path + '/' (zh) or + '/en/' (en),
    no query, no fragment. Returns (ok, reason)."""
    b, u = urlparse(base), urlparse(url)
    if (u.scheme, u.netloc.lower()) != (b.scheme, b.netloc.lower()):
        return False, "scheme/host %s://%s != base %s://%s" % (u.scheme, u.netloc, b.scheme, b.netloc)
    if u.query or "?" in url:
        return False, "has query string"
    if u.fragment or "#" in url:
        return False, "has fragment"
    root = b.path.rstrip("/")
    want = {"zh": root + "/", "en": root + "/en/"}.get(lang)
    if want is None:
        return False, "unknown lang %r" % lang
    if u.path != want:
        return False, "path %s != %s (lang %s)" % (u.path, want, lang)
    return True, "home"


class _Paras(HTMLParser):
    """Text of each <p> inside <article> (or <main> when there is no <article>), ignoring
    <template>/<noscript>/<script>/<style> and hidden elements."""
    INERT = {"template", "noscript", "script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras = {"article": [], "main": []}
        self.depth = {"article": 0, "main": 0}
        self.inert = 0
        self.cur = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        hidden = "hidden" in a or a.get("aria-hidden") == "true" or "display:none" in a.get("style", "").replace(" ", "")
        self.stack.append((tag, hidden))
        if tag in self.INERT or hidden:
            self.inert += 1
        if tag in self.depth:
            self.depth[tag] += 1
        if tag == "p" and not self.inert:
            self.cur = []

    def handle_endtag(self, tag):
        while self.stack:
            t, hidden = self.stack.pop()
            if t in self.INERT or hidden:
                self.inert -= 1
            if t == "p" and self.cur is not None:
                txt = " ".join("".join(self.cur).split())
                for k in self.depth:
                    if self.depth[k]:
                        self.paras[k].append(txt)
                self.cur = None
            if t in self.depth:
                self.depth[t] -= 1
            if t == tag:
                break

    def handle_data(self, data):
        if self.cur is not None and not self.inert:
            self.cur.append(data)


def last_body_paragraph(html):
    """Last non-empty paragraph of the article body (whitespace-collapsed), or None."""
    p = _Paras()
    p.feed(html)
    p.close()
    paras = [t for t in (p.paras["article"] or p.paras["main"]) if t]
    return paras[-1] if paras else None


def page_type_for(name):
    """Page type of a discovered entry; both daily entries ("latest daily", "due daily") are type daily,
    so the 800-letter daily sample floor and the disclaimer check apply to them."""
    if name in ("due daily", "latest daily"):
        return "daily"
    return name.split()[-1] if name.startswith("latest") else name.split()[0]


def check_page(base, lang, path, link_cache, page_type="daily"):
    url = site_url(base, path)
    res = {"lang": lang, "url": url, "checks": {}, "external_non200": [], "pass": True, "review": False}

    def rec(name, ok, detail=""):
        res["checks"][name] = {"ok": ok, "detail": detail}
        if not ok:
            res["pass"] = False

    st, body = fetch(url)
    rec("status_200", st == 200, "HTTP %s" % st)
    if st != 200:
        return res
    if not body or not body.strip():
        rec("visible_text", False, "HTTP 200 but empty response body")
        return res
    p = Page()
    p.feed(body)
    vt = parse_visible(body, lang)
    vis_len = len(vt.text())
    if vt.main_count == 0:
        rec("visible_text", False, "no <main> element in <body> (page template lacks <main>?)")
    elif vt.main_count > 1:
        rec("visible_text", False, "%d <main> elements in <body>; exactly one is required" % vt.main_count)
    else:
        rec("visible_text", vis_len > 0, "%d rendered letters/digits (Unicode L*/N*, blank fillers excluded) in <main>" % vis_len
            if vis_len else "HTTP 200 but no visible text in <main>")
    hl = (p.html_lang or "")
    rec("html_lang", hl.lower().split("-")[0] == lang, "lang=%r" % hl)
    if page_type in DISCLAIMER_TYPES:
        last = last_body_paragraph(body)
        rec("disclaimer", last == DISCLAIMER[lang],
            "last paragraph is the fixed disclaimer" if last == DISCLAIMER[lang]
            else "last paragraph must be exactly %r, got %r" % (DISCLAIMER[lang], (last or "")[:80]))

    # final URL (non-home pages must not be redirected elsewhere; home is checked below)
    final = _final.get(url, url)
    res["final_url"] = final
    if page_type != "home":
        rec("final_url", norm_url(final) == norm_url(url),
            "no redirect" if final == url else "requested %s, final %s" % (url, final))

    # language switch: compare full URLs (scheme, host, base subpath, path, query)
    other = "en" if lang == "zh" else "zh"
    sp = site_path(base, url) or path
    cand_url = site_url(base, other_lang_path(sp))
    cst, _ = fetch(cand_url, want_body=False)
    cand_ok = cst == 200 and norm_url(_final.get(cand_url, cand_url)) == norm_url(cand_url)
    expected = norm_url(cand_url if cand_ok else site_url(base, "/en/" if other == "en" else "/"))
    got = [norm_url(urljoin(url, h)) for h in vt.lang_links]   # visible switch links only
    rec("lang_switch", bool(got) and all(g == expected for g in got),
        "expected %s (%s); visible switch links: %s" % (
            expected, "translation" if cand_ok else "no translation -> home", got or "none"))

    # language of body text
    info = body_language_ratio(body, lang)
    status, detail = judge_language(info, lang, page_type)
    if page_type == "home":
        ok_home, why = is_home_url(base, final, lang)
        if ok_home and (p.html_lang or "").lower().split("-")[0] != lang:
            ok_home, why = False, "html lang %r does not match %s home path" % (p.html_lang, lang)
        if final != url:
            why += " (final URL after redirects: %s)" % final
        if ok_home:
            status = "ok"
            detail = ("not checked: home page exemption (for information only: CJK ratio %.2f over %d letters)"
                      % (info["raw_ratio"], info["raw_letters"]))
        else:
            status = "fail"
            detail = "page_type=home rejected (%s); " % why + detail
    res["language"] = info
    rec("body_language", status == "ok", detail)
    if status == "review":
        res["checks"]["body_language"]["review"] = True
        res["review"] = True

    # markdown rendered
    vis = vt.body_visible()   # visible <body> text outside code/pre
    probs = []
    for tok in ("**", "__"):
        i = vis.find(tok)
        if i >= 0:
            probs.append("%r near: %r" % (tok, vis[max(0, i - 30):i + 30].strip()))
    for line in vis.splitlines():
        if re.match(r"^\s*#{1,6}\s+\S", line):
            probs.append("raw heading: %r" % line.strip()[:60])
            break
    rec("markdown_rendered", not probs, "; ".join(probs) or "no leftover ** / __ / # headings")
    if p.tables:
        styled = all(c for c in p.tables) or re.search(r"(^|[}\s,])table\s*[{,]", p.css)
        rec("table_styled", bool(styled), "%d table(s); %s" % (
            len(p.tables), "styled" if styled else "no table class and no CSS rule for table"))
    else:
        rec("table_styled", True, "no tables")

    # links and assets
    host = urlparse(base).netloc.lower()
    bad = []
    redirects = []
    n_int = 0
    for kind, href in p.links:
        if href.startswith(("mailto:", "javascript:", "tel:", "#", "data:")):
            continue
        full = urldefrag(urljoin(url, href))[0]
        pu = urlparse(full)
        if pu.scheme not in ("http", "https"):
            continue
        if pu.netloc.lower() == host:
            n_int += 1
            if retired_hit(site_path(base, full)):
                bad.append("%s %s links to a retired (taken-down) path" % (kind, full))
                continue
            if full not in link_cache:
                link_cache[full] = fetch(full, want_body=False)[0]
            lfinal = _final.get(full, full)
            if link_cache[full] != 200:
                bad.append("%s %s -> %s" % (kind, full, link_cache[full]))
            elif urlparse(lfinal).netloc.lower() != host:
                bad.append("%s %s redirects off-site to %s" % (kind, full, lfinal))
            elif norm_url(lfinal) != norm_url(full):
                redirects.append("%s %s -> %s" % (kind, full, lfinal))
        else:
            if full not in link_cache:
                link_cache[full] = fetch(full, want_body=False, retries=1)[0]
            if link_cache[full] != 200:
                res["external_non200"].append("%s %s -> %s" % (kind, full, link_cache[full] or "error"))
    rec("internal_links", not bad, "; ".join(bad) or "%d internal link(s)/asset(s) OK" % n_int)
    res["internal_redirects"] = redirects   # same-site redirects: reported, not a failure
    return res



# ---- zh/en pair consistency (key information must match) ----
PAIR_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke_pairs.json")
TIME_RE = re.compile(r"(?<![\d:：])([01]?\d|2[0-3])[:：]([0-5]\d)(?![\d:：])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class PairConfigError(Exception):
    pass


# ---- floors fixed in code: a config below any floor is a CONFIG ERROR (FAIL) ----
REQUIRED_PHRASE_PAGES = ("home", "about")
MIN_PHRASES = {"home": 2, "about": 2}                   # minimum number of phrase items per page
REQUIRED_EVENT_PAGES = ()   # about no longer lists times (one-line page since 2026-10-12)
REQUIRED_EVENTS = {}
REQUIRED_PROFILE_HOSTS = ("x.com", "github.com")
FLOOR_SITEMAPS = ("/sitemap.xml", "/zh/sitemap.xml", "/en/sitemap.xml")
FLOOR_MIN_PAGES = {"daily": 1}
FLOOR_DAILY_EFFECTIVE_EARLIEST = "2026-10-12T07:00"   # SGT; first publication -- the daily rule never starts earlier
CAP_DAILY_EFFECTIVE_LATEST = "2026-10-19T07:00"       # SGT; nor can it be postponed past one week after that
DISCLAIMER = {"zh": "本文不含投资建议。", "en": "This article does not constitute investment advice."}
DISCLAIMER_TYPES = ("daily", "macro", "cards")
FLOOR_RETIRED_PREFIXES = ("/posts/tongyi/", "/framework/", "/posts/daily/2026-10-10/", "/posts/daily/2026-10-11/")
FLOOR_RETIRED_PATHS = ("/posts/tongyi/", "/framework/macro/", "/en/framework/macro/",
                       "/posts/daily/2026-10-10/", "/posts/daily/2026-10-11/",
                       "/en/posts/daily/2026-10-10/", "/en/posts/daily/2026-10-11/")
TIME_GROUP = r"(?P<T>(?:[01]?\d|2[0-3])[:：][0-5]\d)"


def phrase_long_enough(text):
    """Minimum length for a required phrase: >= 4 CJK characters if it contains CJK, else >= 8 letters."""
    t = re.sub(r"\s+", "", text or "")
    cjk = sum(1 for c in t if _is_cjk(c))
    if cjk:
        return cjk >= 4
    return sum(1 for c in t if c.isalpha()) >= 8


def phrase_pairs(item):
    """Normalized list of (zh, en) pairs for a required-phrase item."""
    if "pairs" in item:
        return [tuple(p) for p in item["pairs"]]
    return [(item["zh"], item["en"])]


def load_pair_config(path=None):
    """Load and validate the pair config; raises PairConfigError with a clear message."""
    path = path or PAIR_CONFIG
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except OSError as e:
        raise PairConfigError("cannot read pair config %s: %s" % (path, e))
    except ValueError as e:
        raise PairConfigError("pair config %s is not valid JSON: %s" % (path, e))
    if not isinstance(cfg, dict):
        raise PairConfigError("pair config %s: top level must be an object" % path)
    hosts = cfg.get("profile_hosts")
    if not (isinstance(hosts, list) and hosts and all(isinstance(h, str) and h.strip() for h in hosts)):
        raise PairConfigError("pair config %s: profile_hosts must be a non-empty list of host names" % path)
    missing_hosts = [h for h in REQUIRED_PROFILE_HOSTS if h not in [x.strip().lower() for x in hosts]]
    if missing_hosts:
        raise PairConfigError("pair config %s: profile_hosts is below the floor, missing %s" % (path, missing_hosts))
    rp = cfg.get("required_phrases")
    if not isinstance(rp, dict):
        raise PairConfigError("pair config %s: required_phrases must be an object" % path)
    for page in REQUIRED_PHRASE_PAGES:
        if not rp.get(page):
            raise PairConfigError("pair config %s: required_phrases[%r] must be a non-empty list" % (path, page))
    for page, n in MIN_PHRASES.items():
        if isinstance(rp.get(page), list) and len(rp[page]) < n:
            raise PairConfigError("pair config %s: required_phrases[%r] has %d item(s), below the floor of %d"
                                  % (path, page, len(rp[page]), n))
    for page, items in rp.items():
        if not isinstance(items, list) or not items:
            raise PairConfigError("pair config %s: required_phrases[%r] must be a non-empty list" % (path, page))
        for i, it in enumerate(items):
            where = "required_phrases[%r][%d]" % (page, i)
            if not isinstance(it, dict):
                raise PairConfigError("pair config %s: %s must be an object" % (path, where))
            if "pairs" in it and ("zh" in it or "en" in it):
                raise PairConfigError("pair config %s: %s has both 'pairs' and 'zh'/'en'; use one form" % (path, where))
            if "pairs" in it:
                pairs = it["pairs"]
                if not (isinstance(pairs, list) and pairs and all(
                        isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p) for p in pairs)):
                    raise PairConfigError("pair config %s: %s.pairs must be a non-empty list of [zh, en] pairs" % (path, where))
            elif isinstance(it.get("zh"), str) and isinstance(it.get("en"), str):
                pairs = [[it["zh"], it["en"]]]
            else:
                raise PairConfigError("pair config %s: %s needs string 'zh' and 'en', or 'pairs': [[zh, en], ...] "
                                      "(variants are registered as zh/en pairs)" % (path, where))
            for zh, en in pairs:
                for lang, x in (("zh", zh), ("en", en)):
                    if not phrase_long_enough(x):
                        raise PairConfigError("pair config %s: %s %s phrase %r is too short (need >= 4 CJK "
                                              "characters or >= 8 letters)" % (path, where, lang, x))
    ev = cfg.get("event_times")
    if not isinstance(ev, dict):
        raise PairConfigError("pair config %s: event_times must be an object" % path)
    for page in REQUIRED_EVENT_PAGES:
        if not ev.get(page):
            raise PairConfigError("pair config %s: event_times[%r] must be a non-empty list" % (path, page))
    for page, names in REQUIRED_EVENTS.items():
        have = {it.get("event") for it in ev.get(page, []) if isinstance(it, dict)}
        lacking = [n for n in names if n not in have]
        if lacking:
            raise PairConfigError("pair config %s: event_times[%r] is below the floor, missing event(s) %s"
                                  % (path, page, lacking))
    for page, items in ev.items():
        if not isinstance(items, list) or not items:
            raise PairConfigError("pair config %s: event_times[%r] must be a non-empty list" % (path, page))
        for i, it in enumerate(items):
            where = "event_times[%r][%d]" % (page, i)
            if not (isinstance(it, dict) and isinstance(it.get("event"), str) and it["event"].strip()):
                raise PairConfigError("pair config %s: %s needs a non-empty 'event' name" % (path, where))
            for lang in ("zh", "en"):
                pats = it.get(lang)
                pats = [pats] if isinstance(pats, str) else pats
                if not (isinstance(pats, list) and pats and all(isinstance(x, str) and x.count("{T}") == 1 for x in pats)):
                    raise PairConfigError("pair config %s: %s.%s must be a pattern (or list) containing {T} exactly once"
                                          % (path, where, lang))
                for x in pats:
                    try:
                        rx = re.compile(x.replace("{T}", TIME_GROUP))
                    except re.error as e:
                        raise PairConfigError("pair config %s: %s.%s pattern %r is not a valid regex: %s" % (path, where, lang, x, e))
                    if rx.groups != 1 or list(rx.groupindex) != ["T"]:
                        raise PairConfigError("pair config %s: %s.%s pattern %r has capture groups besides {T}; "
                                              "use non-capturing (?:...) groups" % (path, where, lang, x))
    return cfg


def event_time(text, patterns, lang):
    """Time (HH:MM) attached to an event label: first match of any pattern, {T} = the time."""
    t = re.sub(r"\s+", " ", text)
    for pat in ([patterns] if isinstance(patterns, str) else patterns):
        try:
            m = re.search(pat.replace("{T}", TIME_GROUP), t, re.I if lang == "en" else 0)
            if m:
                h, mm = re.split(r"[:：]", m.group("T"))
                return "%02d:%s" % (int(h), mm)
        except (re.error, IndexError, ValueError):
            continue      # unusable pattern (normally rejected by load_pair_config): no match
    return None


def norm_profile(href, page_url):
    """Normalized profile URL for comparison: resolved against the page URL (so //x.com/a works),
    host lowercased with 'www.' removed; the default port of the ORIGINAL scheme dropped (http:80,
    https:443) and only then http folded to https (http and https are the same profile). Any other
    port (incl. https:80, http:443) keeps scheme and port, so it is a different link. Trailing slash
    and fragment dropped; query kept."""
    full = urldefrag(urljoin(page_url, href.strip()))[0]
    u = urlparse(full)
    if u.scheme.lower() not in ("http", "https"):
        return None
    scheme = u.scheme.lower()
    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    try:
        port = u.port
    except ValueError:
        return None
    # drop only the default port of the ORIGINAL scheme (http:80, https:443), before folding http -> https
    if port == {"http": 80, "https": 443}[scheme]:
        port = None
    netloc = host if port is None else "%s:%d" % (host, port)
    # http and https are folded together only for default-port links; a link with any other port keeps
    # its original scheme, so https://x.com:80/a and http://x.com:443/a never match https://x.com/a
    path = u.path.rstrip("/")
    out_scheme = "https" if port is None else scheme
    return "%s://%s%s%s" % (out_scheme, netloc, path, "?" + u.query if u.query else ""), host, path


def mailto_addresses(href):
    """Lowercased addresses from a mailto: link (percent-decoded, comma-separated, query dropped)."""
    from urllib.parse import unquote
    if not href.strip().lower().startswith("mailto:"):
        return set()
    body = unquote(href.strip()[7:].split("?")[0])   # percent-decode first, then split on commas
    return {a.strip().lower() for a in body.split(",") if a.strip()}


def key_info(html, lang, profile_hosts, page_url="https://example.invalid/"):
    """Times (HH:MM), emails (text and mailto:), external profile URLs and phrase text, taken only
    from VISIBLE text and links inside <main>, <header> and <footer> (same parser and visibility
    rules as visible_text; hidden elements never count)."""
    v = parse_visible(html or "", lang)
    text = v.key_text()
    seq = []
    for h, mm in TIME_RE.findall(text):
        t = "%02d:%s" % (int(h), mm)
        if t not in seq:
            seq.append(t)      # order of first appearance
    times = set(seq)
    hrefs = [h.strip() for h in v.key_links]
    emails = {e.lower() for e in EMAIL_RE.findall(text)}
    for h in hrefs:
        emails |= mailto_addresses(h)
    hosts = {h.lower() for h in profile_hosts}
    profiles = set()
    for h in hrefs:
        n = norm_profile(h, page_url)
        if not n:
            continue
        url, host, path = n
        depth = len([x for x in path.split("/") if x])   # profile = host root or one path segment (x.com/name)
        if depth <= 1 and any(host == x or host.endswith("." + x) for x in hosts):
            profiles.add(url)
    return {"times": times, "time_seq": seq, "emails": emails, "profiles": profiles, "text": text}


def compare_pair(name, zh_html, en_html, cfg, zh_url="https://example.invalid/", en_url="https://example.invalid/en/"):
    """Return dict of check -> {ok, detail}; every mismatch is a FAIL."""
    hosts = cfg.get("profile_hosts", [])
    z, e = key_info(zh_html, "zh", hosts, zh_url), key_info(en_html, "en", hosts, en_url)
    out = {}
    for k, label in (("times", "schedule times"), ("emails", "emails"), ("profiles", "external profile URLs")):
        only_z, only_e = sorted(z[k] - e[k]), sorted(e[k] - z[k])
        ok = not only_z and not only_e
        out["pair_" + k] = {"ok": ok, "detail": ("%s match: %s" % (label, sorted(z[k]) or "none")) if ok else
                            "%s differ: zh only %s; en only %s" % (label, only_z, only_e)}
    # per-event times: the time next to each configured label must be equal on both pages
    ev_bad, ev_ok = [], []
    for item in cfg.get("event_times", {}).get(name, []):
        zt, et = event_time(z["text"], item["zh"], "zh"), event_time(e["text"], item["en"], "en")
        if zt is None or et is None or zt != et:
            ev_bad.append("%s: zh %s, en %s" % (item["event"], zt or "missing", et or "missing"))
        else:
            ev_ok.append("%s %s" % (item["event"], zt))
    out["pair_event_times"] = {"ok": not ev_bad, "detail": ("event times match: %s" % (ev_ok or "none configured"))
                               if not ev_bad else "event times differ: " + "; ".join(ev_bad)}
    missing = []
    ztext = re.sub(r"\s+", "", z["text"])
    etext = re.sub(r"\s+", " ", e["text"]).lower()
    for item in cfg.get("required_phrases", {}).get(name, []):
        pairs = phrase_pairs(item)
        hit = any(re.sub(r"\s+", "", zp) in ztext and re.sub(r"\s+", " ", ep).lower() in etext for zp, ep in pairs)
        if not hit:
            zhits = [zp for zp, _ in pairs if re.sub(r"\s+", "", zp) in ztext]
            ehits = [ep for _, ep in pairs if re.sub(r"\s+", " ", ep).lower() in etext]
            if not zhits:
                missing.append("zh lacks %r" % (pairs[0][0] if len(pairs) == 1 else [p[0] for p in pairs]))
            if not ehits:
                missing.append("en lacks %r" % (pairs[0][1] if len(pairs) == 1 else [p[1] for p in pairs]))
            if zhits and ehits:
                missing.append("zh %r and en %r are not a registered pair" % (zhits[0], ehits[0]))
    n = len(cfg.get("required_phrases", {}).get(name, []))
    out["pair_phrases"] = {"ok": not missing, "detail": ("%d required phrase pair(s) present" % n) if not missing
                           else "; ".join(missing)}
    return out


def deploy_sha(arg=""):
    """Return (sha, source): --deploy-sha, else workflow_run.head_sha from the GitHub event file."""
    if arg.strip():
        return arg.strip(), "--deploy-sha"
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                ev = json.load(f)
            h = (ev.get("workflow_run") or {}).get("head_sha")
            if h:
                return h, "workflow_run.head_sha"
        except (OSError, ValueError):
            pass
    return None, "unknown (no --deploy-sha and no workflow_run event)"


def result_label(r):
    """PASS, FAIL, REVIEW (only REVIEW items failed) or FAIL+REVIEW (both)."""
    if r["pass"]:
        return "PASS"
    hard = any(not v["ok"] and not v.get("review") for v in r["checks"].values())
    if r.get("review"):
        return "FAIL+REVIEW" if hard else "REVIEW"
    return "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://markjin-lab.github.io/")
    ap.add_argument("--json-out")
    ap.add_argument("--discovery-config", help="discovery config (default scripts/smoke_discovery.json)")
    ap.add_argument("--deploy-sha", default="", help="commit SHA of the deploy being checked "
                    "(default: workflow_run.head_sha from $GITHUB_EVENT_PATH)")
    ap.add_argument("--pair-config", default=PAIR_CONFIG, help="JSON config for zh/en key-information checks")
    a = ap.parse_args()
    base = a.base.rstrip("/") + "/"
    sha, src = deploy_sha(a.deploy_sha)
    report = {"base": base, "deploy_sha": sha, "deploy_sha_source": src, "pages": [], "pass": True}
    try:
        pair_cfg, cfg_error = load_pair_config(a.pair_config), None
    except PairConfigError as e:
        pair_cfg, cfg_error = None, str(e)
        report["pass"] = False
        report["pair_config_error"] = cfg_error
    try:
        dcfg, dcfg_error = load_discovery_config(a.discovery_config), None
    except PairConfigError as e:
        dcfg, dcfg_error = DEFAULT_DISCOVERY, str(e)
        report["pass"] = False
        report["discovery_config_error"] = dcfg_error
    link_cache = {}
    discover.sources = []
    pages_found = discover(base, dcfg)
    report["discovery_sources"] = list(discover.sources)
    report["retired_404_ok"] = list(getattr(discover, "retired_ok", []))
    report["daily_rule"] = getattr(discover, "daily_rule", "")
    for name, zh, en, notes in pages_found:
        entry = {"name": name, "notes": list(notes), "results": []}
        if zh is None and en is None:
            report["pass"] = False
            report["pages"].append(entry)
            continue
        for lang, path in (("zh", zh), ("en", en)):
            if path is None:
                if not (lang == "en" and notes):
                    entry["notes"].append("%s version not found" % lang)
                    report["pass"] = False
                    entry["results"].append({"lang": lang, "url": None, "pass": False,
                                             "checks": {"discover": {"ok": False, "detail": "page not found"}},
                                             "external_non200": []})
                continue
            ptype = page_type_for(name)
            r = check_page(base, lang, path, link_cache, ptype)
            r["label"] = result_label(r)
            entry["results"].append(r)
            report["pass"] &= r["pass"]
        if zh is not None and en is not None:
            zs, zb = fetch(site_url(base, zh))
            es, eb = fetch(site_url(base, en))
            if cfg_error:
                pc = {"pair_config": {"ok": False, "detail": "pair checks not run: " + cfg_error}}
            elif zs == 200 and es == 200 and zb and zb.strip() and eb and eb.strip():
                pc = compare_pair(name, zb, eb, pair_cfg, site_url(base, zh), site_url(base, en))
            else:
                pc = {"pair_not_run": {"ok": False, "detail": "pair checks not run: zh HTTP %s%s, en HTTP %s%s" % (
                    zs, "" if zb and zb.strip() else " (empty body)", es, "" if eb and eb.strip() else " (empty body)")}}
            if True:
                ok = all(v["ok"] for v in pc.values())
                entry["results"].append({"lang": "zh+en", "url": "%s <-> %s" % (zh, en), "checks": pc,
                                         "external_non200": [], "pass": ok, "review": False,
                                         "label": "PASS" if ok else "FAIL"})
                report["pass"] &= ok
        report["pages"].append(entry)

    print("deploy SHA: %s (%s)" % (sha or "unknown", src))
    if cfg_error:
        print("PAIR CONFIG ERROR: %s" % cfg_error)
    if dcfg_error:
        print("DISCOVERY CONFIG ERROR: %s (built-in defaults used)" % dcfg_error)
    print("daily rule: %s" % report["daily_rule"])
    print("retired paths answering 404: %s" % (", ".join(report["retired_404_ok"]) or "none"))
    print("discovery sources:")
    for d in report["discovery_sources"]:
        print("   - %s" % format_source(d))
    for e in report["pages"]:
        print("== %s" % e["name"])
        for n in e["notes"]:
            print("   note: %s" % n)
        for r in e["results"]:
            st = result_label(r)
            print("  [%s] %s %s" % (r["lang"], st, r["url"]))
            for k, v in r["checks"].items():
                print("     %-18s %s  %s" % (k, "ok " if v["ok"] else ("REV" if v.get("review") else "BAD"), v["detail"]))
            for x in r["external_non200"]:
                print("     external (warn)    %s" % x)
            for x in r.get("internal_redirects", []):
                print("     redirect (warn)    %s" % x)
    print("\nOVERALL: %s" % ("PASS" if report["pass"] else "FAIL"))
    js = json.dumps(report, ensure_ascii=False, indent=2)
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            f.write(js)
    else:
        print(js)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
