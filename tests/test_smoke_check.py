import pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import smoke_check as sc

FX = ROOT / "tests" / "fixtures"


def page(main, lang="zh-CN"):
    return "<html lang=%s><body><main>%s</main></body></html>" % (lang, main)


class BodyLanguage(unittest.TestCase):
    def test_zh_daily_healthy(self):
        i = sc.body_language_ratio((FX / "sample-daily.zh.html").read_text("utf-8"), "zh")
        self.assertGreaterEqual(i["ratio"], 0.6)
        self.assertGreaterEqual(i["raw_ratio"], 0.3)
        self.assertEqual(sc.judge_language(i, "zh", "daily")[0], "ok")

    def test_en_daily_passes(self):
        i = sc.body_language_ratio((FX / "sample-daily.en.html").read_text("utf-8"), "en")
        self.assertLessEqual(i["ratio"], 0.05)
        self.assertEqual(sc.judge_language(i, "en", "daily")[0], "ok")

    def test_english_page_under_zh_path_with_disclaimer_fails(self):
        en = (FX / "sample-daily.en.html").read_text("utf-8")
        html = en.replace("</main>", "<p>本文不含投资建议。</p></main>")
        i = sc.body_language_ratio(html, "zh")
        self.assertEqual(sc.judge_language(i, "zh", "daily")[0], "fail")

    def test_short_english_with_disclaimer_fails(self):
        html = page("<p>This is an English paragraph about markets and models today.</p>"
                    "<blockquote><p>A quoted English line.</p></blockquote><p>本文不含投资建议。</p>")
        i = sc.body_language_ratio(html, "zh")
        self.assertEqual(sc.judge_language(i, "zh", "home")[0], "fail")

    def test_only_source_line_before_translation_is_stripped(self):
        html = page("<p>The model is accurate but not humble.</p><p>译文：模型准确但不谦逊。</p>"
                    "<p>An unrelated English line stays.</p>")
        i = sc.body_language_ratio(html, "zh")
        self.assertLess(i["letters"], i["raw_letters"])
        self.assertGreater(i["letters"], len("模型准确但不谦逊"))  # unrelated line kept

    def test_strip_cap(self):
        html = page("<pre><code>" + "x" * 500 + "</code></pre><p>中文正文。</p>")
        i = sc.body_language_ratio(html, "zh")
        self.assertGreater(i["stripped_frac"], sc.MAX_STRIP_FRAC)
        self.assertEqual(sc.judge_language(i, "zh", "home")[0], "fail")

    def test_small_sample_is_review(self):
        i = sc.body_language_ratio(page("<p>这是一段很短的中文。</p>"), "zh")
        st, d = sc.judge_language(i, "zh", "daily")
        self.assertEqual(st, "review")
        self.assertIn("sample too small", d)

    def test_empty_after_stripping_fails(self):
        html = page("<pre><code>code()</code></pre><p><a href='/x/'>链接文字</a></p>")
        i = sc.body_language_ratio(html, "zh")
        self.assertEqual(i["letters"], 0)
        self.assertEqual(sc.judge_language(i, "zh", "home")[0], "fail")

    def test_home_skips_language_checks(self):
        from unittest import mock
        html = "<html lang=zh-CN><body><span class=lang><a href='/en/'>EN</a></span><main><p>Hi</p></main></body></html>"
        def fake(url, want_body=True, retries=2):
            return (200, html) if url.endswith("example.test/") else (200, None)
        with mock.patch.object(sc, "fetch", fake):
            home = sc.check_page("https://example.test/", "zh", "/", {}, "home")
            daily = sc.check_page("https://example.test/", "zh", "/", {}, "daily")
        self.assertTrue(home["checks"]["body_language"]["ok"])
        self.assertTrue(home["pass"])
        self.assertFalse(daily["checks"]["body_language"]["ok"])
        self.assertNotIn("home", sc.MIN_LETTERS)

    def test_home_type_on_other_path_fails(self):
        from unittest import mock
        html = "<html lang=zh-CN><body><span class=lang><a href='/en/posts/x/'>EN</a></span><main><p>Hi</p></main></body></html>"
        def fake(url, want_body=True, retries=2):
            return (200, html) if url.endswith("/posts/x/") else (200, None)
        with mock.patch.object(sc, "fetch", fake):
            r = sc.check_page("https://example.test/", "zh", "/posts/x/", {}, "home")
        self.assertFalse(r["checks"]["body_language"]["ok"])
        self.assertFalse(r["pass"])


class HomeUrl(unittest.TestCase):
    B = "https://markjin-lab.github.io/"

    def bad(self, url, lang, base=None):
        self.assertFalse(sc.is_home_url(base or self.B, url, lang)[0], url)

    def test_real_home_pages(self):
        self.assertTrue(sc.is_home_url(self.B, self.B, "zh")[0])
        self.assertTrue(sc.is_home_url(self.B, self.B + "en/", "en")[0])

    def test_off_site(self):
        self.bad("https://evil.example/", "zh")
        self.bad("http://markjin-lab.github.io/", "zh")

    def test_query(self):
        self.bad(self.B + "?x=1", "zh")
        self.bad(self.B + "en/?", "en")

    def test_fragment(self):
        self.bad(self.B + "#top", "zh")
        self.bad(self.B + "en/#", "en")

    def test_zh_with_en_path(self):
        self.bad(self.B + "en/", "zh")

    def test_en_with_root_path(self):
        self.bad(self.B, "en")

    def test_other_path(self):
        self.bad(self.B + "posts/x/", "zh")

    def test_base_with_subpath(self):
        b = "https://example.test/site/"
        self.assertTrue(sc.is_home_url(b, "https://example.test/site/", "zh")[0])
        self.assertTrue(sc.is_home_url(b, "https://example.test/site/en/", "en")[0])
        self.bad("https://example.test/", "zh", b)
        self.bad("https://example.test/en/", "en", b)

    def test_check_page_subpath_home_passes(self):
        from unittest import mock
        html = "<html lang=zh-CN><body><span class=lang><a href='/site/en/'>EN</a></span><main><p>Hi</p></main></body></html>"
        def fake(url, want_body=True, retries=2):
            return (200, html) if url == "https://example.test/site/" else (200, None)
        with mock.patch.object(sc, "fetch", fake):
            r = sc.check_page("https://example.test/site/", "zh", "/", {}, "home")
        self.assertTrue(r["checks"]["body_language"]["ok"], r["checks"]["body_language"])


class EmptyBody(unittest.TestCase):
    def run_page(self, body, path, page_type):
        from unittest import mock
        def fake(url, want_body=True, retries=2):
            return (200, body)
        with mock.patch.object(sc, "fetch", fake):
            return sc.check_page("https://example.test/", "zh", path, {}, page_type)

    def test_empty_body_fails(self):
        for body in ("", "   \n"):
            r = self.run_page(body, "/posts/daily/x/", "daily")
            self.assertFalse(r["pass"])
            self.assertFalse(r["checks"]["visible_text"]["ok"])

    def test_empty_body_home_fails(self):
        r = self.run_page("", "/", "home")
        self.assertFalse(r["pass"])

    def test_no_visible_text_home_fails(self):
        html = "<html lang=zh-CN><head><title></title></head><body><main></main></body></html>"
        r = self.run_page(html, "/", "home")
        self.assertFalse(r["checks"]["visible_text"]["ok"])
        self.assertFalse(r["pass"])


class VisibleTextTests(unittest.TestCase):
    def v(self, body, head=""):
        return sc.visible_text("<html><head>%s</head><body><main>%s</main></body></html>" % (head, body))

    def test_plain(self):
        self.assertEqual(self.v("<p>hi there</p>"), "hithere")

    def test_title_and_head_excluded(self):
        self.assertEqual(self.v("", "<title>T</title><meta name=x content=y>"), "")
        self.assertEqual(sc.visible_text("<title>Only title</title>"), "")

    def test_script_style_template_noscript_excluded(self):
        for t in ("script", "style", "template", "noscript"):
            self.assertEqual(self.v("<%s>x y</%s>" % (t, t)), "", t)

    def test_hidden_attribute_with_descendants(self):
        self.assertEqual(self.v("<div hidden><p>a<span>b</span></p></div>"), "")

    def test_aria_hidden(self):
        self.assertEqual(self.v('<div aria-hidden="true"><p>a</p></div>'), "")
        self.assertEqual(self.v('<div aria-hidden="false">a</div>'), "a")

    def test_display_none(self):
        self.assertEqual(self.v('<div style="color:red; display : none"><p>a</p></div>'), "")

    def test_visibility_hidden(self):
        self.assertEqual(self.v('<div style="visibility:hidden"><b>a</b></div>'), "")

    def test_void_hidden_does_not_leak(self):
        self.assertEqual(self.v('<p><img hidden src=x>after</p>'), "after")

    def test_zero_width_and_whitespace(self):
        self.assertEqual(self.v("<p>\u200b\u200c\u200d\u2060\ufeff \n\t&nbsp;</p>"), "")

    def test_only_letters_and_digits_count(self):
        self.assertEqual(self.v("<p>a1 中文，！ ２</p>"), "a1中文２")

    def test_invisible_format_chars_only_fail(self):
        from unittest import mock
        for body in ("&lrm;", "\u200e", "\u200f", "&rlm;", "\u2060", "\ufeff", "\u200e\u200f\u2060\ufeff",
                     "— … · ！？ ©®™ → ★ | - _ . ,", "&lrm;&nbsp;…&rlm;"):
            html = "<html lang=zh-CN><body><main><p>%s</p></main></body></html>" % body
            self.assertEqual(sc.visible_text(html), "", repr(body))
            with mock.patch.object(sc, "fetch", lambda url, want_body=True, retries=2: (200, html)):
                r = sc.check_page("https://example.test/", "zh", "/", {}, "home")
            self.assertFalse(r["checks"]["visible_text"]["ok"], repr(body))
            self.assertFalse(r["pass"], repr(body))

    def test_page_with_only_invisible_content_fails(self):
        from unittest import mock
        html = ('<html lang=zh-CN><head><title>标题</title></head><body><div hidden>隐藏</div>'
                '<p style="display:none">x</p><p>\u200b</p></body></html>')
        with mock.patch.object(sc, "fetch", lambda url, want_body=True, retries=2: (200, html)):
            r = sc.check_page("https://example.test/", "zh", "/", {}, "home")
        self.assertFalse(r["checks"]["visible_text"]["ok"])
        self.assertFalse(r["pass"])

    def test_hidden_body(self):
        for a in ("hidden", 'aria-hidden="true"', 'style="display:none"', 'style="visibility: hidden"'):
            self.assertEqual(sc.visible_text("<html><body %s><main><p>text</p></main></body></html>" % a), "", a)

    def test_hidden_html(self):
        for a in ("hidden", 'aria-hidden="true"', 'style="display:none"', 'style="visibility:hidden"'):
            self.assertEqual(sc.visible_text("<html %s><body><main><p>text</p></main></body></html>" % a), "", a)

    def test_visible_body_still_counts(self):
        self.assertEqual(sc.visible_text('<html lang=zh><body class=x style="color:red"><main><p>text</p></main></body></html>'), "text")

    def test_missing_body_tag_counts_nothing(self):
        self.assertEqual(sc.visible_text("<html><main><p>text</p></main></html>"), "")

    def run_page(self, html, path="/", ptype="home"):
        from unittest import mock
        with mock.patch.object(sc, "fetch", lambda url, want_body=True, retries=2: (200, html)):
            return sc.check_page("https://example.test/", "zh", path, {}, ptype)

    def test_zh_home_empty_main_with_nav_footer_fails(self):
        html = ("<html lang=zh-CN><body><header><nav><a href='/'>首页</a><a href='/about/'>关于</a>"
                "<span class=lang><a href='/en/'>English</a></span></nav></header>"
                "<main></main><footer>markjin 本站内容不含投资建议 2026</footer></body></html>")
        r = self.run_page(html)
        self.assertFalse(r["checks"]["visible_text"]["ok"])
        self.assertFalse(r["pass"])

    def test_no_main_fails(self):
        html = ("<html lang=zh-CN><body><nav><span class=lang><a href='/en/'>EN</a></span></nav>"
                "<div><p>大量正文文字但没有 main 元素</p></div></body></html>")
        r = self.run_page(html)
        self.assertFalse(r["checks"]["visible_text"]["ok"])
        self.assertIn("no <main>", r["checks"]["visible_text"]["detail"])
        self.assertFalse(r["pass"])

    def test_hidden_main_fails(self):
        self.assertEqual(sc.visible_text("<html><body><main hidden><p>text</p></main></body></html>"), "")

    def test_text_outside_main_not_counted(self):
        self.assertEqual(sc.visible_text("<html><body><nav>nav</nav><main><p>in</p></main><footer>f</footer></body></html>"), "in")

    def test_filler_characters_only_fail(self):
        for ch in ("\u3164", "&#x3164;", "\u115f", "\u1160", "\uffa0", "\u2800", "\u17b4\u17b5",
                   "\u3164\u115f\u1160\uffa0\u2800"):
            html = "<html lang=zh-CN><body><main><p>%s</p></main></body></html>" % ch
            self.assertEqual(sc.visible_text(html), "", repr(ch))
            r = self.run_page(html)
            self.assertFalse(r["checks"]["visible_text"]["ok"], repr(ch))
            self.assertFalse(r["pass"], repr(ch))

    def test_hidden_body_page_fails(self):
        from unittest import mock
        html = "<html lang=zh-CN><body hidden><main><p>正文</p></main></body></html>"
        with mock.patch.object(sc, "fetch", lambda url, want_body=True, retries=2: (200, html)):
            r = sc.check_page("https://example.test/", "zh", "/", {}, "home")
        self.assertFalse(r["checks"]["visible_text"]["ok"])
        self.assertFalse(r["pass"])


