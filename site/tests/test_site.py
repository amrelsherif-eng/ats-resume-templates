import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import pytest
from playwright.sync_api import expect

from conftest import ALLOWED_HOSTS, CHECK_TIMEOUT, LIVE_URL, NO_OVERFLOW, ROOT, TEMPLATE_IDS, assert_no_browser_errors, score_of, upload


def test_loads_without_errors(page):
    page.set_viewport_size({"width": 1280, "height": 800})
    expect(page).to_have_title(re.compile("ATS Resume Templates"))
    page.wait_for_load_state("networkidle")
    assert_no_browser_errors(page)


@pytest.mark.parametrize("width", [320, 375, 768, 1024, 1440])
def test_no_horizontal_overflow(page, width):
    page.set_viewport_size({"width": width, "height": 900})
    assert page.evaluate(NO_OVERFLOW)
    page.locator("#lang").click()
    expect(page.locator("html")).to_have_attribute("dir", "rtl")
    assert page.evaluate(NO_OVERFLOW)


def test_template_cards(page):
    cards = page.locator("#grid .card:not(.request)")
    expect(cards).to_have_count(5)
    for template_id in TEMPLATE_IDS:
        card = page.locator(f"#tpl-{template_id}")
        overleaf = card.get_by_role("link", name="Edit on Overleaf")
        href = overleaf.get_attribute("href")
        raw_path = f"https://raw.githubusercontent.com/amrelsherif-eng/ats-resume-templates/main/templates/{template_id}/resume.tex"
        assert href.startswith("https://www.overleaf.com/docs?snip_uri=")
        assert quote(raw_path, safe="") in href
        expect(card.get_by_role("link", name="View sample PDF")).to_have_attribute("href", re.compile("overleaf.com"))
        expect(card.locator("[data-ai]")).to_have_count(1)
        expect(card.get_by_role("link", name="PDF", exact=True)).to_have_count(0)
        pdf = card.locator(".shot")
        response = page.request.get(f"{page.url.rsplit('/', 1)[0]}/{pdf.get_attribute('href')}")
        assert response.status == 200


def test_language_switch(page):
    heading = page.locator("h1")
    english = heading.inner_text()
    page.locator("#lang").click()
    expect(page.locator("html")).to_have_attribute("dir", "rtl")
    expect(page.locator("html")).to_have_attribute("lang", "ar")
    arabic = heading.inner_text()
    assert arabic != english and re.search(r"[\u0600-\u06ff]", arabic)
    page.reload(wait_until="networkidle")
    expect(page.locator("html")).to_have_attribute("lang", "ar")
    page.locator("#lang").click()
    expect(page.locator("html")).to_have_attribute("dir", "ltr")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.locator("#tpl-software-web h3")).to_have_text("Software Engineering")


def test_arabic_template_titles_and_brand(page):
    page.locator("#lang").click()
    expect(page.locator("nav .brand")).to_have_text("نماذج سيرة ذاتية ATS")
    expect(page.locator("#tpl-software-web h3")).to_have_text("هندسة البرمجيات")
    expect(page.locator("#tpl-software-web .tag")).to_have_text("Software Engineering")
    expect(page.locator("nav a[aria-label='نجمة على GitHub']")).to_be_visible()


@pytest.mark.parametrize("width", [360, 390])
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_template_actions_fit_on_mobile(page, width, lang):
    page.set_viewport_size({"width": width, "height": 900})
    if lang == "ar":
        page.locator("#lang").click()
    for actions in page.locator("#grid .card:not(.request) .actions").all():
        assert actions.evaluate("(e) => e.scrollWidth <= e.clientWidth")
        for action in actions.locator(".btn").all():
            assert action.evaluate("(e) => e.scrollWidth <= e.clientWidth")