class Redirects(unittest.TestCase):
    B = "https://example.test/"
    HOME = ("<html lang=zh-CN><body><span class=lang><a href='/en/'>EN</a></span>"
            "<main><p>Hi</p></main></body></html>")

    def run_home(self, final):
        from unittest import mock
        def fake(url, want_body=True, retries=2):
            if url == self.B:
                sc._final[url] = final
            return (200, self.HOME)
        sc._final.clear()
        try:
            with mock.patch.object(sc, "fetch", fake):
                return sc.check_page(self.B, "zh", "/", {}, "home")
        finally:
            sc._final.clear()

    def test_redirect_off_site(self):
        self.assertFalse(self.run_home("https://evil.example/")["checks"]["body_language"]["ok"])

    def test_redirect_non_home_path(self):
        self.assertFalse(self.run_home("https://example.test/posts/x/")["checks"]["body_language"]["ok"])

    def test_redirect_query(self):
        self.assertFalse(self.run_home("https://example.test/?ref=1")["checks"]["body_language"]["ok"])

    def test_legit_redirect_to_root(self):
        r = self.run_home("https://example.test/")
        self.assertTrue(r["checks"]["body_language"]["ok"], r["checks"]["body_language"])

    def test_html_lang_must_match_path(self):
        from unittest import mock
        html = self.HOME.replace("lang=zh-CN", "lang=en")
        with mock.patch.object(sc, "fetch", lambda url, want_body=True, retries=2: (200, html)):
            r = sc.check_page(self.B, "zh", "/", {}, "home")
        self.assertFalse(r["checks"]["body_language"]["ok"])


def fake_site(pages):
    """pages: url -> (status, body) or (status, body, final_url). Unknown URLs -> 404."""
    def fetch(url, want_body=True, retries=2):
        v = pages.get(url, (404, None))
        if len(v) == 3:
            sc._final[url] = v[2]
        return v[0], v[1]
    return fetch


def html_page(lang, main, switch, extra=""):
    return ("<html lang=%s><body><span class=lang><a href='%s'>switch</a></span>%s"
            "<main>%s</main></body></html>" % (lang, switch, extra, main))


class SiteBase(unittest.TestCase):
    NOW = "2026-10-21T12:00"   # SGT, after the daily rule took effect: the 2026-10-21 daily is due

    def setUp(self):
        sc._final.clear()
        sc._cache.clear()
        from unittest import mock
        self._today = mock.patch.object(sc, "now_sgt", lambda: self.NOW)
        self._today.start()

    def tearDown(self):
        self._today.stop()
        sc._final.clear()
        sc._cache.clear()

    def check(self, pages, base, lang, path, ptype="daily"):
        from unittest import mock
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            return sc.check_page(base, lang, path, {}, ptype)


class Visibility(unittest.TestCase):
    def v(self, body):
        return sc.visible_text("<html><body><main>%s</main></body></html>" % body)

    def test_visible_child_of_visibility_hidden_parent_shows(self):
        self.assertEqual(self.v('<div style="visibility:hidden">a<p style="visibility:visible">b</p>c</div>'), "b")

    def test_visibility_hidden_inherited(self):
        self.assertEqual(self.v('<div style="visibility:hidden"><p><span>a</span></p></div>'), "")

    def test_display_none_not_overridable(self):
        self.assertEqual(self.v('<div style="display:none"><p style="visibility:visible;display:block">b</p></div>'), "")

    def test_hidden_attr_not_overridable(self):
        self.assertEqual(self.v('<div hidden><p style="visibility:visible">b</p></div>'), "")

    def test_visibility_collapse(self):
        self.assertEqual(self.v('<p style="visibility:collapse">a</p>'), "")

    def test_main_visibility_hidden_with_visible_child(self):
        self.assertEqual(sc.visible_text('<html><body><main style="visibility:hidden">a<b style="visibility:visible">b</b></main></body></html>'), "b")


class ParseStyle(unittest.TestCase):
    def test_later_declaration_wins(self):
        self.assertEqual(sc.parse_style("display:none; display:block")["display"], "block")
        self.assertEqual(sc.visible_text('<html><body><main><p style="display:none;display:block">a</p></main></body></html>'), "a")

    def test_important_beats_later(self):
        self.assertEqual(sc.parse_style("display:none !important; display:block")["display"], "none")
        self.assertEqual(sc.parse_style("display:none; display:block!IMPORTANT")["display"], "block")

    def test_custom_property_ignored(self):
        st = sc.parse_style("--display:none; --x: visibility:hidden")
        self.assertNotIn("display", st)
        self.assertNotIn("visibility", st)
        self.assertEqual(sc.visible_text('<html><body><main><p style="--display:none">a</p></main></body></html>'), "a")

    def test_substring_lookalikes_ignored(self):
        self.assertEqual(sc.visible_text('<html><body><main><p style="content:\'display:none\'; font-family: visibility:hidden">a</p></main></body></html>'), "a")
        self.assertNotIn("display", sc.parse_style("background:url(a;display:none)"))

    def test_comments_and_case(self):
        self.assertEqual(sc.parse_style("/* display:none */ DISPLAY : None")["display"], "none")
        self.assertEqual(sc.parse_style("/* display:none */ color:red"), {"color": "red"})

    def test_display_none_with_spaces(self):
        self.assertEqual(sc.visible_text('<html><body><main><p style=" display :  none ">a</p></main></body></html>'), "")


class RetiredSections(SiteBase):
    """Taken-down sections (decision 2026-10-11 22:39, quote_ref t212u): retired paths must 404,
    and no home page, expected sitemap or checked page may link to / list them."""
    B = "https://ex.test/"
    GOOD = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://ex.test/posts/daily/2026-10-21/</loc></url></urlset>')

    def site(self, **extra):
        pages = {self.B: (200, "<a href='/about/'>a</a>"), self.B + "en/": (200, "<a href='/en/about/'>a</a>"),
                 self.B + "sitemap.xml": (200, self.GOOD), self.B + "zh/sitemap.xml": (200, self.GOOD),
                 self.B + "en/sitemap.xml": (200, self.GOOD)}
        pages.update(extra)
        return pages

    def disc(self, pages, cfg=None):
        from unittest import mock
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            return sc.discover(self.B, cfg)

    def test_all_retired_404_passes(self):
        out = self.disc(self.site())
        self.assertFalse([p for p in out if p[0].startswith(("retired", "sources"))], out)
        self.assertIn("/framework/macro/", sc.discover.retired_ok)
        self.assertIn("/posts/tongyi/", sc.discover.retired_ok)

    def test_retired_path_still_served_fails(self):
        out = self.disc(self.site(**{self.B + "framework/macro/": (200, "x")}))
        bad = [p for p in out if p[0] == "retired /framework/macro/"]
        self.assertEqual(len(bad), 1)
        self.assertIn("must answer 404, got HTTP 200", bad[0][3][0])
        self.assertIsNone(bad[0][1])

    def test_redirect_is_not_404(self):
        out = self.disc(self.site(**{self.B + "posts/tongyi/": (301, None)}))
        self.assertTrue(any(p[0] == "retired /posts/tongyi/" for p in out))

    def test_home_link_to_retired_fails(self):
        out = self.disc(self.site(**{self.B + "en/": (200, "<a href='/en/framework/macro/'>m</a>")}))
        err = [p for p in out if p[0].startswith("sources")]
        self.assertEqual(len(err), 1)
        self.assertIn("/en/framework/macro/", err[0][3][0])

    def test_sitemap_listing_retired_fails(self):
        sm = self.GOOD.replace("</urlset>", "<url><loc>https://ex.test/posts/tongyi/01-zonglun/</loc></url></urlset>")
        out = self.disc(self.site(**{self.B + "zh/sitemap.xml": (200, sm)}))
        err = [p for p in out if p[0].startswith("sources")]
        self.assertEqual(len(err), 1)
        self.assertIn("retired path(s) still listed/linked: /posts/tongyi/01-zonglun/", err[0][3][0])

    def test_subpath_base(self):
        B = "https://ex.test/site/"
        self.assertTrue(sc.retired_hit(sc.site_path(B, B + "framework/macro/")))
        self.assertFalse(sc.retired_hit(sc.site_path(B, "https://ex.test/framework/macro/")))

    def test_page_link_to_retired_fails(self):
        html = html_page("zh-CN", "<p>" + "字" * 900 + "</p><a href='/framework/macro/'>m</a>", "/en/posts/daily/x/")
        pages = {self.B + "posts/daily/x/": (200, html), self.B + "en/posts/daily/x/": (200, "x"),
                 self.B + "framework/macro/": (200, "still there")}
        r = self.check(pages, self.B, "zh", "/posts/daily/x/")
        self.assertFalse(r["checks"]["internal_links"]["ok"])
        self.assertIn("retired", r["checks"]["internal_links"]["detail"])


class DailyGracePeriod(SiteBase):
    """Decision 2026-10-11 23:01 (quote_ref t217u): the two published dailies were deleted; dailies start
    2026-10-12. Before that date (SGT) the site may have no daily; from that date the minimum is 1 again.
    The welcome post is never a daily."""
    B = "https://ex.test/"
    GOOD = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://ex.test/posts/daily/2026-10-10-welcome/</loc></url></urlset>')

    def site(self, **extra):
        pages = {self.B: (200, "x"), self.B + "en/": (200, "x"),
                 self.B + "sitemap.xml": (200, self.GOOD), self.B + "zh/sitemap.xml": (200, self.GOOD),
                 self.B + "en/sitemap.xml": (200, self.GOOD),
                 self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-10-welcome/'>w</a>"),
                 self.B + "en/posts/daily/": (200, "<a href='/en/posts/daily/2026-10-10-welcome/'>w</a>")}
        pages.update(extra)
        return pages

    def disc(self, pages, today):
        from unittest import mock
        with mock.patch.object(sc, "fetch", fake_site(pages)), mock.patch.object(sc, "now_sgt", lambda: today if "T" in today else today + "T12:00"):
            return sc.discover(self.B)

    def test_welcome_is_not_a_daily(self):
        self.assertIsNone(sc.DAILY_RE.match("/posts/daily/2026-10-10-welcome/"))
        self.assertIsNone(sc.DAILY_RE.match("/en/posts/daily/2026-10-10-welcome/"))
        self.assertIsNotNone(sc.DAILY_RE.match("/posts/daily/2026-10-12/"))

    def test_zero_dailies_allowed_before_effective_date(self):
        out = self.disc(self.site(), "2026-10-11")
        self.assertFalse([p for p in out if "daily" in p[0]], out)
        self.assertIn("not yet in effect (starts 2026-10-12T07:00", sc.discover.daily_rule)
        self.assertIn("no zh daily found, allowed", sc.discover.daily_rule)

    def test_zero_dailies_fail_from_effective_date(self):
        for today in ("2026-10-12", "2026-11-01"):
            out = self.disc(self.site(), today)
            bad = [p for p in out if p[0] == "latest daily"]
            self.assertEqual(len(bad), 1, today)
            self.assertTrue(bad[0][3][0].startswith("FAIL: no zh daily post found"))

    def test_welcome_does_not_satisfy_minimum_from_effective_date(self):
        out = self.disc(self.site(), "2026-10-12")
        self.assertTrue(any(p[0] == "latest daily" and p[1] is None for p in out))

    def test_daily_present_before_date_is_still_paired(self):
        pages = self.site(**{self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-12/'>d</a>")})
        out = self.disc(pages, "2026-10-11")
        ld = [p for p in out if p[0] == "latest daily"]
        self.assertEqual(ld[0][1:3], ("/posts/daily/2026-10-12/", "/en/posts/daily/2026-10-12/"))

    def test_en_daily_without_zh_fails_even_in_grace(self):
        pages = self.site(**{self.B + "en/posts/daily/": (200, "<a href='/en/posts/daily/2026-10-12/'>d</a>")})
        out = self.disc(pages, "2026-10-11")
        self.assertTrue(any(p[0] == "latest daily" and "no zh daily" in p[3][0] for p in out))

    def test_effective_date_cannot_be_postponed(self):
        import json, tempfile, os
        ok = json.load(open(sc.DISCOVERY_CONFIG, encoding="utf-8"))
        self.assertEqual(ok["daily_min_effective_from"], "2026-10-12T07:00")
        for bad, msg in ((dict(ok, daily_min_effective_from="2026-10-12T06:59"), "earlier than the floor"),
                         (dict(ok, daily_min_effective_from="2026-10-11T07:00"), "earlier than the floor"),
                         (dict(ok, daily_min_effective_from="2026-10-19T07:01"), "later than the cap"),
                         (dict(ok, daily_min_effective_from="2099-01-01T00:00"), "later than the cap"),
                         (dict(ok, daily_min_effective_from="2026-10-12"), "YYYY-MM-DDTHH:MM"),
                         (dict(ok, daily_min_effective_from="12 Oct"), "YYYY-MM-DDTHH:MM")):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(bad, f)
            try:
                with self.assertRaises(sc.PairConfigError) as cm:
                    sc.load_discovery_config(f.name)
                self.assertIn(msg, str(cm.exception))
            finally:
                os.unlink(f.name)

    def test_effective_instant_is_0700_on_2026_10_12(self):
        out = self.disc(self.site(), "2026-10-12T06:59")
        self.assertFalse([p for p in out if "daily" in p[0]], out)
        out = self.disc(self.site(), "2026-10-12T07:00")
        due = [p for p in out if p[0] == "due daily"]
        self.assertEqual(due[0][1:3], ("/posts/daily/2026-10-12/", "/en/posts/daily/2026-10-12/"))

    def test_later_start_within_cap_is_accepted(self):
        import json, tempfile, os
        ok = json.load(open(sc.DISCOVERY_CONFIG, encoding="utf-8"))
        for later in ("2026-10-12T07:00", "2026-10-13T07:00", "2026-10-19T07:00"):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(dict(ok, daily_min_effective_from=later), f)
            try:
                sc.load_discovery_config(f.name)
            finally:
                os.unlink(f.name)

    def test_code_clamps_start_even_if_loader_is_bypassed(self):
        from unittest import mock
        early = dict(sc.DEFAULT_DISCOVERY, daily_min_effective_from="2026-10-01T00:00")
        with mock.patch.object(sc, "now_sgt", lambda: "2026-10-12T06:59"):
            self.assertIsNone(sc.due_daily(early)[0])          # cannot start before 2026-10-12T07:00
        late = dict(sc.DEFAULT_DISCOVERY, daily_min_effective_from="2099-01-01T00:00")
        with mock.patch.object(sc, "now_sgt", lambda: "2026-10-19T07:00"):
            self.assertEqual(sc.due_daily(late)[0], "2026-10-19")   # cannot be postponed past the cap
        later = dict(sc.DEFAULT_DISCOVERY, daily_min_effective_from="2026-10-14T07:00")
        with mock.patch.object(sc, "now_sgt", lambda: "2026-10-13T12:00"):
            self.assertIsNone(sc.due_daily(later)[0])

    def test_due_daily_is_checked_as_daily_type(self):
        short = html_page("zh-CN", "<p>" + "字" * 100 + "</p><p>本文不含投资建议。</p>", "/en/posts/daily/2026-10-21/")
        short_en = html_page("en", "<p>" + "word " * 30 + "</p><p>This article does not constitute investment advice.</p>",
                             "/posts/daily/2026-10-21/")
        pages = self.site(**{self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-20/'>d</a>"),
                             self.B + "posts/daily/2026-10-21/": (200, short),
                             self.B + "en/posts/daily/2026-10-21/": (200, short_en)})
        from unittest import mock
        real = sc.check_page
        with mock.patch.object(sc, "fetch", fake_site(pages)), mock.patch.object(sc, "now_sgt", lambda: "2026-10-21T08:00"):
            out = sc.discover(self.B)
            due = [p for p in out if p[0] == "due daily"]
            self.assertEqual(due[0][1], "/posts/daily/2026-10-21/")
            r = real(self.B, "zh", "/posts/daily/2026-10-21/", {}, "daily")
        self.assertFalse(r["checks"]["body_language"]["ok"], r["checks"]["body_language"])   # below 800 letters
        self.assertIn("sample", r["checks"]["body_language"]["detail"])
        self.assertEqual(sc.page_type_for("due daily"), "daily")
        self.assertEqual(sc.page_type_for("latest daily"), "daily")
        self.assertEqual(sc.page_type_for("about"), "about")

    def test_today_daily_due_after_0700(self):
        pages = self.site(**{self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-12/'>d</a>"),
                             self.B + "en/posts/daily/": (200, "<a href='/en/posts/daily/2026-10-12/'>d</a>")})
        out = self.disc(pages, "2026-10-14T08:00")      # 10-13 and 10-14 missed: an older daily is not enough
        due = [p for p in out if p[0] == "due daily"]
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0][1:3], ("/posts/daily/2026-10-14/", "/en/posts/daily/2026-10-14/"))
        self.assertIn("latest zh daily found: /posts/daily/2026-10-12/", due[0][3][0])

    def test_previous_day_due_before_0700(self):
        pages = self.site(**{self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-13/'>d</a>")})
        out = self.disc(pages, "2026-10-14T06:30")
        self.assertFalse([p for p in out if p[0] == "due daily"], out)
        out = self.disc(pages, "2026-11-01T06:59")      # month boundary: 10-31 is due
        self.assertEqual([p for p in out if p[0] == "due daily"][0][1], "/posts/daily/2026-10-31/")

    def test_today_present_is_checked_as_pair(self):
        pages = self.site(**{self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-14/'>d</a>")})
        out = self.disc(pages, "2026-10-14T07:00")
        self.assertFalse([p for p in out if p[0] == "due daily"], out)
        ld = [p for p in out if p[0] == "latest daily"]
        self.assertEqual(ld[0][1:3], ("/posts/daily/2026-10-14/", "/en/posts/daily/2026-10-14/"))

    def test_floor_lists_all_four_retired_daily_urls(self):
        for pth in ("/posts/daily/2026-10-10/", "/posts/daily/2026-10-11/",
                    "/en/posts/daily/2026-10-10/", "/en/posts/daily/2026-10-11/"):
            self.assertIn(pth, sc.FLOOR_RETIRED_PATHS)

    def test_retired_check_does_not_follow_redirects(self):
        import http.server, threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/posts/daily/2026-10-10/":
                    self.send_response(301); self.send_header("Location", "/gone/"); self.end_headers()
                else:
                    self.send_response(404); self.end_headers()

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = "http://127.0.0.1:%d" % srv.server_port
            self.assertEqual(sc.fetch_status_nofollow(base + "/posts/daily/2026-10-10/", retries=0), 301)
            self.assertEqual(sc.fetch_status_nofollow(base + "/posts/daily/2026-10-11/", retries=0), 404)
        finally:
            srv.shutdown()

    def test_retired_dailies_404_and_welcome_kept(self):
        out = self.disc(self.site(), "2026-10-11")
        for p in ("/posts/daily/2026-10-10/", "/posts/daily/2026-10-11/", "/en/posts/daily/2026-10-10/", "/en/posts/daily/2026-10-11/"):
            self.assertIn(p, sc.discover.retired_ok)
        self.assertFalse(sc.retired_hit("/posts/daily/2026-10-10-welcome/"))
        self.assertTrue(sc.retired_hit("/en/posts/daily/2026-10-10/"))


class DeploySha(unittest.TestCase):
    def test_arg(self):
        self.assertEqual(sc.deploy_sha("abc123"), ("abc123", "--deploy-sha"))

    def test_event_file(self):
        import json, os, tempfile
        from unittest import mock
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"workflow_run": {"head_sha": "deadbeef"}}, f)
        try:
            with mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": f.name}):
                self.assertEqual(sc.deploy_sha(""), ("deadbeef", "workflow_run.head_sha"))
        finally:
            os.unlink(f.name)

    def test_unknown(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=True):
            sha, src = sc.deploy_sha("")
        self.assertIsNone(sha)
        self.assertIn("unknown", src)


class LangSwitchSubpath(SiteBase):
    B = "https://ex.test/site/"
    MAIN = "<p>" + "中文正文内容" * 40 + "</p>"

    def test_subpath_home_whole_page_passes(self):
        pages = {self.B: (200, html_page("zh-CN", "<p>首页</p>", "/site/en/")),
                 self.B + "en/": (200, html_page("en", "<p>Home</p>", "/site/"))}
        r = self.check(pages, self.B, "zh", "/", "home")
        self.assertTrue(r["pass"], r["checks"])
        r = self.check(pages, self.B, "en", "/en/", "home")
        self.assertTrue(r["pass"], r["checks"])

    def test_subpath_switch_to_root_path_fails(self):
        pages = {self.B: (200, html_page("zh-CN", "<p>首页</p>", "/en/")),
                 self.B + "en/": (200, html_page("en", "<p>Home</p>", "/site/"))}
        r = self.check(pages, self.B, "zh", "/", "home")
        self.assertFalse(r["checks"]["lang_switch"]["ok"])
        self.assertFalse(r["pass"])

    def test_subpath_about_translation(self):
        pages = {self.B + "about/": (200, html_page("zh-CN", self.MAIN, "/site/en/about/")),
                 self.B + "en/about/": (200, html_page("en", "<p>x</p>", "/site/about/"))}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertTrue(r["checks"]["lang_switch"]["ok"], r["checks"]["lang_switch"])
        self.assertTrue(r["pass"], r["checks"])

    def test_switch_must_match_host(self):
        pages = {self.B + "about/": (200, html_page("zh-CN", self.MAIN, "https://evil.test/site/en/about/")),
                 self.B + "en/about/": (200, html_page("en", "<p>x</p>", "/site/about/"))}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertFalse(r["checks"]["lang_switch"]["ok"])

    def test_translation_redirecting_elsewhere_counts_as_missing(self):
        pages = {self.B + "about/": (200, html_page("zh-CN", self.MAIN, "/site/en/about/")),
                 self.B + "en/about/": (200, html_page("en", "<p>x</p>", "/site/"), self.B + "en/")}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertFalse(r["checks"]["lang_switch"]["ok"])
        self.assertIn("no translation", r["checks"]["lang_switch"]["detail"])


class PageBoundaries(SiteBase):
    B = "https://ex.test/"
    MAIN = "<p>" + "中文正文内容" * 40 + "</p>"

    def test_non_home_redirect_fails(self):
        pages = {self.B + "about/": (200, html_page("zh-CN", self.MAIN, "/en/about/"), self.B + "other/"),
                 self.B + "en/about/": (200, "x")}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertFalse(r["checks"]["final_url"]["ok"])
        self.assertFalse(r["pass"])

    def test_internal_link_offsite_redirect_fails(self):
        pages = {self.B + "about/": (200, html_page("zh-CN", self.MAIN + "<a href='/go/'>go</a>", "/en/about/")),
                 self.B + "en/about/": (200, "x"),
                 self.B + "go/": (200, "x", "https://evil.test/")}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertFalse(r["checks"]["internal_links"]["ok"])

    def test_internal_same_site_redirect_warns(self):
        pages = {self.B + "about/": (200, html_page("zh-CN", self.MAIN + "<a href='/old/'>old</a>", "/en/about/")),
                 self.B + "en/about/": (200, "x"),
                 self.B + "old/": (200, "x", self.B + "new/")}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertTrue(r["checks"]["internal_links"]["ok"])
        self.assertEqual(len(r["internal_redirects"]), 1)
        self.assertTrue(r["pass"], r["checks"])


class Labels(unittest.TestCase):
    def test_fail_and_review(self):
        r = {"pass": False, "review": True, "checks": {"a": {"ok": False}, "body_language": {"ok": False, "review": True}}}
        self.assertEqual(sc.result_label(r), "FAIL+REVIEW")
        r["checks"]["a"]["ok"] = True
        self.assertEqual(sc.result_label(r), "REVIEW")
        self.assertEqual(sc.result_label({"pass": True, "checks": {}}), "PASS")


class LanguageUsesVisibleMain(SiteBase):
    B = "https://ex.test/"

    def page(self, main_attrs, main, extra="", lang="zh-CN", sw="/en/posts/daily/d/"):
        return ("<html lang=%s><body><span class=lang><a href='%s'>s</a></span>%s"
                "<main %s>%s</main></body></html>" % (lang, sw, extra, main_attrs, main))

    def test_main_with_attributes_is_used(self):
        html = self.page('class="content" id=c', "<p>" + "中文" * 500 + "</p>")
        i = sc.body_language_ratio(html, "zh")
        self.assertEqual(i["main_count"], 1)
        self.assertEqual(i["raw_letters"], 1000)

    def test_english_main_with_hidden_chinese_fails(self):
        html = self.page('class="content"', "<p>" + "abcde " * 200 + "</p>",
                         extra="<div hidden>" + "汉字" * 250 + "</div><template>" + "汉字" * 250 + "</template>")
        i = sc.body_language_ratio(html, "zh")
        self.assertEqual(i["raw_ratio"], 0.0)
        self.assertEqual(sc.judge_language(i, "zh", "daily")[0], "fail")

    def test_hidden_chinese_inside_main_not_counted(self):
        html = self.page("", "<p>" + "abcde " * 200 + "</p><div style='display:none'>" + "汉字" * 400 +
                         "</div><span aria-hidden=true>" + "汉字" * 400 + "</span>")
        i = sc.body_language_ratio(html, "zh")
        self.assertEqual(i["raw_ratio"], 0.0)

    def test_no_main_no_whole_page_fallback(self):
        html = "<html lang=zh-CN><body><div>" + "中文" * 600 + "</div></body></html>"
        i = sc.body_language_ratio(html, "zh")
        self.assertEqual(i["raw_letters"], 0)
        self.assertEqual(sc.judge_language(i, "zh", "daily")[0], "fail")

    def test_multiple_main_fails(self):
        html = ("<html lang=zh-CN><body><main></main><main><p>" + "中文" * 600 +
                "</p></main></body></html>")
        i = sc.body_language_ratio(html, "zh")
        self.assertEqual(i["main_count"], 2)
        self.assertEqual(sc.judge_language(i, "zh", "daily")[0], "fail")
        pages = {self.B + "posts/daily/d/": (200, html)}
        r = self.check(pages, self.B, "zh", "/posts/daily/d/", "daily")
        self.assertFalse(r["checks"]["visible_text"]["ok"])

    def test_check_page_end_to_end(self):
        html = self.page('class="content"', "<p>" + "abcde " * 200 + "</p>",
                         extra="<div hidden>" + "汉字" * 500 + "</div>")
        pages = {self.B + "posts/daily/d/": (200, html), self.B + "en/posts/daily/d/": (200, "<html></html>")}
        r = self.check(pages, self.B, "zh", "/posts/daily/d/", "daily")
        self.assertFalse(r["checks"]["body_language"]["ok"])
        self.assertFalse(r["pass"])


class SharedLetterFilter(SiteBase):
    B = "https://ex.test/"

    def test_same_filter(self):
        txt = "中文abc123\u3164\u115f\u1160\uffa0\u2800\u200e，！"
        self.assertEqual(sc._ratio(txt)[1], len([c for c in txt if sc.is_letter(c)]))
        self.assertEqual(sc._ratio(txt)[1], 5)          # 中文abc: digits excluded
        self.assertEqual(sc.visible_text("<html><body><main>%s</main></body></html>" % txt), "中文abc123")

    def test_filler_padded_en_daily_fails(self):
        html = ("<html lang=en><body><span class=lang><a href='/posts/daily/d/'>zh</a></span>"
                "<main><p>中文" + "\u3164" * 900 + "</p></main></body></html>")
        i = sc.body_language_ratio(html, "en")
        self.assertEqual(i["raw_letters"], 2)
        pages = {self.B + "en/posts/daily/d/": (200, html), self.B + "posts/daily/d/": (200, "<html></html>")}
        r = self.check(pages, self.B, "en", "/en/posts/daily/d/", "daily")
        self.assertFalse(r["checks"]["body_language"]["ok"])
        self.assertFalse(r["pass"])


class DailyPairing(SiteBase):
    B = "https://ex.test/"

    def disc(self, pages):
        from unittest import mock
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            return [p for p in sc.discover(self.B) if p[0].startswith("latest daily")][0]

    def test_pairs_by_zh_date(self):
        pages = {self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-21/'>a</a><a href='/posts/daily/2026-10-20/'>b</a>"),
                 self.B + "en/posts/daily/": (200, "<a href='/en/posts/daily/2026-10-20/'>b</a>")}
        name, zh, en, notes = self.disc(pages)
        self.assertEqual(zh, "/posts/daily/2026-10-21/")
        self.assertEqual(en, "/en/posts/daily/2026-10-21/")
        self.assertTrue(any("differs" in n for n in notes))

    def test_missing_same_date_en_fails(self):
        zh = ("<html lang=zh-CN><body><span class=lang><a href='/en/'>en</a></span><main><p>" + "中文" * 500 +
              "</p></main></body></html>")
        pages = {self.B + "posts/daily/2026-10-21/": (200, zh)}
        r = self.check(pages, self.B, "en", "/en/posts/daily/2026-10-21/", "daily")
        self.assertFalse(r["checks"]["status_200"]["ok"])
        self.assertFalse(r["pass"])

    def test_no_zh_daily_fails(self):
        name, zh, en, notes = self.disc({})
        self.assertIsNone(zh)
        self.assertIsNone(en)
        self.assertTrue(notes[0].startswith("FAIL"))

    def test_main_reports_fail_for_missing_en(self):
        import io, contextlib
        from unittest import mock
        zh = ("<html lang=zh-CN><body><span class=lang><a href='/en/'>en</a></span><main><p>" + "中文" * 500 +
              "</p></main></body></html>")
        pages = {self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-21/'>a</a>"),
                 self.B + "en/posts/daily/": (200, "<a href='/en/posts/daily/2026-10-20/'>b</a>"),
                 self.B + "posts/daily/2026-10-21/": (200, zh)}
        out = io.StringIO()
        with mock.patch.object(sc, "fetch", fake_site(pages)), \
                mock.patch.object(sys, "argv", ["x", "--base", self.B, "--json-out", "/dev/null"]), \
                contextlib.redirect_stdout(out):
            rc = sc.main()
        self.assertEqual(rc, 1)
        self.assertIn("[en] FAIL https://ex.test/en/posts/daily/2026-10-21/", out.getvalue())


class VisibleLangSwitch(SiteBase):
    B = "https://ex.test/"
    MAIN = "<p>" + "中文正文内容" * 40 + "</p>"

    def test_hidden_correct_link_plus_visible_wrong_fails(self):
        html = ("<html lang=zh-CN><body><span class=lang hidden><a href='/en/about/'>EN</a></span>"
                "<span class=lang><a href='/en/wrong/'>EN</a></span><main>%s</main></body></html>" % self.MAIN)
        pages = {self.B + "about/": (200, html), self.B + "en/about/": (200, "x"), self.B + "en/wrong/": (200, "x")}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertFalse(r["checks"]["lang_switch"]["ok"])

    def test_only_hidden_switch_fails(self):
        html = ("<html lang=zh-CN><body><span class=lang style='display:none'><a href='/en/about/'>EN</a></span>"
                "<main>%s</main></body></html>" % self.MAIN)
        pages = {self.B + "about/": (200, html), self.B + "en/about/": (200, "x")}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertFalse(r["checks"]["lang_switch"]["ok"])


class LinksAndAssets(SiteBase):
    B = "https://ex.test/"
    MAIN = "<p>" + "中文正文内容" * 40 + "</p>"

    def run_extra(self, extra, pages_extra):
        html = ("<html lang=zh-CN><head><style>.x{background:url('/bg.png')}</style></head><body>"
                "<span class=lang><a href='/en/about/'>EN</a></span><main>%s%s</main></body></html>" % (self.MAIN, extra))
        pages = {self.B + "about/": (200, html), self.B + "en/about/": (200, "x"), self.B + "bg.png": (200, "x")}
        pages.update(pages_extra)
        return self.check(pages, self.B, "zh", "/about/", "about")

    def test_uppercase_host_is_internal(self):
        r = self.run_extra("<a href='https://EX.TEST/missing/'>x</a>", {})
        self.assertFalse(r["checks"]["internal_links"]["ok"])

    def test_srcset_poster_css_url(self):
        r = self.run_extra("<img srcset='/a.png 1x, /b.png 2x'><video poster='/p.png'></video>"
                           "<div style=\"background-image:url(/c.png)\"></div>",
                           {self.B + "a.png": (200, "x"), self.B + "p.png": (200, "x"), self.B + "c.png": (200, "x")})
        d = r["checks"]["internal_links"]["detail"]
        self.assertFalse(r["checks"]["internal_links"]["ok"])
        self.assertIn("/b.png", d)
        r = self.run_extra("<img srcset='/a.png 1x'>", {self.B + "a.png": (200, "x")})
        self.assertTrue(r["checks"]["internal_links"]["ok"], r["checks"]["internal_links"])

    def test_style_block_url_checked(self):
        r = self.run_extra("", {})
        self.assertTrue(r["checks"]["internal_links"]["ok"])
        self.assertIn("bg.png", " ".join(u for _, u in self._links()))
        r = self.run_extra("", {self.B + "bg.png": (404, None)})
        self.assertFalse(r["checks"]["internal_links"]["ok"])
        self.assertIn("/bg.png", r["checks"]["internal_links"]["detail"])

    def _links(self):
        p = sc.Page()
        p.feed("<style>.x{background:url('/bg.png')}</style>")
        return p.links


class MarkdownVisibleOnly(SiteBase):
    B = "https://ex.test/"
    MAIN = "<p>" + "中文正文内容" * 40 + "</p>"

    def test_hidden_markdown_tokens_ignored(self):
        html = ("<html lang=zh-CN><head><title>**t**</title></head><body><span class=lang><a href='/en/about/'>EN</a></span>"
                "<div hidden>**x**</div><main>%s<pre>__init__</pre></main></body></html>" % self.MAIN)
        pages = {self.B + "about/": (200, html), self.B + "en/about/": (200, "x")}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertTrue(r["checks"]["markdown_rendered"]["ok"], r["checks"]["markdown_rendered"])

    def test_visible_markdown_tokens_flagged(self):
        html = ("<html lang=zh-CN><body><span class=lang><a href='/en/about/'>EN</a></span>"
                "<main>%s<p>**bold**</p></main></body></html>" % self.MAIN)
        pages = {self.B + "about/": (200, html), self.B + "en/about/": (200, "x")}
        r = self.check(pages, self.B, "zh", "/about/", "about")
        self.assertFalse(r["checks"]["markdown_rendered"]["ok"])


class HomeDetail(SiteBase):
    def test_home_detail_is_plain(self):
        B = "https://ex.test/"
        html = "<html lang=zh-CN><body><span class=lang><a href='/en/'>EN</a></span><main><p>首页</p></main></body></html>"
        r = self.check({B: (200, html), B + "en/": (200, "x")}, B, "zh", "/", "home")
        d = r["checks"]["body_language"]["detail"]
        self.assertTrue(d.startswith("not checked: home page exemption"), d)
        self.assertNotIn("need", d)


class DigitsOnlyCountForVisibility(SiteBase):
    B = "https://ex.test/"

    def test_en_daily_of_digits_fails_minimum(self):
        html = ("<html lang=en><body><span class=lang><a href='/posts/daily/d/'>zh</a></span>"
                "<main><p>" + "2026 10 11 " * 200 + "</p></main></body></html>")
        i = sc.body_language_ratio(html, "en")
        self.assertEqual(i["raw_letters"], 0)
        self.assertNotEqual(sc.judge_language(i, "en", "daily")[0], "ok")
        pages = {self.B + "en/posts/daily/d/": (200, html), self.B + "posts/daily/d/": (200, "<html></html>")}
        r = self.check(pages, self.B, "en", "/en/posts/daily/d/", "daily")
        self.assertTrue(r["checks"]["visible_text"]["ok"])      # digits are visible text
        self.assertFalse(r["checks"]["body_language"]["ok"])
        self.assertFalse(r["pass"])

    def test_en_daily_few_letters_many_digits_is_review(self):
        html = ("<html lang=en><body><main><p>Short note. " + "1234567890" * 100 + "</p></main></body></html>")
        i = sc.body_language_ratio(html, "en")
        self.assertLess(i["letters"], sc.MIN_LETTERS["daily"])
        self.assertEqual(sc.judge_language(i, "en", "daily")[0], "review")

    def test_zh_padded_with_digits_gains_no_ratio(self):
        base = "<p>" + "中文" * 200 + "English words here " * 40 + "</p>"
        plain = sc.body_language_ratio("<html><body><main>%s</main></body></html>" % base, "zh")
        padded = sc.body_language_ratio("<html><body><main>%s<p>%s</p></main></body></html>"
                                        % (base, "１２３４５６７８９０" * 300 + "0" * 3000), "zh")
        self.assertEqual(plain["raw_ratio"], padded["raw_ratio"])
        self.assertEqual(plain["raw_letters"], padded["raw_letters"])


class TemplateMain(unittest.TestCase):
    def test_main_in_template_ignored(self):
        html = ("<html><body><template><main><p>x</p></main></template>"
                "<main><p>正文</p></main></body></html>")
        v = sc.parse_visible(html)
        self.assertEqual(v.main_count, 1)
        self.assertEqual(v.text(), "正文")

    def test_only_template_main_means_no_main(self):
        v = sc.parse_visible("<html><body><template><main><p>正文</p></main></template></body></html>")
        self.assertEqual(v.main_count, 0)
        self.assertEqual(sc.body_language_ratio("<html><body><template><main>中文</main></template></body></html>", "zh")["main_count"], 0)


class Srcset(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(sc.parse_srcset("/a.png 1x, /b.png 2x"), ["/a.png", "/b.png"])
        self.assertEqual(sc.parse_srcset("/a.png"), ["/a.png"])
        self.assertEqual(sc.parse_srcset("  /a.png 100w,\n/b.png 200w  "), ["/a.png", "/b.png"])

    def test_url_with_commas(self):
        self.assertEqual(sc.parse_srcset("/img/a,b.png 1x, /img/c,d.png 2x"), ["/img/a,b.png", "/img/c,d.png"])
        self.assertEqual(sc.parse_srcset("/x.png?w=1,2 1x"), ["/x.png?w=1,2"])

    def test_trailing_comma_ends_candidate(self):
        self.assertEqual(sc.parse_srcset("/a.png,/b.png 2x"), ["/a.png,/b.png"])
        self.assertEqual(sc.parse_srcset("/a.png, /b.png"), ["/a.png", "/b.png"])
        self.assertEqual(sc.parse_srcset("/a.png,, ,/b.png 2x,"), ["/a.png", "/b.png"])

    def test_descriptor_parens(self):
        self.assertEqual(sc.parse_srcset("/a.png foo(1,2) 1x, /b.png 2x"), ["/a.png", "/b.png"])

    def test_empty(self):
        self.assertEqual(sc.parse_srcset(""), [])
        self.assertEqual(sc.parse_srcset(" , ,"), [])


class ProfileNormalization(unittest.TestCase):
    CFG = sc.load_pair_config()

    def H(self, lang, main):
        return "<html lang=%s><body><main>%s</main></body></html>" % (lang, main)

    def cmp(self, zh, en):
        return sc.compare_pair("none", self.H("zh-CN", zh), self.H("en", en), self.CFG,
                               "https://markjin-lab.github.io/about/", "https://markjin-lab.github.io/en/about/")

    def test_protocol_relative_zh_missing_en_fails(self):
        r = self.cmp('<a href="//x.com/markjin">X</a>', "<p>none</p>")
        self.assertFalse(r["pair_profiles"]["ok"])
        self.assertIn("https://x.com/markjin", r["pair_profiles"]["detail"])

    def test_equivalent_forms_match(self):
        forms = ["//x.com/markjin", "https://x.com/markjin/", "http://X.COM/markjin", "https://www.x.com/markjin",
                 "HTTPS://x.com:443/markjin#top", "http://x.com:80/markjin/"]
        for f in forms:
            r = self.cmp('<a href="https://x.com/markjin">X</a>', '<a href="%s">X</a>' % f)
            self.assertTrue(r["pair_profiles"]["ok"], (f, r["pair_profiles"]))

    def test_different_profile_or_port_differs(self):
        self.assertFalse(self.cmp('<a href="https://x.com/markjin">X</a>', '<a href="https://x.com/other">X</a>')["pair_profiles"]["ok"])
        self.assertFalse(self.cmp('<a href="https://x.com/markjin">X</a>', '<a href="https://x.com:8443/markjin">X</a>')["pair_profiles"]["ok"])

    def test_norm_profile(self):
        self.assertEqual(sc.norm_profile("//X.com/a/#f", "https://s.test/p/")[0], "https://x.com/a")
        self.assertIsNone(sc.norm_profile("mailto:a@b.com", "https://s.test/"))

    def test_mailto_case_and_encoding(self):
        r = self.cmp('<a href="mailto:Markjin@Mail.GrokBot.com">c</a>', '<a href="mailto:markjin%40mail.grokbot.com?subject=hi">c</a>')
        self.assertTrue(r["pair_emails"]["ok"], r["pair_emails"])
        self.assertEqual(sc.mailto_addresses("MAILTO:A@B.com,c@d.com"), {"a@b.com", "c@d.com"})

    def test_mailto_missing_fails(self):
        self.assertFalse(self.cmp('<a href="mailto:a@b.com">c</a>', "<p>none</p>")["pair_emails"]["ok"])


class NonRenderedMain(unittest.TestCase):
    CFG = sc.load_pair_config()

    def test_noscript_main_not_counted(self):
        v = sc.parse_visible("<html><body><noscript><main>x</main></noscript><main><p>正文</p></main></body></html>")
        self.assertEqual(v.main_count, 1)
        self.assertEqual(v.text(), "正文")
        self.assertEqual(sc.parse_visible("<html><body><noscript><main>x</main></noscript></body></html>").main_count, 0)

    def test_compare_pair_template_main_before_real_main(self):
        zh = ("<html lang=zh-CN><body><template><main><p>每日 11:00 <a href='https://x.com/fake'>X</a> fake@x.com 统一系统观</p></main></template>"
              "<main><p>每日 06:30 <a href='https://x.com/markjin'>X</a> a@b.com</p></main></body></html>")
        en = ("<html lang=en><body><main><p>Daily 06:30 <a href='https://x.com/markjin'>X</a> a@b.com</p></main></body></html>")
        r = sc.compare_pair("none", zh, en, self.CFG)
        self.assertTrue(all(v["ok"] for v in r.values()), r)
        en2 = en.replace("06:30", "11:00")
        self.assertFalse(sc.compare_pair("none", zh, en2, self.CFG)["pair_times"]["ok"])
        cfg = {"profile_hosts": ["x.com"], "required_phrases": {"p": [{"zh": "统一系统观", "en": "Unified Systems View"}]}}
        self.assertFalse(sc.compare_pair("p", zh, en + "<p>Unified Systems View</p>", cfg)["pair_phrases"]["ok"])


class ParserDiscovery(unittest.TestCase):
    def test_anchor_hrefs_parser(self):
        html = ("<a class=x href='/framework/a/'>a</a><a href=/framework/b/>b</a>"
                "<a href=\"/posts/daily/2026-10-21/?x=1&amp;y=2\">c</a><!-- <a href='/framework/c/'> -->"
                "<script>var s='<a href=\"/framework/d/\">';</script><link href='/framework/e/'>")
        self.assertEqual(sc.html_anchor_hrefs(html), ["/framework/a/", "/framework/b/", "/posts/daily/2026-10-21/?x=1&y=2"])

    def test_sitemap_xml(self):
        xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               "<url><loc> https://ex.test/a/ </loc></url><url><loc>https://ex.test/b/?p=1&amp;q=2</loc></url></urlset>")
        self.assertEqual(sc.sitemap_locs(xml), ["https://ex.test/a/", "https://ex.test/b/?p=1&q=2"])
        with self.assertRaises(sc.SitemapError):
            sc.sitemap_locs("<loc>broken")
        with self.assertRaises(sc.SitemapError):
            sc.sitemap_locs("")

    def test_daily_list_via_parser(self):
        from unittest import mock
        B = "https://ex.test/"
        pages = {B + "posts/daily/": (200, "<ul><li><a href=/posts/daily/2026-10-21/>a</a></li>"
                                          "<!-- <a href='/posts/daily/2099-01-01/'>x</a> --></ul>")}
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            sp, _ = sc.latest_daily(B, "zh")
        self.assertEqual(sp, "/posts/daily/2026-10-21/")


class R13Ports(unittest.TestCase):
    P = "https://s.test/about/"

    def n(self, h):
        return sc.norm_profile(h, self.P)[0]

    def test_scheme_specific_default_port(self):
        self.assertEqual(self.n("https://x.com:443/markjin"), "https://x.com/markjin")
        self.assertEqual(self.n("http://x.com:80/markjin"), "https://x.com/markjin")
        self.assertEqual(self.n("http://x.com/markjin"), "https://x.com/markjin")

    def test_cross_ports_are_different(self):
        base = self.n("https://x.com/markjin")
        for h in ("https://x.com:80/markjin", "http://x.com:443/markjin", "https://x.com:8443/markjin",
                  "http://x.com:8080/markjin"):
            self.assertNotEqual(self.n(h), base, h)
        self.assertNotEqual(self.n("https://x.com:80/markjin"), self.n("http://x.com:80/markjin"))

    def test_compare_pair_https_port_80_fails(self):
        cfg = {"profile_hosts": ["x.com"], "required_phrases": {}}
        H = "<html lang=%s><body><main><a href='%s'>X</a></main></body></html>"
        r = sc.compare_pair("none", H % ("zh-CN", "https://x.com/markjin"), H % ("en", "https://x.com:80/markjin"), cfg)
        self.assertFalse(r["pair_profiles"]["ok"])
        r = sc.compare_pair("none", H % ("zh-CN", "https://x.com/markjin"), H % ("en", "http://x.com:443/markjin"), cfg)
        self.assertFalse(r["pair_profiles"]["ok"])
        r = sc.compare_pair("none", H % ("zh-CN", "https://x.com:443/markjin"), H % ("en", "http://x.com:80/markjin/"), cfg)
        self.assertTrue(r["pair_profiles"]["ok"], r)


class R13TemplateDiscovery(unittest.TestCase):
    def test_template_and_noscript_anchors_ignored(self):
        html = ("<a href='/posts/daily/2026-10-21/'>a</a><template><a href='/posts/daily/2026-10-12/'>t</a></template>"
                "<noscript><a href='/framework/n/'>n</a></noscript><a href='/framework/m/'>m</a>")
        self.assertEqual(sc.html_anchor_hrefs(html), ["/posts/daily/2026-10-21/", "/framework/m/"])

    def test_latest_daily_ignores_template_link(self):
        from unittest import mock
        B = "https://ex.test/"
        pages = {B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-21/'>a</a>"
                                          "<template><a href='/posts/daily/2026-10-12/'>x</a></template>")}
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            self.assertEqual(sc.latest_daily(B, "zh")[0], "/posts/daily/2026-10-21/")

    def test_template_links_not_link_checked(self):
        p = sc.Page()
        p.feed("<template><img src='/t.png'><a href='/t/'>t</a></template><a href='/real/'>r</a>")
        self.assertEqual(p.links, [("link", "/real/")])


class R13Mailto(unittest.TestCase):
    def test_decode_then_split(self):
        self.assertEqual(sc.mailto_addresses("mailto:a@b.com%2Cc@d.com"), {"a@b.com", "c@d.com"})
        self.assertEqual(sc.mailto_addresses("mailto:a@b.com%2Cc@d.com"), sc.mailto_addresses("mailto:a@b.com,c@d.com"))
        self.assertEqual(sc.mailto_addresses("mailto:A%40B.COM?cc=x@y.com"), {"a@b.com"})


class R13Sitemap(SiteBase):
    B = "https://ex.test/"

    def disc(self, pages):
        from unittest import mock
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            return sc.discover(self.B)

    def test_parse_failure_fails(self):
        pages = {self.B: (200, "<a href='/about/'>m</a>"),
                 self.B + "sitemap.xml": (200, "<urlset><url><loc>https://ex.test/posts/daily/x/</loc></url>")}
        out = self.disc(pages)
        err = [p for p in out if p[0] == "sources (sitemap error / retired link)"]
        self.assertEqual(len(err), 1)
        self.assertIn("parse error", err[0][3][0])
        self.assertIsNone(err[0][1])

    def test_absent_sitemap_fails(self):
        pages = {self.B: (200, "<a href='/about/'>m</a>")}
        out = self.disc(pages)
        err = [p for p in out if "sitemap error" in p[0]]
        self.assertEqual(len(err), 1)
        self.assertIn("expected sitemap /sitemap.xml -> HTTP 404", err[0][3][0])

    def test_empty_or_unusable_sitemap_fails(self):
        good = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://ex.test/posts/daily/2026-10-21/</loc></url></urlset>')
        for body, msg in (("", "empty sitemap body"), ("   \n", "empty sitemap body"),
                          ("<html><body>hi</body></html>", "not a sitemap"),
                          ("<urlset></urlset>", "no <loc>")):
            pages = {self.B: (200, "<a href='/about/'>m</a>"),
                     self.B + "sitemap.xml": (200, good), self.B + "en/sitemap.xml": (200, good),
                     self.B + "zh/sitemap.xml": (200, body)}
            sc._cache.clear()
            out = self.disc(pages)
            err = [p for p in out if "sitemap error" in p[0]]
            self.assertEqual(len(err), 1, body)
            self.assertIn(msg, err[0][3][0])

    def test_all_sitemaps_valid_no_error(self):
        good = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://ex.test/posts/daily/2026-10-21/</loc></url></urlset>')
        idx = ('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://ex.test/zh/sitemap.xml</loc></sitemap></sitemapindex>')
        pages = {self.B: (200, "x"), self.B + "sitemap.xml": (200, idx),
                 self.B + "zh/sitemap.xml": (200, good), self.B + "en/sitemap.xml": (200, good)}
        out = self.disc(pages)
        self.assertFalse(any("sitemap" in p[0] or "too few" in p[0] or p[0].startswith("retired") for p in out), out)

    def test_min_pages(self):
        from unittest import mock
        good = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://ex.test/posts/daily/2026-10-21/</loc></url></urlset>')
        pages = {self.B: (200, "x"), self.B + "sitemap.xml": (200, good), self.B + "zh/sitemap.xml": (200, good),
                 self.B + "en/sitemap.xml": (200, good),
                 self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-21/'>a</a>")}
        cfg = {"expected_sitemaps": ["/sitemap.xml", "/zh/sitemap.xml", "/en/sitemap.xml"],
               "min_pages": {"daily": 3}}
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            out = sc.discover(self.B, cfg)
        names = [p[0] for p in out]
        self.assertIn("daily (too few)", names)
        self.assertFalse(any(n.startswith("framework") for n in names))

    def test_discovery_config_validation(self):
        import tempfile, os, json
        sc.load_discovery_config()   # repo file is valid
        ok = json.load(open(sc.DISCOVERY_CONFIG, encoding="utf-8"))
        for bad in (dict(ok, expected_sitemaps=[]),
                    dict(ok, min_pages={"daily": 0}),
                    dict(ok, expected_sitemaps=["sitemap.xml"]),
                    {"expected_sitemaps": ["/sitemap.xml"]},
                    {k: v for k, v in ok.items() if k != "retired_paths"},
                    dict(ok, retired_prefixes=["/framework/"]),
                    dict(ok, retired_paths=["/posts/tongyi/", "/framework/macro/", "/en/framework/macro/", "/about/"])):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(bad, f)
            try:
                with self.assertRaises(sc.PairConfigError):
                    sc.load_discovery_config(f.name)
            finally:
                os.unlink(f.name)

    def test_sitemap_server_error_fails(self):
        pages = {self.B: (200, "<a href='/about/'>m</a>"), self.B + "zh/sitemap.xml": (500, None)}
        out = self.disc(pages)
        self.assertTrue(any("sitemap error" in p[0] for p in out))


class R13PairRobustness(SiteBase):
    EV = {"profile_hosts": ["x.com"], "required_phrases": {}, "event_times": {"about": [
        {"event": "review starts", "zh": "{T}\\s*开审", "en": "review starts at {T}"},
        {"event": "publish", "zh": "{T}\\s*发布", "en": ["published (?:at|by|before) {T}", "publish(?:es)? (?:at|by|before) {T}"]},
        {"event": "Monday proposal review", "zh": "每周一\\s*{T}", "en": "every Monday at {T}"}]}}
    ZH = "<html><body><main><p>每日 06:30 开审，07:00 发布（SGT）；改进提案每周一 10:00 审核。</p></main></body></html>"

    def ev(self, en_text):
        en = "<html><body><main><p>%s</p></main></body></html>" % en_text
        return sc.compare_pair("about", self.ZH, en, self.EV)

    def test_event_times_match(self):
        r = self.ev("Daily review starts at 06:30 and posts are published at 07:00 (SGT); "
                    "improvement proposals are reviewed every Monday at 10:00.")
        self.assertTrue(r["pair_event_times"]["ok"], r["pair_event_times"])
        self.assertTrue(r["pair_times"]["ok"])

    def test_swap_with_same_order_fails(self):
        # same set AND same order of appearance (06:30, 07:00, 10:00), but review/publish swapped
        r = self.ev("Posts are published at 06:30; daily review starts at 07:00; every Monday at 10:00.")
        self.assertTrue(r["pair_times"]["ok"])          # set check alone would pass
        self.assertFalse(r["pair_event_times"]["ok"])
        self.assertIn("review starts: zh 06:30, en 07:00", r["pair_event_times"]["detail"])

    def test_missing_event_fails(self):
        r = self.ev("Daily review starts at 06:30 and posts are published at 07:00. Proposals weekly at 10:00.")
        self.assertFalse(r["pair_event_times"]["ok"])
        self.assertIn("Monday proposal review: zh 10:00, en missing", r["pair_event_times"]["detail"])

    def test_set_check_kept_as_extra(self):
        r = self.ev("Daily review starts at 06:30 and posts are published at 07:00 (SGT); "
                    "every Monday at 10:00. Also 11:00.")
        self.assertTrue(r["pair_event_times"]["ok"])
        self.assertFalse(r["pair_times"]["ok"])

    def test_phrase_pairs_and_whitespace(self):
        cfg = {"profile_hosts": ["x.com"], "required_phrases": {"p": [
            {"pairs": [["统一系统观", "Unified Systems View"], ["统一的系统观", "Unified System View"]]}]}}
        def r(zh, en):
            return sc.compare_pair("p", "<html><body><main><p>%s</p></main></body></html>" % zh,
                                   "<html><body><main><p>%s</p></main></body></html>" % en, cfg)["pair_phrases"]
        self.assertTrue(r("统一 系统观", "the Unified\n  Systems View")["ok"])
        self.assertTrue(r("统一的系统观", "Unified System View")["ok"])
        cross = r("统一系统观", "Unified System View")      # zh variant 0 with en variant 1: not a registered pair
        self.assertFalse(cross["ok"])
        self.assertIn("not a registered pair", cross["detail"])

    def test_bad_config_raises_clear_error(self):
        import tempfile, os
        for content in ("{not json", '{"required_phrases": {"home": [{"zh": "x"}]}}', '[]',
                        '{"profile_hosts": "x.com"}'):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                f.write(content)
            try:
                with self.assertRaises(sc.PairConfigError):
                    sc.load_pair_config(f.name)
            finally:
                os.unlink(f.name)
        with self.assertRaises(sc.PairConfigError):
            sc.load_pair_config("/nonexistent/pairs.json")

    def run_main(self, pages, extra_args=()):
        import io, contextlib, json, tempfile, os
        from unittest import mock
        out = io.StringIO()
        with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as jf:
            path = jf.name
        try:
            with mock.patch.object(sc, "fetch", fake_site(pages)), \
                    mock.patch.object(sys, "argv", ["x", "--base", "https://ex.test/", "--json-out", path] + list(extra_args)), \
                    contextlib.redirect_stdout(out):
                rc = sc.main()
            with open(path, encoding="utf-8") as f:
                return rc, out.getvalue(), json.load(f)
        finally:
            os.unlink(path)

    def test_bad_config_reported_in_main(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{bad")
        try:
            rc, out, js = self.run_main({}, ["--pair-config", f.name])
        finally:
            os.unlink(f.name)
        self.assertEqual(rc, 1)
        self.assertIn("PAIR CONFIG ERROR", out)
        self.assertIn("not valid JSON", js["pair_config_error"])

    def test_pair_not_run_is_explicit_fail(self):
        rc, out, js = self.run_main({})
        home = [p for p in js["pages"] if p["name"] == "home"][0]
        pr = [r for r in home["results"] if r["lang"] == "zh+en"][0]
        self.assertFalse(pr["pass"])
        self.assertIn("pair_not_run", pr["checks"])
        self.assertIn("not run", pr["checks"]["pair_not_run"]["detail"])


class R14PhraseConfig(unittest.TestCase):
    def load(self, cfg):
        import tempfile, os, json
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
        try:
            return sc.load_pair_config(f.name)
        finally:
            os.unlink(f.name)

    def base(self):
        import json
        return json.load(open(sc.PAIR_CONFIG, encoding="utf-8"))

    def with_events(self):
        """Production config plus a test-only event list (production has no event pages since 2026-10-12)."""
        import copy
        c = self.base()
        c["event_times"]["about"] = copy.deepcopy(R13PairRobustness.EV["event_times"]["about"])
        return c

    def bad(self, cfg, msg):
        with self.assertRaises(sc.PairConfigError) as cm:
            self.load(cfg)
        self.assertIn(msg, str(cm.exception))

    def test_repo_config_valid(self):
        self.load(self.base())

    def test_required_pages_cannot_be_dropped(self):
        c = self.base(); del c["required_phrases"]["home"]; self.bad(c, "required_phrases['home']")
        c = self.base(); c["required_phrases"]["about"] = []; self.bad(c, "required_phrases['about']")
        c = self.base(); del c["required_phrases"]; self.bad(c, "required_phrases")
        c = self.base(); c["profile_hosts"] = []; self.bad(c, "profile_hosts")
        c = self.with_events(); c["event_times"]["about"] = []; self.bad(c, "event_times['about']")   # empty list still rejected

    def test_empty_variant_lists_rejected(self):
        c = self.base(); c["required_phrases"]["home"][0] = {"pairs": []}; self.bad(c, "pairs")
        c = self.base(); c["required_phrases"]["home"][0] = {"zh": ["统一系统观"], "en": ["Unified Systems View"]}
        self.bad(c, "registered as zh/en pairs")

    def test_short_phrases_rejected(self):
        c = self.base(); c["required_phrases"]["home"][0] = {"zh": "系统", "en": "Unified Systems View"}; self.bad(c, "too short")
        c = self.base(); c["required_phrases"]["home"][0] = {"zh": "统一系统观", "en": "View"}; self.bad(c, "too short")
        c = self.base(); c["required_phrases"]["home"][0] = {"pairs": [["统一系统观", "Unified Systems View"], ["统一", "Unified"]]}
        self.bad(c, "too short")
        self.assertTrue(sc.phrase_long_enough("认知实践"))
        self.assertTrue(sc.phrase_long_enough("abcd efgh"))
        self.assertFalse(sc.phrase_long_enough("abc 1234"))

    def test_event_pattern_validation(self):
        c = self.with_events(); c["event_times"]["about"][0]["en"] = "review starts at"; self.bad(c, "{T}")
        c = self.with_events(); c["event_times"]["about"][0]["zh"] = "{T}{T}"; self.bad(c, "{T}")
        c = self.with_events(); c["event_times"]["about"][0]["zh"] = "({T}"; self.bad(c, "not a valid regex")
        c = self.with_events(); c["event_times"]["about"][0]["event"] = ""; self.bad(c, "event")


class R15Floors(unittest.TestCase):
    load = R14PhraseConfig.load
    base = R14PhraseConfig.base
    with_events = R14PhraseConfig.with_events
    bad = R14PhraseConfig.bad
    def test_capture_group_patterns_rejected(self):
        c = self.with_events(); c["event_times"]["about"][0]["en"] = "(review starts) at {T}"
        self.bad(c, "capture groups besides {T}")
        c = self.with_events(); c["event_times"]["about"][0]["zh"] = "(?P<x>每日) {T}\\s*开审"
        self.bad(c, "capture groups besides {T}")
        c = self.with_events(); c["event_times"]["about"][0]["en"] = "(?:review|Review) starts at {T}"
        self.load(c)    # non-capturing groups are fine

    def test_capture_group_pattern_does_not_crash_at_runtime(self):
        self.assertEqual(sc.event_time("review starts at 06:30", "(review starts) at {T}", "en"), "06:30")
        self.assertIsNone(sc.event_time("x", "({T}", "en"))

    def test_capture_group_config_reported_by_main(self):
        import io, contextlib, json, tempfile, os
        from unittest import mock
        c = self.with_events(); c["event_times"]["about"][0]["en"] = "(review starts) at {T}"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(c, f)
        out = io.StringIO()
        try:
            with mock.patch.object(sc, "fetch", fake_site({})), \
                    mock.patch.object(sys, "argv", ["x", "--base", "https://ex.test/", "--pair-config", f.name,
                                                    "--json-out", "/dev/null"]), contextlib.redirect_stdout(out):
                rc = sc.main()
        finally:
            os.unlink(f.name)
        self.assertEqual(rc, 1)
        self.assertIn("PAIR CONFIG ERROR", out.getvalue())

    def test_phrase_count_floor(self):
        c = self.base(); c["required_phrases"]["about"] = c["required_phrases"]["about"][:1]
        self.bad(c, "below the floor of 2")
        c = self.base(); c["required_phrases"]["home"] = c["required_phrases"]["home"][:1]
        self.bad(c, "below the floor of 2")

    def test_event_floor(self):
        # No page keeps an event floor since the about page dropped its schedule (2026-10-12):
        # the production config has no about events and loads; an empty event_times is accepted.
        self.assertEqual(sc.REQUIRED_EVENT_PAGES, ())
        self.assertEqual(sc.REQUIRED_EVENTS, {})
        c = self.base()
        self.assertNotIn("about", c["event_times"])
        self.assertEqual(self.load(c)["event_times"], {})
        c["event_times"] = {}; self.load(c)
        del c["event_times"]; self.bad(c, "event_times must be an object")

    def test_profile_host_floor(self):
        c = self.base(); c["profile_hosts"] = ["x.com"]
        self.bad(c, "missing ['github.com']")

    def test_pairs_plus_zh_en_rejected(self):
        c = self.base(); c["required_phrases"]["home"][0] = {"pairs": [["统一系统观", "Unified Systems View"]], "zh": "认知实践与自我进化"}
        self.bad(c, "both 'pairs' and 'zh'/'en'")

    def dbad(self, cfg, msg):
        import tempfile, os, json
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
        try:
            with self.assertRaises(sc.PairConfigError) as cm:
                sc.load_discovery_config(f.name)
            self.assertIn(msg, str(cm.exception))
        finally:
            os.unlink(f.name)

    def test_discovery_floors(self):
        import json
        ok = json.load(open(sc.DISCOVERY_CONFIG, encoding="utf-8"))
        self.dbad(dict(ok, expected_sitemaps=["/sitemap.xml"]), "below the floor")
        self.dbad(dict(ok, min_pages={"daily": True}), "not a boolean")
        self.dbad(dict(ok, min_pages={"daily": 0}), "below the floor")
        self.dbad(dict(ok, retired_prefixes=["/posts/tongyi/"]), "retired_prefixes is below the floor")
        self.dbad(dict(ok, retired_paths=["/posts/tongyi/"]), "retired_paths is below the floor")


class R15Sources(SiteBase):
    B = "https://ex.test/"
    GOOD = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://ex.test/posts/daily/2026-10-21/</loc></url></urlset>')

    def test_all_sources_listed_with_counts(self):
        from unittest import mock
        pages = {self.B: (200, "<a href='/topics/'>m</a><a href='/about/'>a</a>"),
                 self.B + "sitemap.xml": (200, self.GOOD), self.B + "zh/sitemap.xml": (200, self.GOOD),
                 self.B + "en/sitemap.xml": (200, self.GOOD),
                 self.B + "posts/daily/": (200, "<a href='/posts/daily/2026-10-21/'>d</a>"),
                 self.B + "en/posts/daily/": (200, "<a href='/en/posts/daily/2026-10-21/'>d</a>")}
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            sc.discover(self.B)
        src = {(d["role"], d["url"]): d for d in sc.discover.sources}
        home = src[("seed", self.B)]
        self.assertEqual((home["status"], home["links"], home["site_paths"]), (200, 2, 2))
        self.assertEqual(src[("seed", self.B + "en/")]["status"], 404)
        self.assertFalse(any("framework" in r for r, _ in src))
        self.assertEqual(src[("en daily list", self.B + "en/posts/daily/")]["found"], 1)
        self.assertEqual(src[("zh daily list", self.B + "posts/daily/")]["found"], 1)
        self.assertEqual(src[("sitemap", self.B + "zh/sitemap.xml")]["links"], 1)
        line = sc.format_source(home)
        self.assertIn("2 link(s)", line)
        self.assertIn("2 in-site path(s)", line)

    def test_sitemap_with_only_offsite_locs_fails(self):
        from unittest import mock
        off = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://other.test/posts/daily/x/</loc></url></urlset>')
        pages = {self.B: (200, "<a href='/about/'>m</a>"), self.B + "sitemap.xml": (200, self.GOOD),
                 self.B + "zh/sitemap.xml": (200, off), self.B + "en/sitemap.xml": (200, self.GOOD)}
        with mock.patch.object(sc, "fetch", fake_site(pages)):
            out = sc.discover(self.B)
        err = [p for p in out if "sitemap error" in p[0]]
        self.assertEqual(len(err), 1)
        self.assertIn("no <loc> inside the site base", err[0][3][0])

    def test_report_json_has_sources(self):
        import io, contextlib, json, tempfile, os
        from unittest import mock
        with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as jf:
            path = jf.name
        out = io.StringIO()
        try:
            with mock.patch.object(sc, "fetch", fake_site({self.B: (200, "x")})), \
                    mock.patch.object(sys, "argv", ["x", "--base", self.B, "--json-out", path]), contextlib.redirect_stdout(out):
                sc.main()
            js = json.load(open(path, encoding="utf-8"))
        finally:
            os.unlink(path)
        roles = {d["role"] for d in js["discovery_sources"]}
        self.assertTrue({"seed", "sitemap", "zh daily list", "en daily list"} <= roles, roles)
        self.assertIn("discovery sources:", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class PairKeyInfo(unittest.TestCase):
    CFG = sc.load_pair_config()

    ZH_ABOUT = ("<p>markjin 的定位是“统一系统观在 AI 辅助加持下的认知实践与自我进化”。</p>"
                "<p>每日 06:30 开审，07:00 前发布（SGT）；改进提案每周一 10:00 审核。</p>"
                "<p>联系：contact@example.com</p>")
    EN_ABOUT = ("<p>markjin's positioning is cognitive practice and self-evolution of the Unified Systems View.</p>"
                "<p>Daily review starts at 06:30 and posts publish before 07:00 (SGT); proposals every Monday at 10:00.</p>"
                "<p>Contact: contact@example.com</p>")

    def run_pair(self, zh, en, name="about"):
        return sc.compare_pair(name, page(zh), page(en, "en"), self.CFG)

    def test_matching_pair_passes(self):
        r = self.run_pair(self.ZH_ABOUT, self.EN_ABOUT)
        self.assertTrue(all(v["ok"] for v in r.values()), r)

    def test_en_about_11_00_vs_zh_06_30_fails(self):
        zh = "<p>每日 06:30 开审（SGT）。统一系统观 认知实践与自我进化</p>"
        en = ("<p>Daily cross-review (11:00 SGT). Unified Systems View, cognitive practice and self-evolution</p>")
        r = self.run_pair(zh, en)
        self.assertFalse(r["pair_times"]["ok"])
        self.assertIn("11:00", r["pair_times"]["detail"])
        self.assertIn("06:30", r["pair_times"]["detail"])

    def test_time_normalisation_and_fullwidth_colon(self):
        r = self.run_pair("<p>6：30 开审</p>", "<p>review at 06:30</p>", name="none")
        self.assertTrue(r["pair_times"]["ok"], r)

    def test_times_outside_scope_ignored(self):
        zh = "<html lang=zh-CN><body><nav>11:00</nav><main><p>06:30</p></main><aside>12:00</aside></body></html>"
        en = "<html lang=en><body><main><p>06:30</p></main></body></html>"
        self.assertTrue(sc.compare_pair("none", zh, en, self.CFG)["pair_times"]["ok"])

    def test_footer_and_header_are_in_scope(self):
        zh = "<html lang=zh-CN><body><header>06:30</header><main><p>x</p></main><footer>a@b.com</footer></body></html>"
        en = "<html lang=en><body><main><p>x</p></main></body></html>"
        r = sc.compare_pair("none", zh, en, self.CFG)
        self.assertFalse(r["pair_times"]["ok"])
        self.assertFalse(r["pair_emails"]["ok"])

    # hidden content never counts: a hidden correct item must not hide a missing visible one
    def H(self, lang, main, footer=""):
        return "<html lang=%s><body><main>%s</main><footer>%s</footer></body></html>" % (lang, main, footer)

    def test_hidden_mailto_does_not_cover_missing_visible(self):
        zh = self.H("zh-CN", '<p><a href="mailto:a@b.com">联系</a></p>')
        en = self.H("en", '<p><a hidden href="mailto:a@b.com">Contact</a></p>')
        self.assertFalse(sc.compare_pair("none", zh, en, self.CFG)["pair_emails"]["ok"])

    def test_hidden_profile_link_does_not_cover_missing_visible(self):
        zh = self.H("zh-CN", "", '<a href="https://x.com/markjin">X</a>')
        for wrap in ('<span style="display:none">%s</span>', '<div aria-hidden="true">%s</div>',
                     '<template>%s</template>', '<p style="visibility:hidden">%s</p>'):
            en = self.H("en", "", wrap % '<a href="https://x.com/markjin">X</a>')
            r = sc.compare_pair("none", zh, en, self.CFG)
            self.assertFalse(r["pair_profiles"]["ok"], wrap)

    def test_hidden_email_text_does_not_count(self):
        zh = self.H("zh-CN", "<p>a@b.com</p>")
        en = self.H("en", '<p style="display:none">a@b.com</p>')
        self.assertFalse(sc.compare_pair("none", zh, en, self.CFG)["pair_emails"]["ok"])

    def test_hidden_time_does_not_count(self):
        zh = self.H("zh-CN", "<p>06:30</p>")
        en = self.H("en", "<p hidden>06:30</p>")
        self.assertFalse(sc.compare_pair("none", zh, en, self.CFG)["pair_times"]["ok"])

    def test_hidden_phrase_does_not_count(self):
        en = self.EN_ABOUT.replace("Unified Systems View", "framework") + \
            '<p hidden>Unified Systems View</p>'
        r = self.run_pair(self.ZH_ABOUT, en)
        self.assertFalse(r["pair_phrases"]["ok"])

    def test_hidden_wrong_plus_visible_correct_passes(self):
        zh = self.H("zh-CN", '<a href="https://x.com/markjin">X</a>')
        en = self.H("en", '<a href="https://x.com/markjin">X</a><a hidden href="https://x.com/old">X</a>')
        self.assertTrue(sc.compare_pair("none", zh, en, self.CFG)["pair_profiles"]["ok"])

    def test_email_mismatch_fails(self):
        r = self.run_pair(self.ZH_ABOUT, self.EN_ABOUT.replace("contact@example.com", "old@example.com"))
        self.assertFalse(r["pair_emails"]["ok"])

    def test_mailto_counts_as_email(self):
        r = self.run_pair('<p><a href="mailto:a@b.com">联系</a></p>', "<p>a@b.com</p>", name="none")
        self.assertTrue(r["pair_emails"]["ok"], r)

    def test_profile_url_mismatch_fails_and_other_links_ignored(self):
        zh = '<p><a href="https://x.com/markjin">X</a> <a href="https://fred.stlouisfed.org/a">src</a></p>'
        en = '<p><a href="https://x.com/markjin_old">X</a></p>'
        r = self.run_pair(zh, en, name="none")
        self.assertFalse(r["pair_profiles"]["ok"])
        self.assertNotIn("stlouisfed", r["pair_profiles"]["detail"])

    def test_profile_url_www_and_trailing_slash_equal(self):
        r = self.run_pair('<a href="https://www.github.com/markjin-lab/">g</a>',
                          '<a href="https://github.com/markjin-lab">g</a>', name="none")
        self.assertTrue(r["pair_profiles"]["ok"], r)

    def test_missing_en_positioning_phrase_fails(self):
        r = self.run_pair(self.ZH_ABOUT, self.EN_ABOUT.replace("Unified Systems View", "framework"))
        self.assertFalse(r["pair_phrases"]["ok"])
        self.assertIn("Unified Systems View", r["pair_phrases"]["detail"])

    def test_missing_zh_phrase_fails(self):
        r = self.run_pair(self.ZH_ABOUT.replace("统一系统观", "框架"), self.EN_ABOUT)
        self.assertFalse(r["pair_phrases"]["ok"])

    def test_repo_file_links_are_not_profiles(self):
        r = self.run_pair('<a href="https://github.com/example-org/example-data/blob/x/a.pdf">a</a>', "<p>none</p>", name="none")
        self.assertTrue(r["pair_profiles"]["ok"], r)

    def test_page_without_configured_phrases_only_checks_info(self):
        r = self.run_pair("<p>无</p>", "<p>none</p>", name="latest daily")
        self.assertTrue(all(v["ok"] for v in r.values()), r)


class Disclaimer(SiteBase):
    """Fixed article disclaimer: the last paragraph of a daily / macro / card page, verbatim."""
    B = "https://ex.test/"
    ZH = "本文不含投资建议。"
    EN = "This article does not constitute investment advice."

    def dc(self, lang, main, ptype="daily"):
        html = html_page("zh-CN" if lang == "zh" else "en", main, "/x/")
        return self.check({self.B + "p/": (200, html)}, self.B, lang, "/p/", ptype)["checks"].get("disclaimer")

    def test_exact_zh_and_en_pass(self):
        self.assertTrue(self.dc("zh", "<article><p>正文。</p><p>%s</p></article>" % self.ZH)["ok"])
        self.assertTrue(self.dc("en", "<article><p>Body.</p><p>%s</p></article>" % self.EN)["ok"])

    def test_missing_or_not_last_fails(self):
        self.assertFalse(self.dc("zh", "<article><p>正文。</p></article>")["ok"])
        self.assertFalse(self.dc("zh", "<article><p>%s</p><p>正文。</p></article>" % self.ZH)["ok"])

    def test_not_verbatim_fails(self):
        for t in ("本文不构成投资建议。", "本文不含投资建议", "本样例不含投资建议。"):
            self.assertFalse(self.dc("zh", "<article><p>%s</p></article>" % t)["ok"], t)
        self.assertFalse(self.dc("en", "<article><p>This article is not investment advice.</p></article>")["ok"])

    def test_hidden_disclaimer_does_not_count(self):
        self.assertFalse(self.dc("zh", "<article><p>正文。</p><p hidden>%s</p></article>" % self.ZH)["ok"])

    def test_applies_to_macro_and_cards_not_about(self):
        self.assertFalse(self.dc("zh", "<article><p>正文。</p></article>", "macro")["ok"])
        self.assertFalse(self.dc("zh", "<article><p>正文。</p></article>", "cards")["ok"])
        self.assertIsNone(self.dc("zh", "<article><p>正文。</p></article>", "about"))

    def test_fixtures_end_with_disclaimer(self):
        import os
        d = os.path.join(os.path.dirname(__file__), "fixtures")
        self.assertEqual(sc.last_body_paragraph(open(os.path.join(d, "sample-daily.zh.html"), encoding="utf-8").read()), self.ZH)
        self.assertEqual(sc.last_body_paragraph(open(os.path.join(d, "sample-daily.en.html"), encoding="utf-8").read()), self.EN)


class R16AboutOneLiner(unittest.TestCase):
    """About page reduced to one positioning line (decision 2026-10-12 06:28 SGT)."""
    ZH = "统一系统观在AI辅助加持下的认知实践与自我进化。"
    EN = "Cognitive practice and self-evolution of the Unified Systems View, augmented by AI assistance."

    def html(self, lang, text, sw):
        return ("<html lang=%s><body><span class=lang><a href='%s'>X</a></span><main><p>%s</p></main>"
                "<footer>%s</footer></body></html>" % (lang, sw, text, R17FooterDisclaimer.FOOTER["zh" if lang.startswith("zh") else "en"]))

    def run_page(self, pages, lang, path):
        from unittest import mock
        def fake(url, want_body=True, retries=2):
            return pages.get(url, (404, None))
        with mock.patch.object(sc, "fetch", fake):
            return sc.check_page("https://s.test/", lang, path, {}, "about")

    def pages(self):
        return {"https://s.test/about/": (200, self.html("zh-CN", self.ZH, "/en/about/")),
                "https://s.test/en/about/": (200, self.html("en", self.EN, "/about/"))}

    def test_short_about_passes_both_langs(self):
        for lang, path in (("zh", "/about/"), ("en", "/en/about/")):
            r = self.run_page(self.pages(), lang, path)
            self.assertTrue(r["checks"]["body_language"]["ok"], r["checks"]["body_language"])
            self.assertNotIn("exemption", r["checks"]["body_language"]["detail"])
            self.assertFalse(r.get("review"))
            self.assertTrue(r["pass"], r["checks"])
        self.assertNotIn("about", sc.MIN_LETTERS)

    def test_about_keeps_lang_switch_and_html_lang(self):
        p = self.pages()
        p["https://s.test/about/"] = (200, self.html("en", self.ZH, "/en/wrong/"))
        r = self.run_page(p, "zh", "/about/")
        self.assertFalse(r["checks"]["html_lang"]["ok"])
        self.assertFalse(r["checks"]["lang_switch"]["ok"])
        self.assertFalse(r["pass"])

    def test_about_keeps_link_check(self):
        p = self.pages()
        p["https://s.test/about/"] = (200, self.html("zh-CN", self.ZH + "<a href='/gone/'>g</a>", "/en/about/"))
        r = self.run_page(p, "zh", "/about/")
        self.assertFalse(r["pass"])

    def test_en_about_with_chinese_fails_language(self):
        p = self.pages()
        p["https://s.test/en/about/"] = (200, self.html("en",
            "统一系统观在AI辅助加持下的认知实践与自我进化。 Unified Systems View cognitive practice and self-evolution", "/about/"))
        r = self.run_page(p, "en", "/en/about/")
        self.assertFalse(r["checks"]["body_language"]["ok"], r["checks"]["body_language"])
        self.assertFalse(r["pass"])

    def test_zh_about_in_english_fails_language(self):
        p = self.pages()
        p["https://s.test/about/"] = (200, self.html("zh-CN", self.EN, "/en/about/"))
        r = self.run_page(p, "zh", "/about/")
        self.assertFalse(r["checks"]["body_language"]["ok"])

    def test_about_empty_main_still_fails(self):
        p = self.pages()
        p["https://s.test/about/"] = (200, self.html("zh-CN", "", "/en/about/"))
        r = self.run_page(p, "zh", "/about/")
        self.assertFalse(r["checks"]["body_language"]["ok"])

    def test_repo_pair_config_and_pair_check(self):
        cfg = sc.load_pair_config()
        self.assertNotIn("about", cfg["event_times"])
        r = sc.compare_pair("about", self.html("zh-CN", self.ZH, "/en/about/"),
                            self.html("en", self.EN, "/about/"), cfg)
        self.assertTrue(all(v["ok"] for v in r.values()), r)

    def test_repo_about_content_is_one_line(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for fn, line in (("about.md", self.ZH), ("about.en.md", self.EN)):
            body = open(os.path.join(root, "content", fn), encoding="utf-8").read().split("---", 2)[2].strip()
            self.assertEqual(body, line)


class R17FooterDisclaimer(unittest.TestCase):
    """Global footer carries a site-wide disclaimer (2026-10-12 06:37, wording 06:45); it never counts as the article's."""
    FOOTER = {"zh": "本站内容不构成投资建议。", "en": "Content on this site does not constitute investment advice."}
    def doc(self, lang, main):
        return ("<html lang=%s><body><main><article>%s</article></main><footer>%s</footer></body></html>"
                % (lang, main, self.FOOTER["zh" if lang.startswith("zh") else "en"]))

    def test_footer_never_satisfies_disclaimer(self):
        for lang, k in (("zh-CN", "zh"), ("en", "en")):
            h = ("<html lang=%s><body><main><article><p>x</p></article></main><footer><p>%s</p></footer></body></html>"
                 % (lang, sc.DISCLAIMER[k]))
            self.assertEqual(sc.last_body_paragraph(h), "x")

    def test_footer_does_not_satisfy_disclaimer(self):
        self.assertEqual(sc.last_body_paragraph(self.doc("zh-CN", "<p>正文一段。</p>")), "正文一段。")
        self.assertEqual(sc.last_body_paragraph(self.doc("en", "<p>Body text.</p>")), "Body text.")

    def test_article_disclaimer_still_found_with_footer(self):
        for lang, k in (("zh-CN", "zh"), ("en", "en")):
            h = self.doc(lang, "<p>x</p><p>%s</p>" % sc.DISCLAIMER[k])
            self.assertEqual(sc.last_body_paragraph(h), sc.DISCLAIMER[k])

    def test_footer_not_in_language_ratio(self):
        body = "<p>这是一段中文正文，用来计算比例。</p>"
        with_f = sc.body_language_ratio(self.doc("zh-CN", body), "zh")
        no_f = sc.body_language_ratio("<html lang=zh-CN><body><main><article>%s</article></main></body></html>" % body, "zh")
        self.assertEqual(with_f["letters"], no_f["letters"])
        self.assertEqual(with_f["raw_letters"], no_f["raw_letters"])
        en = sc.body_language_ratio(self.doc("en", "<p>English body only.</p>"), "en")
        self.assertEqual(en["raw_letters"], len("Englishbodyonly"))

    def test_i18n_footer_matches_site_disclaimer(self):
        import os, re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for k in ("zh", "en"):
            s = open(os.path.join(root, "i18n", k + ".toml"), encoding="utf-8").read()
            self.assertEqual(re.search(r'^footer_disclaimer = "(.*)"$', s, re.M).group(1), self.FOOTER[k])
            self.assertNotEqual(self.FOOTER[k], sc.DISCLAIMER[k])
            self.assertNotIn("footer_principle", s)
            self.assertNotIn("@", s)