def test_tabs_keyboard(page):
    tabs = page.locator(".tab")
    expect(tabs.nth(0)).to_have_attribute("aria-selected", "true")
    expect(tabs.nth(0)).to_contain_text("Overleaf")
    expect(page.locator("#p-ol")).to_be_visible()
    tabs.first.focus()
    page.keyboard.press("ArrowRight")
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    expect(tabs.nth(1)).to_contain_text("With AI")
    expect(page.locator("#p-ai")).to_be_visible()
    expect(page.locator("#p-ol")).to_be_hidden()
    page.locator("#local-link").click()
    expect(page.locator("#p-lc")).to_be_visible()
    expect(page.locator("#local-link")).to_have_attribute("aria-expanded", "true")
    expect(tabs).to_have_count(2)
    expect(tabs.nth(0)).to_have_attribute("aria-selected", "false")


def test_checker_length_guidance_and_mobile_placeholder(page):
    expect(page.locator("#chk-level legend")).to_have_text("How should we judge length?")
    expect(page.locator("#chk-level-hint")).to_have_text("One page is expected.")
    page.locator('#chk-level input[value="mid"]').check(force=True)
    expect(page.locator("#chk-level-hint")).to_have_text("Up to two pages is fine.")
    page.locator('#chk-level input[value="senior"]').check(force=True)
    expect(page.locator("#chk-level-hint")).to_have_text("Two pages is normal.")
    page.locator('#chk-level input[value="academic"]').check(force=True)
    expect(page.locator("#chk-level-hint")).to_have_text("Length is not limited.")

    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator("#chk-empty")).to_be_hidden()
    upload(page, ROOT / "templates/software-web/resume.pdf")
    expect(page.locator("#chk-out .ring-n")).to_be_visible(timeout=CHECK_TIMEOUT)
    expect(page.locator("#chk-out")).to_be_visible()


def test_checker_framing_and_footer_links(page):
    page.locator("#lang").click()
    expect(page.locator("#chk-level legend")).to_have_text("على أي أساس نحكم على الطول؟")
    expect(page.locator("#chk-level-hint")).to_have_text("المتوقع صفحة واحدة.")
    expect(page.locator("#faq-h")).to_have_text("قبل أن تبدأ")
    expect(page.locator("#faq details").nth(2)).to_have_attribute("open", "")
    expect(page.locator("#faq [data-i='a3']")).to_contain_text("إذا طلب إعلان الوظيفة صورة")
    expect(page.locator("#faq [data-i='a6']")).to_contain_text("النماذج باللغة الإنجليزية")
    expect(page.locator("footer [data-i='foot.made'] a")).to_have_attribute("href", "https://github.com/sb2nov/resume")
    expect(page.locator("footer [data-i='foot.checked']")).to_have_attribute(
        "href", "https://github.com/amrelsherif-eng/ats-resume-templates/actions/workflows/build.yml")
    expect(page.locator("footer [data-i='foot.issue']")).to_have_attribute(
        "href", "https://github.com/amrelsherif-eng/ats-resume-templates/issues/new?title=Template%20request%3A%20&body=Which%20career%20track%3F%0A%0AWhat%20should%20the%20template%20emphasise%3F")
    links = page.locator("#check .ext-note a")
    expect(links).to_have_count(2)
    for link in links.all():
        assert "noopener" in (link.get_attribute("rel") or "").split()
    expect(links.nth(0)).to_have_attribute("href", "https://www.jobscan.co/")
    expect(links.nth(1)).to_have_attribute("href", "https://resumeworded.com/")


def test_video_cards_are_compact_rows_on_mobile(page):
    page.set_viewport_size({"width": 390, "height": 844})
    # The featured tutorial and promo stack at full width on phones.
    section = page.locator("#video .vid-grid").bounding_box()
    demo = page.locator("#video .vid-new .video-frame").bounding_box()
    tut = page.locator("#video .vid-tut .video-frame").bounding_box()
    assert demo["width"] >= section["width"] - 4 and tut["width"] >= section["width"] - 4
    assert abs(demo["height"] / demo["width"] - 1.25) < 0.02
    assert abs(tut["height"] / tut["width"] - 9 / 16) < 0.02
    assert page.locator(".vid-grid .vid-card").first.get_attribute("class").endswith("vid-tut")
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
    expect(page.locator(".vid-new .video-duration")).to_have_text("0:41")
    page.locator("#lang").click()
    expect(page.locator(".vid-new .video-duration")).to_have_text("0:41")


def capture_clipboard(page):
    """Record what the page copies, without touching the machine's real clipboard (shared and flaky)."""
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("""() => {
      window.__copied = null;
      navigator.clipboard.writeText = async (t) => { window.__copied = t; };
    }""")


def copied_text(page, must_contain):
    page.wait_for_function("t => (window.__copied || '').includes(t)", arg=must_contain, timeout=15000)
    return page.evaluate("window.__copied")


def test_copy_prompt(page):
    capture_clipboard(page)
    page.locator("#t-ai").click()
    page.locator('#p-ai [data-copy="prompt"]').click()
    assert copied_text(page, "Fill this").startswith("Fill this LaTeX resume template")


def test_copy_for_ai(page):
    capture_clipboard(page)
    page.locator('[data-ai="software-web"]').click()
    copied = copied_text(page, "documentclass")
    assert copied.startswith("Fill this LaTeX resume template")
    assert "\\documentclass" in copied


def make_pdf(path, pages, lines_per_page):
    import pymupdf

    doc = pymupdf.open()
    for _ in range(pages):
        pdf_page = doc.new_page()
        for i, text in enumerate(lines_per_page):
            pdf_page.insert_text((60, 60 + i * 16), text, fontsize=10)
    doc.save(path)
    doc.close()
    return path


GOOD_LINES = [
    "Sara Ahmed", "sara@example.com | +20 100 000 0000 | Cairo, Egypt | linkedin.com/in/sara",
    "Education", "B.Com, Example University, Jun 2026",
    "Experience", "Finance Intern, Acme Co, Jun 2025 - Aug 2025",
] + [f"- Reconciled {n} bank accounts each month and cleared {n + 3} open items before close" for n in range(2, 20)] + [
    "Skills", "Excel, Power BI, SQL, SAP",
]


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_checker_scores_every_template_high(page, template_id):
    upload(page, ROOT / f"templates/{template_id}/resume.pdf")
    assert score_of(page) >= 90
    expect(page.locator("#chk-out .issue.fail")).to_have_count(0)
    page.locator("#chk-out details.chk-text").evaluate("d => d.open = true")
    expect(page.locator("#chk-out .chk-text pre")).to_contain_text("Your Name")
    assert_no_browser_errors(page)


def test_checker_page_rule_follows_experience(page, tmp_path):
    path = make_pdf(tmp_path / "two-pages.pdf", 2, GOOD_LINES)
    upload(page, path)
    score_of(page)
    pages_row = page.locator("#chk-out .issue", has_text=re.compile(r"\b2 pages"))
    expect(pages_row.first).to_have_class(re.compile(r"\bwarn\b"))
    page.locator('#chk-level input[value="senior"]').check(force=True)
    expect(page.locator("#chk-out .passed .issue.ok", has_text=re.compile(r"\b2 page"))).to_have_count(1)
    page.locator('#chk-level input[value="student"]').check(force=True)


def test_checker_scanned_like(page, tmp_path):
    import pymupdf

    path = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    pdf_page = doc.new_page()
    pdf_page.draw_rect(pymupdf.Rect(72, 72, 300, 300))
    doc.save(path)
    doc.close()
    upload(page, path)
    assert score_of(page) <= 25
    expect(page.locator("#chk-out .issue.fail").first).to_be_visible()


def test_checker_two_columns(page, tmp_path):
    import pymupdf

    path = tmp_path / "columns.pdf"
    doc = pymupdf.open()
    pdf_page = doc.new_page()
    left = ["CONTACT", "sara@example.com", "+20 100 000 0000", "Cairo, Egypt", "SKILLS", "Python", "SQL", "Excel"] * 3
    right = [f"- Built {n} Power BI dashboards for the regional sales team" for n in range(1, 25)]
    for i, t in enumerate(left):
        pdf_page.insert_text((40, 60 + i * 14), t, fontsize=9)
    for i, t in enumerate(right):
        pdf_page.insert_text((230, 60 + i * 14), t, fontsize=9)
    doc.save(path)
    doc.close()
    upload(page, path)
    assert score_of(page) < 85  # columns can scramble the reading order: never "Excellent"
    expect(page.locator("#chk-out .issue.warn", has_text=re.compile("column", re.I))).to_have_count(1)


def test_checker_weak_content(page, tmp_path):
    lines = ["Omar Hassan", "omar@example.com | +20 111 222 3333 | Giza, Egypt", "Experience"] + [
        "- Responsible for helping users with computer problems in the office every day" for _ in range(8)
    ] + ["- I am a hard-working team player", "Education", "BSc, Example University", "Skills", "Windows"]
    upload(page, make_pdf(tmp_path / "weak.pdf", 1, lines))
    # Clean formatting must not hide weak content (Resume Worded scored a similar CV 20/100).
    assert score_of(page) < 70
    for pattern in ["passive openers", "pronouns", "buzzwords", "word for word"]:
        expect(page.locator("#chk-out .issue", has_text=re.compile(pattern, re.I)).first).to_be_visible()


def test_checker_arabic_report(page):
    page.locator("#lang").click()
    upload(page, ROOT / "templates/network-cloud/resume.pdf")
    score_of(page)
    expect(page.locator("#chk-out .ring")).to_have_attribute("aria-label", re.compile(r"درجة قابلية القراءة لأنظمة ATS"))
    assert re.search(r"[؀-ۿ]", page.locator("#chk-out .chk-verdict").text_content())
    assert re.search(r"[؀-ۿ]", page.locator("#chk-out .passed .issue-t").first.text_content())


def test_checker_ai_prompt(page):
    capture_clipboard(page)
    upload(page, ROOT / "templates/mobile-apps/resume.pdf")
    score_of(page)
    page.locator("#chk-out .chk-tools button").click()
    assert "Your Name" in copied_text(page, "MY RESUME")


def test_checker_not_pdf(page, tmp_path):
    path = tmp_path / "not-really.pdf"
    path.write_text("this is plain text, not a PDF", encoding="utf-8")
    upload(page, path)
    expect(page.locator("#chk-out .chk-error")).to_be_visible(timeout=CHECK_TIMEOUT)
    assert not [e for e in page._site_errors if "Invalid PDF" not in e], page._site_errors


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_accessibility_axe(browser, site_url, lang):
    axe_path = os.environ.get("AXE_PATH")
    if not axe_path or not Path(axe_path).is_file():
        pytest.skip("Set AXE_PATH to axe.min.js to run the accessibility check")
    # axe is injected inline, so this check runs in its own context with CSP bypassed.
    context = browser.new_context(bypass_csp=True)
    page = context.new_page()
    page.goto(site_url, wait_until="networkidle", timeout=60_000 if LIVE_URL else 30_000)
    if lang == "ar":
        page.locator("#lang").click()
    page.add_script_tag(path=axe_path)
    violations = page.evaluate("""async () => {
      const result = await axe.run(document, {runOnly: ['wcag2a', 'wcag2aa']});
      return result.violations.filter(v => ['critical', 'serious'].includes(v.impact));
    }""")
    context.close()
    details = "\n".join(
        f"{v['id']}: {v['help']} ({len(v['nodes'])} nodes) e.g. {v['nodes'][0]['target']}" for v in violations)
    assert not violations, f"Serious accessibility violations:\n{details}"


def test_security_headers_meta(page):
    csp = page.locator('meta[http-equiv="Content-Security-Policy"]')
    expect(csp).to_have_count(1)
    content = csp.get_attribute("content")
    assert "script-src 'self'" in content
    assert "unsafe-inline" not in content and "unsafe-eval" not in content
    for link in page.locator('a[target="_blank"]').all():
        assert "noopener" in (link.get_attribute("rel") or "").split()



@pytest.mark.skipif(not LIVE_URL, reason="only meaningful against the deployed site")
def test_live_security_headers(page):
    headers = page.request.get(LIVE_URL + "/").headers
    if ".github.io" in LIVE_URL:
        # GitHub Pages ignores _headers: it sends HSTS itself, and CSP/referrer come from <meta> tags.
        assert "strict-transport-security" in headers
        page.goto(LIVE_URL + "/")
        expect(page.locator('meta[http-equiv="Content-Security-Policy"]')).to_have_count(1)
        expect(page.locator('meta[name="referrer"]')).to_have_count(1)
        return
    for name in ["content-security-policy", "x-content-type-options", "x-frame-options",
                 "strict-transport-security", "referrer-policy", "permissions-policy"]:
        assert name in headers, f"missing header {name}"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


def test_unknown_path_is_404(page, site_url):
    response = page.request.get(site_url + "/no-such-page-xyz")
    assert response.status == 404


def test_support_link_and_demo_video(page, site_url):
    # The support link points at GitHub Sponsors.
    expect(page.locator("#support")).to_be_visible()
    expect(page.locator("#support")).to_have_attribute("href", "https://github.com/sponsors/amrelsherif-eng")
    # The demo video is configured in app.js: it replaces the "coming soon" placeholder,
    # is served from this site (CSP media-src 'self'), never preloads, and has EN + AR captions.
    video = page.locator("#demo-video")
    # The poster is lazy: nothing under assets/video/ loads with the first screen.
    assert video.get_attribute("poster") is None
    assert page.locator("#tut-video source").count() == 0, "tutorial source must wait until the section is near"
    video.scroll_into_view_if_needed()
    expect(video).to_be_visible()
    expect(page.locator("#video-soon")).to_have_count(0)
    expect(video).to_have_attribute("preload", "none")
    expect(video).to_have_attribute("poster", re.compile(r"assets/video/demo-poster\.webp$"))
    src = video.locator("source").get_attribute("src")
    assert src == "assets/video/demo.mp4"
    tracks = video.locator("track")
    expect(tracks).to_have_count(2)
    assert sorted(t.get_attribute("srclang") for t in tracks.all()) == ["ar", "en"]
    base = site_url.rstrip("/") + "/"
    mp4 = page.request.get(base + src)
    assert mp4.status == 200
    assert mp4.headers["content-type"].startswith("video/mp4")
    assert len(mp4.body()) < 6 * 1024 * 1024, "keep the site video small for performance"
    for name in ("demo-poster.webp", "demo.en.vtt", "demo.ar.vtt"):
        assert page.request.get(base + "assets/video/" + name).status == 200
    assert page.request.get(base + "assets/video/demo.en.vtt").text().startswith("WEBVTT")
    # The full tutorial follows the site language and is self-hosted too.
    tut = page.locator("#tut-video")
    expect(tut).to_be_visible()
    expect(tut).to_have_attribute("preload", "none")
    expect(tut.locator("source")).to_have_attribute("src", "assets/video/tutorial-en.mp4")
    expect(tut).to_have_attribute("poster", re.compile(r"tutorial-poster-en\.webp$"))
    for name in ("tutorial-en.mp4", "tutorial-ar.mp4"):
        r = page.request.get(base + "assets/video/" + name)
        assert r.status == 200 and r.headers["content-type"].startswith("video/mp4")
        assert len(r.body()) < 25 * 1024 * 1024, "Cloudflare Pages rejects files over 25 MiB"
    for name in ("tutorial-poster-en.webp", "tutorial-poster-ar.webp"):
        assert page.request.get(base + "assets/video/" + name).status == 200
    buttons = page.locator(".tut-lang")
    expect(buttons).to_have_count(2)
    expect(page.locator('.tut-lang[data-tl="en"]')).to_contain_text("English")
    expect(page.locator('.tut-lang[data-tl="en"]')).to_have_attribute("aria-pressed", "true")
    page.locator('.tut-lang[data-tl="ar"]').click()
    expect(tut.locator("source")).to_have_attribute("src", "assets/video/tutorial-ar.mp4")
    expect(tut).to_have_attribute("poster", re.compile(r"tutorial-poster-ar\.webp$"))
    # The site is still English, so the chip describes the Arabic track in English.
    expect(page.locator(".vid-tut .video-chips li")).to_have_text("Egyptian Arabic voice-over + on-screen subtitles")
    expect(page.locator(".tut-ch-time")).to_have_text(["0:23", "0:50", "2:20", "3:27", "3:52"])
    expect(page.locator('.tut-lang[data-tl="ar"]')).to_have_attribute("aria-pressed", "true")
    expect(page.locator('.tut-lang[data-tl="en"]')).to_have_attribute("aria-pressed", "false")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    assert page.locator("footer nav").first.evaluate("n => getComputedStyle(n).position") == "static"


def test_tutorial_language_tracks_site_until_manual_choice(page):
    page.locator("#video").scroll_into_view_if_needed()
    tut = page.locator("#tut-video")
    page.locator("#lang").click()
    expect(tut.locator("source")).to_have_attribute("src", "assets/video/tutorial-ar.mp4")
    expect(tut).to_have_attribute("poster", re.compile(r"tutorial-poster-ar\.webp$"))
    page.locator('.tut-lang[data-tl="en"]').click()
    page.locator("#lang").click()
    expect(tut.locator("source")).to_have_attribute("src", "assets/video/tutorial-en.mp4")
    expect(tut).to_have_attribute("poster", re.compile(r"tutorial-poster-en\.webp$"))
    expect(page.locator("html")).to_have_attribute("lang", "en")


def test_tutorial_layout_and_chapters(page):
    page.set_viewport_size({"width": 1280, "height": 900})
    tut = page.locator(".vid-tut").bounding_box()
    promo = page.locator(".vid-new").bounding_box()
    assert tut["x"] < promo["x"] and tut["width"] > promo["width"]
    page.set_viewport_size({"width": 820, "height": 900})
    promo_frame = page.locator(".vid-new .video-frame").bounding_box()
    assert abs(promo_frame["width"] - 220) < 2
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
    page.locator("#video").scroll_into_view_if_needed()
    video = page.locator("#tut-video")
    video.evaluate("v => { v.muted = true; }")
    page.locator('.tut-ch[data-ch="2"]').click()
    page.wait_for_function("() => document.querySelector('#tut-video').currentTime >= 140", timeout=10000)
    styles = page.locator('.tut-lang[aria-pressed="true"]').evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color]")
    assert styles == ["rgb(98, 201, 212)", "rgb(6, 16, 21)"]


def test_local_link_hides_tab_indicator(page):
    tabs = page.locator(".tabs")
    page.locator("#local-link").click()
    expect(tabs).to_have_class(re.compile(r"\bno-sel\b"))
    # The indicator fades (0.22 s), so wait for the end value instead of reading it mid-transition.
    page.wait_for_function("() => getComputedStyle(document.querySelector('.tabs'), '::before').opacity === '0'")
    page.get_by_role("tab", name=re.compile("Overleaf")).click()
    page.wait_for_function("() => getComputedStyle(document.querySelector('.tabs'), '::before').opacity === '1'")


def test_seo_basics(page, site_url):
    assert page.locator('meta[name="description"]').get_attribute("content")
    assert page.locator('link[rel="canonical"]').get_attribute("href").startswith("https://")
    assert page.locator('meta[property="og:image"]').get_attribute("content").endswith(".png")
    assert page.locator("html").get_attribute("lang") in ("en", "ar")
    assert page.locator("h1").count() == 1
    for path in ("/robots.txt", "/sitemap.xml", "/assets/social-preview.png"):
        assert page.request.get(site_url + path).status == 200, path


def test_keyboard_skip_link_and_focus(page):
    page.keyboard.press("Tab")
    skip = page.locator("a.skip")
    expect(skip).to_be_focused()
    expect(skip).to_be_in_viewport()
    page.keyboard.press("Enter")
    assert page.evaluate("location.hash") == "#templates"
    # Focus rings must be visible on interactive elements.
    page.locator("#lang").focus()
    outline = page.locator("#lang").evaluate("e => getComputedStyle(e).outlineStyle")
    assert outline != "none"


def test_reduced_motion(browser, site_url):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    page.goto(site_url, wait_until="networkidle")
    durations = page.evaluate("""() => [...document.querySelectorAll('.caret, .scan, .badge')]
        .map(e => getComputedStyle(e).animationDuration)""")
    context.close()
    assert durations and all(d in ("0s", "1e-05s") or d.startswith("0") for d in durations), durations


def test_page_weight_budget(browser, site_url):
    """First visit (before using the checker) stays under 1.6 MB and loads fonts from the site itself."""
    context = browser.new_context()
    page = context.new_page()
    sizes, hosts = [], set()
    page.on("response", lambda r: (sizes.append(len(r.body())) if r.ok else None, hosts.add(urlparse(r.url).hostname)))
    page.goto(site_url, wait_until="networkidle")
    context.close()
    total = sum(sizes)
    assert total < 1_600_000, f"first load is {total / 1e6:.2f} MB"
    assert hosts <= ALLOWED_HOSTS, hosts


def test_scroll_reveal_never_leaves_content_hidden(browser, site_url):
    # Motion on: every section that fades in must end up visible once the user scrolls past it.
    page = browser.new_page(reduced_motion="no-preference", viewport={"width": 1280, "height": 800})
    page.goto(site_url + "/")
    height = page.evaluate("document.documentElement.scrollHeight")
    for y in range(0, height + 800, 400):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(60)
    page.wait_for_timeout(900)
    assert page.evaluate("document.querySelectorAll('.reveal:not(.is-visible)').length") == 0
    assert page.evaluate("document.querySelectorAll('.reveal').length") > 0
    page.close()


def test_english_page_does_not_download_arabic_font(browser, site_url):
    page = browser.new_page()
    fonts = []
    page.on("request", lambda r: fonts.append(r.url) if r.url.endswith(".woff2") else None)
    page.goto(site_url + "/")
    page.wait_for_load_state("networkidle")
    assert fonts and not [u for u in fonts if "arabic" in u], fonts
    page.close()


def test_arabic_browser_gets_arabic_without_layout_shift(browser, site_url):
    # lang-boot.js picks Arabic before the first paint; the page stays hidden until the text is Arabic.
    context = browser.new_context(locale="ar-EG", viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(site_url + "/")
    page.wait_for_load_state("networkidle")
    assert page.evaluate("() => [document.documentElement.dir, document.documentElement.lang]") == ["rtl", "ar"]
    assert page.evaluate("() => document.documentElement.classList.contains('i18n-wait')") is False
    expect(page.locator("h1")).not_to_contain_text("Your")
    shift = page.evaluate("""() => new Promise(done => {
        let total = 0;
        new PerformanceObserver(list => { for (const e of list.getEntries()) if (!e.hadRecentInput) total += e.value; })
            .observe({ type: 'layout-shift', buffered: true });
        setTimeout(() => done(total), 500);
    })""")
    assert shift < 0.1, shift
    context.close()
